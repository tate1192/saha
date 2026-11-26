"""Tests for the cost layer of a field operation.

Pins what the office relies on when it trusts a margin: one automatic line per
cost component, rebuilt (not doubled) on every refresh, a field worker closing
the job without touching the head-office money fields, and cost fields that stay
invisible to that worker.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("field_operation_cost", "post_install", "-at_install")
class TestFieldOperationCost(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Operation = cls.env["field.operation"]
        company = cls.env.company
        worker_group = cls.env.ref("field_operation.service_group_worker")
        cls.worker = cls.env["res.users"].create(
            {
                "name": "Cost Worker",
                "login": "cost_worker@example.com",
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
                "group_ids": [(6, 0, [worker_group.id])],
            }
        )
        office_group = cls.env.ref("field_operation.service_group_user")
        cls.office = cls.env["res.users"].create(
            {
                "name": "Cost Office",
                "login": "cost_office@example.com",
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
                "group_ids": [(6, 0, [office_group.id])],
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {"name": "Costed Employee", "user_id": cls.worker.id, "hourly_cost": 100.0}
        )
        cls.helper = cls.env["hr.employee"].create(
            {"name": "Costed Helper", "hourly_cost": 50.0}
        )
        start = fields.Datetime.now().replace(microsecond=0)
        cls.operation = cls.Operation.create(
            {
                "subject": "Costed Service",
                "status": "planned",
                "user_id": cls.env.user.id,
                "start_date": start,
                "end_date": start + timedelta(hours=2),
                "person_ids": [(6, 0, (cls.employee | cls.helper).ids)],
                "service_price": 1000.0,
                "contractor_cost": 200.0,
                "vehicle_cost": 50.0,
            }
        )

    def test_01_refresh_builds_one_line_per_component(self):
        """Two people x 2h, plus subcontractor and vehicle: 4 derived lines."""
        self.operation.action_refresh_costs()

        lines = self.operation.cost_line_ids
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(lines.mapped("auto")))
        labour = lines.filtered(lambda line: line.line_type == "personnel")
        self.assertEqual(len(labour), 2)
        self.assertEqual(sorted(labour.mapped("quantity")), [2.0, 2.0])
        self.assertEqual(sorted(labour.mapped("unit_cost")), [50.0, 100.0])
        self.assertAlmostEqual(sum(labour.mapped("amount")), 300.0)

        self.assertAlmostEqual(self.operation.personnel_cost, 300.0)
        self.assertAlmostEqual(self.operation.material_cost, 0.0)
        self.assertAlmostEqual(self.operation.external_cost, 250.0)
        self.assertAlmostEqual(self.operation.other_cost, 0.0)
        self.assertAlmostEqual(self.operation.total_cost, 550.0)
        self.assertAlmostEqual(self.operation.cost_hours, 4.0)
        self.assertAlmostEqual(self.operation.revenue_amount, 1000.0)
        self.assertAlmostEqual(self.operation.profit_amount, 450.0)
        self.assertAlmostEqual(self.operation.profit_percent, 45.0)

    def test_02_second_refresh_replaces_the_derived_lines(self):
        """A re-plan must move the cost, never pile a second set on top."""
        self.operation.action_refresh_costs()
        self.operation.action_refresh_costs()

        self.assertEqual(len(self.operation.cost_line_ids), 4)
        self.assertAlmostEqual(self.operation.total_cost, 550.0)

    def test_03_manual_line_survives_the_refresh(self):
        """Only the ``auto`` lines are rebuilt; typed cost is the office's."""
        self.operation.cost_line_ids.create(
            {
                "operation_id": self.operation.id,
                "line_type": "other",
                "name": "Parking",
                "quantity": 1.0,
                "unit_cost": 25.0,
            }
        )
        self.operation.action_refresh_costs()

        lines = self.operation.cost_line_ids
        self.assertEqual(len(lines), 5)
        manual = lines.filtered(lambda line: not line.auto)
        self.assertEqual(len(manual), 1)
        self.assertAlmostEqual(manual.amount, 25.0)
        self.assertAlmostEqual(self.operation.other_cost, 25.0)
        self.assertAlmostEqual(self.operation.total_cost, 575.0)

    def test_04_operation_without_price_shows_no_margin(self):
        """Revenue falls back to zero and the margin stays blank, not crashing."""
        self.operation.service_price = 0.0
        self.operation.contractor_cost = 0.0
        self.operation.vehicle_cost = 0.0
        self.operation.action_refresh_costs()

        self.assertAlmostEqual(self.operation.revenue_amount, 0.0)
        self.assertAlmostEqual(self.operation.profit_amount, -300.0)
        self.assertAlmostEqual(self.operation.profit_percent, 0.0)

    def test_05_worker_close_rebuilds_instead_of_doubling(self):
        """Regression: the worker who closes the job cannot read the cost lines.

        The rebuild must read them anyway, or the automatic set of the first
        close stays in the table and the second close adds a copy of it.
        """
        self.operation.action_refresh_costs()
        self.assertEqual(len(self.operation.cost_line_ids), 4)

        self.operation.with_user(self.worker).write({"status": "done"})
        self.assertEqual(len(self.operation.cost_line_ids), 4)

        self.operation.write({"status": "progress"})
        self.operation.with_user(self.worker).write({"status": "done"})
        self.assertEqual(len(self.operation.cost_line_ids), 4)
        self.assertAlmostEqual(self.operation.total_cost, 550.0)

    def test_06_money_fields_stay_office_only(self):
        Operation = self.env["field.operation"]
        worker_view = Operation.with_user(self.worker).browse(self.operation.id)
        self.assertNotIn("total_cost", Operation.with_user(self.worker).fields_get())
        self.assertNotIn("cost_line_ids", Operation.with_user(self.worker).fields_get())
        with self.assertRaises(AccessError):
            worker_view.read(["total_cost"])

    def test_07_refresh_button_is_head_office_only(self):
        """The button is hidden from them, and the RPC must refuse them too.

        Regression: the action was gated on the office group while the lines it
        rebuilds are head-office only, so an office user hit an AccessError on
        ``cost_line_ids`` in the middle of the refresh.
        """
        with self.assertRaises(AccessError):
            self.operation.with_user(self.worker).action_refresh_costs()
        with self.assertRaises(AccessError):
            self.operation.with_user(self.office).action_refresh_costs()
        self.operation.action_refresh_costs()
        self.assertEqual(len(self.operation.cost_line_ids), 4)

    def test_08_negative_cost_is_rejected(self):
        line = self.operation.cost_line_ids.create(
            {
                "operation_id": self.operation.id,
                "line_type": "other",
                "name": "Negative",
                "quantity": 1.0,
                "unit_cost": 10.0,
            }
        )
        with self.assertRaises(ValidationError):
            line.unit_cost = -10.0
        with self.assertRaises(ValidationError):
            line.quantity = -1.0

    def test_09_amount_follows_quantity_and_unit_cost(self):
        line = self.operation.cost_line_ids.create(
            {
                "operation_id": self.operation.id,
                "line_type": "other",
                "name": "Mileage",
                "quantity": 3.0,
                "unit_cost": 12.5,
            }
        )
        self.assertAlmostEqual(line.amount, 37.5)
        line.quantity = 4.0
        self.assertAlmostEqual(line.amount, 50.0)
        self.assertAlmostEqual(self.operation.other_cost, 50.0)
        self.assertAlmostEqual(self.operation.total_cost, 50.0)
