# Copyright(C) 2025 - Today Softteknik Bilişim
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFieldOperationMachine(TransactionCase):
    """Behavioural tests for the field operation machine module.

    The suite focuses on the invariants that were previously broken:
    spare part stock consumption (P0), spare part wizard stock moves,
    cancellation/unlink integrity, the maintenance cron, maintenance cost
    recomputation, multi-company isolation and the server side guards.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock_location = cls.env.ref("stock.stock_location_stock")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_machine(self, **vals):
        base = {"name": "Test Machine"}
        base.update(vals)
        return self.env["machine.master"].create(base)

    def _make_product(self, quantity=0.0, price=10.0):
        template = self.env["product.template"].create(
            {
                "name": "Spare Part Test",
                "is_storable": True,
                "list_price": price,
            }
        )
        product = template.product_variant_id
        if quantity:
            self.env["stock.quant"]._update_available_quantity(
                product, self.stock_location, quantity
            )
        return product

    def _available(self, product):
        return self.env["stock.quant"]._get_available_quantity(
            product, self.stock_location
        )

    def _create_spare_part(self, machine, product, quantity=1.0, unit_price=10.0):
        return self.env["machine.spare.part"].create(
            {
                "machine_id": machine.id,
                "product_id": product.id,
                "quantity": quantity,
                "unit_price": unit_price,
                "source_type": "stock",
                "location_id": self.stock_location.id,
            }
        )

    # ------------------------------------------------------------------
    # T1 - P0: spare part consumption must actually reduce the stock
    # ------------------------------------------------------------------
    def test_spare_part_consumption_reduces_stock(self):
        """Confirming then completing a spare part must move real stock.

        The stock move has to reach the ``done`` state and the quantity held
        in the source location must decrease by the consumed quantity.
        """
        product = self._make_product(quantity=5.0)
        machine = self._create_machine()
        part = self._create_spare_part(machine, product, quantity=2.0)

        part.action_confirm()
        part.action_done()

        self.assertEqual(part.state, "done")
        self.assertTrue(part.stock_move_id, "no stock move was created")
        self.assertEqual(part.stock_move_id.state, "done")
        self.assertAlmostEqual(self._available(product), 3.0, places=2)

    def test_spare_part_insufficient_stock_raises(self):
        """Consuming more than the available stock must raise a UserError."""
        product = self._make_product(quantity=0.0)
        machine = self._create_machine()
        part = self._create_spare_part(machine, product, quantity=5.0)

        with self.assertRaises(UserError):
            part.action_confirm()
            part.action_done()

    # ------------------------------------------------------------------
    # T2 - wizard must produce stock moves and must not duplicate
    # ------------------------------------------------------------------
    def test_wizard_creates_spare_parts_with_stock_moves(self):
        """Spare parts created through the wizard must carry a stock move."""
        product = self._make_product(quantity=5.0)
        machine = self._create_machine()
        wizard = self.env["machine.spare.part.wizard"].create(
            {
                "machine_id": machine.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "quantity": 2.0,
                            "unit_price": 10.0,
                        },
                    )
                ],
            }
        )

        wizard.action_create_spare_parts()

        parts = self.env["machine.spare.part"].search([("machine_id", "=", machine.id)])
        self.assertEqual(len(parts), 1)
        self.assertTrue(parts.stock_move_id, "wizard did not create a stock move")
        parts.action_done()
        self.assertEqual(parts.state, "done")
        self.assertAlmostEqual(self._available(product), 3.0, places=2)

    def test_wizard_is_idempotent(self):
        """Running the wizard action twice must not duplicate the records."""
        product = self._make_product(quantity=5.0)
        machine = self._create_machine()
        wizard = self.env["machine.spare.part.wizard"].create(
            {
                "machine_id": machine.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "quantity": 2.0,
                            "unit_price": 10.0,
                        },
                    )
                ],
            }
        )

        wizard.action_create_spare_parts()
        first_count = self.env["machine.spare.part"].search_count(
            [("machine_id", "=", machine.id)]
        )
        # The wizard refuses a second submit on the same transient record instead of
        # silently creating another set of records.
        with self.assertRaises(UserError):
            wizard.action_create_spare_parts()
        second_count = self.env["machine.spare.part"].search_count(
            [("machine_id", "=", machine.id)]
        )
        self.assertEqual(first_count, second_count)

    # ------------------------------------------------------------------
    # T3 - cancellation / unlink integrity
    # ------------------------------------------------------------------
    def test_cancel_restores_stock(self):
        """Cancelling a completed spare part must give the stock back."""
        product = self._make_product(quantity=5.0)
        machine = self._create_machine()
        part = self._create_spare_part(machine, product, quantity=2.0)

        part.action_confirm()
        part.action_done()
        self.assertAlmostEqual(self._available(product), 3.0, places=2)

        part.action_cancel()
        self.assertAlmostEqual(self._available(product), 5.0, places=2)

    def test_unlink_completed_spare_part_is_blocked(self):
        """A spare part that already moved stock cannot be deleted."""
        product = self._make_product(quantity=5.0)
        machine = self._create_machine()
        part = self._create_spare_part(machine, product, quantity=2.0)

        part.action_confirm()
        part.action_done()

        with self.assertRaises(UserError):
            part.unlink()

    # ------------------------------------------------------------------
    # T4 - maintenance cron actually runs
    # ------------------------------------------------------------------
    def test_cron_upcoming_maintenance_schedules_activity(self):
        """The upcoming maintenance cron must act on machines due soon."""
        machine = self._create_machine()
        maintenance = self.env["machine.maintenance"].create({"machine_id": machine.id})
        maintenance.action_schedule()
        maintenance.action_start()
        maintenance.action_done()
        maintenance.next_maintenance_date = fields.Date.context_today(
            maintenance
        ) + timedelta(days=3)

        domain = [
            ("res_model", "=", "machine.master"),
            ("res_id", "=", machine.id),
        ]
        before = self.env["mail.activity"].search_count(domain)
        self.env["machine.maintenance"]._cron_notify_upcoming_maintenance()
        after = self.env["mail.activity"].search_count(domain)
        self.assertGreater(after, before)

    def test_cron_upcoming_maintenance_with_no_data_does_not_crash(self):
        """The cron must be a no-op (and not fail) when nothing is due."""
        self.env["machine.maintenance"]._cron_notify_upcoming_maintenance()

    # ------------------------------------------------------------------
    # T5 - maintenance cost must not stay stale
    # ------------------------------------------------------------------
    def test_parts_cost_recomputes_when_spare_part_changes(self):
        """parts_cost and total_cost must follow the spare part subtotals."""
        machine = self._create_machine()
        product = self._make_product(price=50.0)
        maintenance = self.env["machine.maintenance"].create(
            {"machine_id": machine.id, "labor_cost": 100.0}
        )
        part = self.env["machine.spare.part"].create(
            {
                "machine_id": machine.id,
                "maintenance_id": maintenance.id,
                "product_id": product.id,
                "quantity": 2.0,
                "unit_price": 50.0,
            }
        )

        maintenance.invalidate_recordset()
        self.assertAlmostEqual(maintenance.parts_cost, 100.0, places=2)
        self.assertAlmostEqual(maintenance.total_cost, 200.0, places=2)

        part.quantity = 3.0
        maintenance.invalidate_recordset()
        self.assertAlmostEqual(maintenance.parts_cost, 150.0, places=2)
        self.assertAlmostEqual(maintenance.total_cost, 250.0, places=2)

    # ------------------------------------------------------------------
    # T6 - multi-company isolation
    # ------------------------------------------------------------------
    def test_multi_company_isolation(self):
        """A user of company A must not see company B's machines."""
        company_a = self.env["res.company"].create({"name": "Company A"})
        company_b = self.env["res.company"].create({"name": "Company B"})
        service_user_group = self.env.ref("field_operation.service_group_user")
        user_a = self.env["res.users"].create(
            {
                "name": "Company A User",
                "login": "company_a_user_machine_test",
                "company_id": company_a.id,
                "company_ids": [(6, 0, [company_a.id])],
                "group_ids": [(6, 0, [service_user_group.id])],
            }
        )
        machine_a = self._create_machine(company_id=company_a.id)
        machine_b = self._create_machine(company_id=company_b.id)

        visible = (
            self.env["machine.master"]
            .with_user(user_a)
            .search([("id", "in", [machine_a.id, machine_b.id])])
        )
        self.assertIn(machine_a, visible)
        self.assertNotIn(machine_b, visible)

    # ------------------------------------------------------------------
    # T7 - server side guards
    # ------------------------------------------------------------------
    def test_maintenance_wrong_state_transition_raises(self):
        """A state transition that is not allowed must raise a UserError."""
        machine = self._create_machine()
        maintenance = self.env["machine.maintenance"].create({"machine_id": machine.id})
        maintenance.action_schedule()
        with self.assertRaises(UserError):
            maintenance.action_schedule()

    def test_maintenance_action_requires_service_user(self):
        """A non service user must not be able to drive the maintenance flow."""
        machine = self._create_machine()
        maintenance = self.env["machine.maintenance"].create({"machine_id": machine.id})
        worker_group = self.env.ref("field_operation.service_group_worker")
        worker = self.env["res.users"].create(
            {
                "name": "Field Worker",
                "login": "field_worker_machine_test",
                "group_ids": [(6, 0, [worker_group.id])],
            }
        )
        with self.assertRaises(AccessError):
            maintenance.with_user(worker).action_schedule()

    # ------------------------------------------------------------------
    # T7b - the removed model must not exist anymore
    # ------------------------------------------------------------------
    def test_maintenance_line_model_is_removed(self):
        """machine.maintenance.line was dropped from the registry."""
        self.assertNotIn("machine.maintenance.line", self.env.registry)

    # ------------------------------------------------------------------
    # T8 - the money fields are office-only
    # ------------------------------------------------------------------
    def test_worker_cannot_read_the_costs(self):
        """A worker sees maintenance and spare parts without the cost fields."""
        worker_group = self.env.ref("field_operation.service_group_worker")
        worker = self.env["res.users"].create(
            {
                "name": "Machine Cost Worker",
                "login": "machine_cost_worker",
                "group_ids": [(6, 0, [worker_group.id])],
            }
        )
        machine = self._create_machine()
        maintenance = self.env["machine.maintenance"].create(
            {"machine_id": machine.id, "labor_cost": 50.0}
        )
        product = self._make_product(quantity=2.0)
        spare = self._create_spare_part(machine, product, quantity=1.0, unit_price=10.0)

        self.assertNotIn(
            "total_cost", self.env["machine.maintenance"].with_user(worker).fields_get()
        )
        self.assertNotIn(
            "unit_price", self.env["machine.spare.part"].with_user(worker).fields_get()
        )
        with self.assertRaises(AccessError):
            maintenance.with_user(worker).read(["labor_cost"])
        with self.assertRaises(AccessError):
            spare.with_user(worker).read(["unit_price"])
