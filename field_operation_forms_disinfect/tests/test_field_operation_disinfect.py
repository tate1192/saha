"""Tests for the independent disinfection form lines.

The form flow owns its data: the lines live in
``field.operation.forms.disinfect`` and the PH/CL readings live on the form.
No operation is created or updated.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("field_operation_forms_disinfect", "post_install", "-at_install")
class TestFieldOperationFormsDisinfect(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.forms_model = cls.env["field.operation.forms"]
        cls.line_model = cls.env["field.operation.forms.disinfect"]
        cls.partner = cls.env["res.partner"].create({"name": "Disinfect Customer"})
        cls.service_type = cls.env["field.operation.type"].search(
            [("type", "=", "disinfect")], limit=1
        )
        cls.product = cls.env["field.disinfect.product"].create({"name": "Dispenser"})

    def _user(self, login, *groups):
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "group_ids": [
                    Command.set(
                        [self.env.ref("base.group_user").id]
                        + [self.env.ref(xmlid).id for xmlid in groups]
                    )
                ],
            }
        )

    def _form(self, **values):
        values.setdefault("customer_id", self.partner.id)
        values.setdefault("service_type_id", self.service_type.id)
        return self.forms_model.create(values)

    def _line(self, form, **values):
        values.setdefault("product_id", self.product.id)
        values.setdefault("forms_id", form.id)
        return self.line_model.create(values)

    def test_01_line_lives_on_the_form(self):
        """The form is the only parent: there is no operation link."""
        form = self._form(
            subject="Disinfection visit",
            start_date="2026-01-02 09:00:00",
            end_date="2026-01-02 10:00:00",
        )
        line = self._line(form, tank_dimensions="200L", cleaning=True)

        self.assertTrue(line.name.startswith("DIS-F-"), line.name)
        self.assertEqual(line.forms_id, form)
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.tank_dimensions, "200L")
        self.assertTrue(line.cleaning)
        self.assertEqual(line.customer_id, self.partner)
        self.assertEqual(line.company_id, form.company_id)
        self.assertEqual(line.user_id, form.user_id)
        self.assertEqual(line.subject, "Disinfection visit")
        self.assertEqual(line.status, form.status)
        self.assertEqual(line.start_date, form.start_date)
        self.assertEqual(line.end_date, form.end_date)
        self.assertNotIn("operation_id", self.line_model._fields)
        self.assertFalse(form.operation_id)

    def test_02_ph_fields_live_on_the_form(self):
        """The readings are stored on the form, not on an operation."""
        form = self._form()
        form.write(
            {
                "before_ph": "7.2",
                "after_ph": "6.8",
                "before_cl": "0.8",
                "after_cl": "0.5",
            }
        )

        self.assertEqual(form.before_ph, "7.2")
        self.assertEqual(form.after_cl, "0.5")
        self.assertNotIn("before_ph", self.line_model._fields)
        self.assertNotIn("before_cl", self.line_model._fields)
        self.assertFalse(form.operation_id)

    def test_03_rule_follows_the_form_assignment(self):
        """Leader and assigned person see the lines; outsiders do not."""
        leader = self._user("dis_leader", "field_operation_forms.forms_user")
        technician = self._user("dis_tech", "field_operation_forms.forms_user")
        outsider = self._user("dis_outsider", "field_operation_forms.forms_user")
        employee = self.env["hr.employee"].create(
            {"name": "Disinfect Tech", "user_id": technician.id}
        )

        form = self._form(
            team_leader_id=leader.id, person_ids=[Command.set([employee.id])]
        )
        line = self._line(form)
        other_line = self._line(self._form())

        self.assertIn(line, self.line_model.with_user(leader).search([]))
        self.assertIn(line, self.line_model.with_user(technician).search([]))
        self.assertNotIn(line, self.line_model.with_user(outsider).search([]))
        self.assertNotIn(other_line, self.line_model.with_user(leader).search([]))

    def test_04_mail_action_opens_the_composer(self):
        """The bridge keeps the form e-mail action."""
        form = self._form()
        action = form.action_send_disinfect_mail()

        self.assertEqual(action["res_model"], "mail.compose.message")
        self.assertEqual(action["context"]["default_res_ids"], form.ids)
        template = self.env.ref(
            "field_operation_forms_disinfect.email_field_operation_form_biocidal"
        )
        self.assertEqual(action["context"]["default_template_id"], template.id)

        forms_user = self._user("dis_mailer", "field_operation_forms.forms_user")
        with self.assertRaises(AccessError):
            form.with_user(forms_user).action_send_disinfect_mail()

    def test_05_report_prints_ph_and_cl_readings(self):
        self.partner.lang = "en_US"
        form = self._form()
        form.write(
            {
                "before_ph": "7.21",
                "after_ph": "6.81",
                "before_cl": "0.81",
                "after_cl": "0.51",
            }
        )
        report = self.env.ref(
            "field_operation_forms_disinfect.action_field_disinfect_pdf"
        )

        html, _report_type = self.env["ir.actions.report"]._render_qweb_html(
            report, form.ids
        )
        html = html.decode() if isinstance(html, bytes) else html
        for expected in (
            "Before PH:",
            "After PH:",
            "Before CL:",
            "After CL:",
            "7.21",
            "6.81",
            "0.81",
            "0.51",
        ):
            self.assertIn(expected, html)

    def test_06_deleting_the_form_deletes_the_lines(self):
        form = self._form()
        line = self._line(form)
        form.unlink()
        self.assertFalse(line.exists())

    def test_07_no_operation_is_created(self):
        operation_count = self.env["field.operation"].search_count([])
        form = self._form()
        self._line(form)
        self.assertFalse(form.operation_id)
        self.assertEqual(self.env["field.operation"].search_count([]), operation_count)
