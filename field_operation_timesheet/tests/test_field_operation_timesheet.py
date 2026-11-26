"""Tests for the per-person time lines of a field operation.

Pins the flow the office bills on: a proposal from the planning, a lock on
approval, the totals the operation shows, and the reconciliation with HR
attendance that keeps the two numbers honest.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("field_operation_timesheet", "post_install", "-at_install")
class TestFieldOperationTimesheet(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Operation = cls.env["field.operation"]
        cls.TimeLine = cls.env["field.operation.time.line"]
        company = cls.env.company
        worker_group = cls.env.ref("field_operation.service_group_worker")
        cls.worker = cls.env["res.users"].create(
            {
                "name": "Time Worker",
                "login": "time_worker@example.com",
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
                "group_ids": [(6, 0, [worker_group.id])],
            }
        )
        cls.other_worker = cls.env["res.users"].create(
            {
                "name": "Time Other Worker",
                "login": "time_other_worker@example.com",
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
                "group_ids": [(6, 0, [worker_group.id])],
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {"name": "Timed Employee", "user_id": cls.worker.id}
        )
        cls.colleague = cls.env["hr.employee"].create(
            {"name": "Timed Colleague", "user_id": cls.other_worker.id}
        )
        cls.start = fields.Datetime.now().replace(microsecond=0)
        cls.operation = cls.Operation.create(
            {
                "subject": "Timed Service",
                "status": "planned",
                "user_id": cls.env.user.id,
                "start_date": cls.start,
                "end_date": cls.start + timedelta(hours=2),
                "person_ids": [(6, 0, (cls.employee | cls.colleague).ids)],
            }
        )

    def _line(self, employee=None, duration=2.0, date=None):
        return self.TimeLine.create(
            {
                "operation_id": self.operation.id,
                "employee_id": (employee or self.employee).id,
                "date": date or fields.Date.context_today(self.TimeLine),
                "duration": duration,
            }
        )

    def test_01_proposal_creates_one_draft_line_per_person(self):
        self.operation.action_generate_time_lines()

        lines = self.operation.time_line_ids
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines.mapped("employee_id"), self.employee | self.colleague)
        self.assertEqual(set(lines.mapped("state")), {"draft"})
        self.assertEqual(set(lines.mapped("duration")), {2.0})
        self.assertAlmostEqual(self.operation.time_draft, 4.0)
        self.assertAlmostEqual(self.operation.time_approved, 0.0)
        self.assertAlmostEqual(self.operation.time_expected, 4.0)

    def test_02_second_proposal_on_the_same_day_adds_nothing(self):
        self.operation.action_generate_time_lines()
        self.operation.action_generate_time_lines()

        self.assertEqual(len(self.operation.time_line_ids), 2)

    def test_03_proposal_for_another_day_adds_that_day(self):
        """Regression: the proposal deduped on the employee only, so a second
        day for the same team produced no line at all."""
        self.operation.action_generate_time_lines()
        start = self.start + timedelta(days=1)
        self.operation.write(
            {"start_date": start, "end_date": start + timedelta(hours=2)}
        )
        self.operation.action_generate_time_lines()

        self.assertEqual(len(self.operation.time_line_ids), 4)

    def test_04_proposal_needs_a_planned_window_and_a_team(self):
        empty = self.Operation.create(
            {"subject": "No Window", "status": "planned", "user_id": self.env.user.id}
        )
        with self.assertRaises(UserError):
            empty.action_generate_time_lines()
        empty.write(
            {"start_date": self.start, "end_date": self.start + timedelta(hours=1)}
        )
        with self.assertRaises(UserError):
            empty.action_generate_time_lines()

    def test_05_approval_locks_the_line(self):
        line = self._line()
        line.action_approve()

        self.assertEqual(line.state, "approved")
        self.assertEqual(line.approved_by, self.env.user)
        self.assertTrue(line.approved_on)
        with self.assertRaises(UserError):
            line.duration = 4.0
        with self.assertRaises(UserError):
            line.unlink()

        line.action_reset_draft()
        self.assertEqual(line.state, "draft")
        line.duration = 3.0
        self.assertAlmostEqual(line.duration, 3.0)

    def test_06_totals_split_draft_and_approved(self):
        self._line(duration=2.0)
        approved = self._line(employee=self.colleague, duration=1.5)
        approved.action_approve()

        self.assertAlmostEqual(self.operation.time_draft, 2.0)
        self.assertAlmostEqual(self.operation.time_approved, 1.5)
        self.assertAlmostEqual(self.operation.time_expected, 4.0)
        self.assertAlmostEqual(self.operation.time_difference, -2.5)

    def test_07_unassigned_employee_is_rejected(self):
        outsider = self.env["hr.employee"].create({"name": "Not On The Team"})
        with self.assertRaises(ValidationError):
            self._line(employee=outsider)

    def test_08_duration_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._line(duration=0.0)

    def test_09_field_worker_cannot_approve(self):
        line = self._line()
        with self.assertRaises(AccessError):
            line.with_user(self.worker).action_approve()
        with self.assertRaises(AccessError):
            self.operation.with_user(self.worker).action_approve_time_lines()

    def test_10_field_worker_only_reads_their_own_time(self):
        self._line()
        self._line(employee=self.colleague)

        visible = self.TimeLine.with_user(self.worker).search([])
        self.assertEqual(visible.employee_id, self.employee)
        self.assertNotIn(self.colleague, visible.employee_id)

    def test_11_reconciliation_compares_approved_time_with_attendance(self):
        if "hr.attendance" not in self.env:
            self.skipTest("hr_attendance is not installed")
        line = self._line(duration=2.0)
        line.action_approve()
        check_in = self.start
        self.env["hr.attendance"].create(
            {
                "employee_id": self.employee.id,
                "check_in": check_in,
                "check_out": check_in + timedelta(hours=3),
            }
        )
        today = fields.Date.context_today(self.TimeLine)
        wizard = self.env["field.operation.timesheet.reconciliation"].create(
            {"date_from": today, "date_to": today}
        )
        wizard.action_compute()

        row = wizard.line_ids.filtered(lambda rec: rec.employee_id == self.employee)
        self.assertEqual(len(row), 1)
        self.assertAlmostEqual(row.timesheet_hours, 2.0)
        self.assertAlmostEqual(row.attendance_hours, 3.0)
        self.assertAlmostEqual(row.difference, -1.0)

    def test_12_field_worker_cannot_run_the_reconciliation(self):
        Wizard = self.env["field.operation.timesheet.reconciliation"]
        today = fields.Date.context_today(self.TimeLine)
        # The ACL already refuses the wizard to a field worker...
        with self.assertRaises(AccessError):
            Wizard.with_user(self.worker).create({"date_from": today, "date_to": today})
        # ...and the action itself refuses the group, so a leaked record is not
        # enough to read everybody's hours.
        wizard = Wizard.create({"date_from": today, "date_to": today})
        with self.assertRaises(AccessError):
            wizard.with_user(self.worker).action_compute()
