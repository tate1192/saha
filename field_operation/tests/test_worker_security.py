"""Record-rule and field-level security for the Field Worker role.

The worker record rule is split in two: reading covers the worker's own jobs in
every non-draft status (the mobile history and the desktop list need the closed
ones), writing stays on the open part of the flow. The money fields carry
``groups=`` so a worker cannot read them even through a direct RPC call.
"""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestWorkerSecurity(TransactionCase):
    """Pins the read/write split and the office-only money fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        worker_group = cls.env.ref("field_operation.service_group_worker")
        office_group = cls.env.ref("field_operation.service_group_user")
        company = cls.env.company
        cls.worker = cls.env["res.users"].create(
            {
                "name": "Rule Worker",
                "login": "rule_worker@example.com",
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
                "group_ids": [(6, 0, [worker_group.id])],
            }
        )
        cls.office = cls.env["res.users"].create(
            {
                "name": "Rule Office",
                "login": "rule_office@example.com",
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
                "group_ids": [(6, 0, [office_group.id])],
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {"name": "Rule Worker Employee", "user_id": cls.worker.id}
        )
        Operation = cls.env["field.operation"]
        people = [(6, 0, cls.employee.ids)]
        office_user = {"user_id": cls.office.id}
        cls.planned = Operation.create(
            dict(
                office_user,
                subject="Worker planned job",
                status="planned",
                person_ids=people,
                service_price=150.0,
            )
        )
        cls.done = Operation.create(
            dict(
                office_user,
                subject="Worker closed job",
                status="done",
                person_ids=people,
                service_price=150.0,
            )
        )
        cls.draft = Operation.create(
            dict(
                office_user,
                subject="Worker draft job",
                status="draft",
                person_ids=people,
            )
        )
        cls.foreign = Operation.create(
            dict(office_user, subject="Someone else's job", status="progress")
        )

    def test_read_scope_covers_closed_jobs_but_not_drafts(self):
        visible = self.env["field.operation"].with_user(self.worker).search([])
        self.assertIn(self.planned, visible)
        self.assertIn(self.done, visible)
        self.assertNotIn(self.draft, visible)
        self.assertNotIn(self.foreign, visible)

    def test_write_scope_stops_at_the_closed_job(self):
        self.planned.with_user(self.worker).write({"subject": "worker edited"})
        with self.assertRaises(AccessError):
            self.done.with_user(self.worker).write({"subject": "too late"})
        with self.assertRaises(AccessError):
            self.foreign.with_user(self.worker).write({"subject": "not mine"})

    def test_service_price_is_office_only(self):
        Operation = self.env["field.operation"]
        office_job = Operation.with_user(self.office).browse(self.done.id)
        self.assertEqual(office_job.service_price, 150.0)
        with self.assertRaises(AccessError):
            Operation.with_user(self.worker).browse(self.done.id).read(
                ["service_price"]
            )
        self.assertNotIn("service_price", Operation.with_user(self.worker).fields_get())
        groups = (Operation._fields["service_price"].groups or "").split(",")
        self.assertIn("base.group_portal", groups)
