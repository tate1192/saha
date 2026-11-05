"""Tests for the field operation forms.

Covers what the review found broken: the link between an operation and its form
(drift, duplicate creation, silent closing), the field-user visibility rule, the
server-side rights behind the buttons, and the portal page and signature routes.
"""

import base64
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import TransactionCase


@tagged("field_operation_forms", "post_install", "-at_install")
class TestFieldOperationForms(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Form Customer"})
        cls.service_type = cls.env["field.operation.type"].search([], limit=1)
        cls.team = cls.env["field.operation.team"].create({"name": "Form Team"})
        cls.forms_model = cls.env["field.operation.forms"]
        cls.operation_model = cls.env["field.operation"]

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

    def _operation(self, subject="Form Job", partner=None, team=True):
        return self.operation_model.create(
            {
                "subject": subject,
                "partner_id": (partner or self.partner).id,
                "service_type_id": self.service_type.id,
                "team_id": self.team.id if team else False,
                "status": "done",
            }
        )

    def _form(self, **values):
        values.setdefault("customer_id", self.partner.id)
        values.setdefault("service_type_id", self.service_type.id)
        return self.forms_model.create(values)

    def test_01_operation_and_form_links_stay_in_sync(self):
        """The operation's form follows the form side, in both directions."""
        operation = self._operation()
        form = self._form(operation_id=operation.id)

        self.assertEqual(operation.forms_id, form)
        self.assertEqual(operation.forms_count, 1)
        self.assertEqual(form.operation_count, 1)

        # pointing the form at another operation moves the link, without duplicating it
        other = self._operation("Second job")
        form.operation_id = other
        self.assertFalse(operation.forms_id)
        self.assertEqual(operation.forms_count, 0)
        self.assertEqual(other.forms_id, form)

        # detaching the form empties both sides
        form.operation_id = False
        self.assertFalse(other.forms_id)
        self.assertEqual(form.operation_count, 0)

    def test_02_create_forms_refuses_a_second_form(self):
        """The button creates one form, and says so instead of piling up orphans."""
        operation = self._operation()
        form = operation.action_create_forms()
        self.assertEqual(form.operation_id, operation)
        self.assertEqual(operation.forms_id, form)

        with self.assertRaises(UserError):
            operation.action_create_forms()
        self.assertEqual(
            self.forms_model.search_count([("operation_id", "=", operation.id)]), 1
        )

    def test_03_create_forms_requires_a_team_and_a_right(self):
        """No team, or no group: the form is not created."""
        without_team = self._operation("No team", team=False)
        with self.assertRaises(UserError):
            without_team.action_create_forms()

        outsider = self._user("forms_outsider")
        with self.assertRaises(AccessError):
            self._operation("No right").with_user(outsider).action_create_forms()

    def test_04_field_user_sees_his_work_and_loses_it_when_closed(self):
        """Leader or assigned person sees the open form; closed forms leave the list."""
        leader = self._user("forms_leader", "field_operation_forms.forms_user")
        technician = self._user("forms_tech", "field_operation_forms.forms_user")
        employee = self.env["hr.employee"].create(
            {"name": "Technician", "user_id": technician.id}
        )

        open_form = self._form(
            subject="Assigned to the technician",
            status="new",
            team_leader_id=leader.id,
            person_ids=[Command.set([employee.id])],
        )
        done_form = self._form(
            subject="Closed", status="done", team_leader_id=leader.id
        )

        # the leader sees his form, the assigned technician sees the same one
        self.assertIn(open_form, self.forms_model.with_user(leader).search([]))
        self.assertIn(open_form, self.forms_model.with_user(technician).search([]))
        # the assigned-person search filter now matches what the rule allows
        self.assertEqual(
            self.forms_model.with_user(technician).search_count(
                [("person_ids.user_id", "=", technician.id)]
            ),
            1,
        )
        # a closed form is out of the field user's list. exists() ignores record rules,
        # so searching is the honest check here
        self.assertNotIn(done_form, self.forms_model.with_user(leader).search([]))
        self.assertEqual(
            self.forms_model.with_user(leader).search_count(
                [("id", "=", done_form.id)]
            ),
            0,
        )

    def test_05_status_actions_need_the_right_group(self):
        """The button groups are enforced on the server too."""
        user = self._user("forms_user_only", "field_operation_forms.forms_user")
        form = self._form(team_leader_id=user.id)

        self.assertTrue(form.with_user(user).action_completed())
        self.assertEqual(form.status, "completed")
        self.assertTrue(form.with_user(user).action_draft())

        with self.assertRaises(AccessError):
            form.with_user(user).action_done()
        with self.assertRaises(AccessError):
            form.with_user(user).action_cancel()

    def test_06_action_done_pushes_the_outcome_and_needs_a_link(self):
        """Closing writes the outcome onto the operation, or explains why it cannot."""
        operation = self._operation()
        form = self.forms_model.create(
            {
                "subject": "Closable",
                "customer_id": self.partner.id,
                "service_type_id": self.service_type.id,
                "operation_id": operation.id,
                "customer_signed_by": "Customer Name",
                "staff_signed_by": "Staff Name",
                "solution": "<p>Fixed</p>",
                "end_date": fields.Datetime.now(),
            }
        )
        form.customer_signature = base64.b64encode(b"customer").decode()
        self.assertTrue(form.action_done())

        self.assertEqual(form.status, "done")
        self.assertEqual(operation.signed_by, "Customer Name")
        self.assertEqual(operation.staff_signed_by, "Staff Name")
        self.assertEqual(operation.solution, "<p>Fixed</p>")
        self.assertTrue(operation.form_signature)

        orphan = self._form(status="completed")
        with self.assertRaises(UserError):
            orphan.action_done()
        self.assertEqual(orphan.status, "completed")

    def test_07_signing_stamps_a_real_moment(self):
        """The signature timestamp is a datetime, not a date coerced to midnight.

        ``signed`` is derived from the signature images, so typing the customer name
        on its own must not flag the form as signed.
        """
        form = self._form()
        before = fields.Datetime.now() - timedelta(minutes=1)
        form.customer_signed_by = "Signed By"
        form._signed_on()

        self.assertGreaterEqual(form.signed_on, before)
        self.assertLessEqual(
            form.signed_on, fields.Datetime.now() + timedelta(minutes=1)
        )
        self.assertFalse(form.signed, "a name without a signature image is not signed")

    def test_08_search_view_filters_are_valid(self):
        """Every filter_domain of the search view must name a real field.

        The Customer box used to carry ``[('partner_id', 'child_of', self)]`` while the
        model has no ``partner_id``: searching crashed with a ValueError.
        """
        search_view = self.env.ref(
            "field_operation_forms.field_operation_forms_search_view"
        )
        self.assertNotIn("partner_id", search_view.arch)

        found_form = self._form()
        found = self.forms_model.search([("customer_id", "child_of", self.partner.id)])
        self.assertIn(found_form, found)

    def test_09_portal_is_read_only_and_signature_payload_is_checked(self):
        """The portal reads; the signature writes are whitelisted and validated."""
        portal_group = self.env.ref("base.group_portal")
        portal_user = self.env["res.users"].create(
            {
                "name": "Portal Customer",
                "login": "forms_portal_customer",
                "group_ids": [Command.set([portal_group.id])],
            }
        )
        form = self._form(customer_id=portal_user.partner_id.id, status="new")

        # the portal cannot write the form itself
        with self.assertRaises(AccessError):
            form.with_user(portal_user).write(
                {"status": "done", "solution": "<p>x</p>"}
            )
        self.assertEqual(form.status, "new")

        # ...but the signature helpers do, with a whitelist and a validated payload,
        # even when the caller is the portal user (this is the controller path)
        signature = base64.b64encode(b"drawn-signature").decode()
        form.with_user(portal_user)._portal_sign_customer("Customer Name", signature)
        self.assertEqual(form.customer_signed_by, "Customer Name")
        form.with_user(portal_user)._portal_sign_staff("Staff Name", signature)
        self.assertTrue(form.signed)
        self.assertEqual(form.status, "new", "signing must not close the form")

        with self.assertRaises(UserError):
            form._portal_sign_customer("Customer Name", "not base64 !")
        with self.assertRaises(UserError):
            form._portal_sign_customer("Customer Name", False)

    def test_10_a_form_created_from_the_client_gets_its_reference(self):
        """The web client sends the "/" field default back with the create payload.

        The sequence used to run only when ``name`` was missing from the values, so
        a form created from the menu stayed at "/" without a FOF- number.
        """
        default_name = self.forms_model.default_get(["name"])["name"]
        self.assertEqual(default_name, "/")
        form = self._form(name=default_name)
        self.assertRegex(form.name, r"^FOF-\d+$")

    def test_11_signed_is_derived_from_both_signatures(self):
        """``signed`` follows the signature images instead of a hand-written flag."""
        form = self._form()
        self.assertFalse(form.signed)

        form.customer_signature = base64.b64encode(b"customer").decode()
        self.assertFalse(form.signed, "one signature does not make a signed form")

        form.staff_signature = base64.b64encode(b"staff").decode()
        self.assertTrue(form.signed)

        form.staff_signature = False
        self.assertFalse(form.signed)

        # the flag cannot be forced any more: it is recomputed from the signatures
        form.write({"signed": True})
        form.invalidate_recordset(["signed"])
        self.assertFalse(form.signed)

    def test_12_contact_mobile_reads_through_without_writing_back(self):
        """The contact phone stays the master record: the form copy only follows it."""
        partner = self.env["res.partner"].create(
            {"name": "Phone Owner", "phone": "111222333"}
        )
        form = self._form(contact_id=partner.id)
        self.assertEqual(form.contact_mobile, "111222333")
        self.assertTrue(
            self.forms_model._fields["contact_mobile"].readonly,
            "a writable related field would overwrite res.partner.phone",
        )

        partner.phone = "444555666"
        form.invalidate_recordset(["contact_mobile"])
        self.assertEqual(form.contact_mobile, "444555666")

    @patch(
        "odoo.addons.base.models.ir_actions_report.IrActionsReport._run_wkhtmltopdf",
        return_value=b"%PDF-1.4\n% mocked by the test\n",
    )
    def test_13_the_service_form_pdf_is_wired_to_the_model(self, run_wkhtmltopdf):
        """The report reaches the PDF pipeline and travels with the e-mail template.

        The wkhtmltopdf binary is mocked: a real run fetches the report assets over
        HTTP from inside the open test transaction and hangs the whole suite on a
        headless machine (the HTML content is covered by the rendering tests).
        """
        form = self._form(subject="Printable")
        report = self.env.ref("field_operation_forms.action_service_form_pdf")
        self.assertEqual(report.model, "field.operation.forms")
        self.assertEqual(report.report_type, "qweb-pdf")

        pdf, report_type = (
            self.env["ir.actions.report"]
            .with_context(force_report_rendering=True)
            ._render_qweb_pdf(report, [form.id])
        )
        self.assertEqual(report_type, "pdf")
        self.assertTrue(
            pdf.startswith(b"%PDF"), "the report did not reach the PDF pipeline"
        )
        run_wkhtmltopdf.assert_called_once()

        template = self.env.ref(
            "field_operation_forms.field_operation_forms_email_template"
        )
        self.assertIn(
            report,
            template.report_template_ids,
            "the e-mail template must carry the form PDF as an attachment",
        )

    def test_14_create_form_button_is_offered_only_once(self):
        """The button hides as soon as the operation has a form, or is closed.

        It used to be ``status in ('draft','done','cancel') and forms_count == 0``,
        which left it visible on every operation that already had a form — clicking
        it raised "This operation already has a form.".
        """
        condition = "forms_count != 0 or status in ('draft','done','cancel')"
        arch = self.env.ref(
            "field_operation_forms.field_operation_forms_inh_view"
        ).arch_db
        self.assertIn(condition, arch)
        self.assertNotIn(
            "status in ('draft','done','cancel') and forms_count == 0",
            arch,
            "the old condition is back: it shows the button on a form that exists",
        )


@tagged("field_operation_forms", "post_install", "-at_install")
class TestFieldOperationFormsPortal(HttpCase):
    def test_portal_page_and_signature_route(self):
        """The customer page renders and the signature route stores the signature."""
        env = self.env
        service_type = env["field.operation.type"].search([], limit=1)
        portal_group = env.ref("base.group_portal")
        portal_user = env["res.users"].create(
            {
                "name": "Portal Signer",
                "login": "forms_portal_signer",
                "password": "PortalSigner123",
                "group_ids": [Command.set([portal_group.id])],
            }
        )
        form = env["field.operation.forms"].create(
            {
                "subject": "Portal Form",
                "customer_id": portal_user.partner_id.id,
                "service_type_id": service_type.id,
                "status": "new",
            }
        )
        self.authenticate("forms_portal_signer", "PortalSigner123")

        page = self.url_open(
            f"/my/operation_forms_detail/{form.id}?access_token={form.access_token}"
        )
        self.assertEqual(page.status_code, 200)
        self.assertIn(form.subject, page.text)
        # both shortcuts are offered while the signatures are missing
        self.assertIn('data-bs-target="#modalaccept"', page.text)
        self.assertIn('data-bs-target="#smodalaccept"', page.text)

        listing = self.url_open("/my/operation_forms")
        self.assertEqual(listing.status_code, 200)

        signature = base64.b64encode(b"portal-drawn-signature").decode()
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"name": "Portal Signer", "signature": signature},
        }
        response = self.url_open(
            f"/my/operation_forms_detail/{form.id}/form/customer_sign/portal",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["result"]["force_refresh"])
        form.invalidate_recordset()
        self.assertEqual(form.customer_signed_by, "Portal Signer")

        # the customer shortcut is gone now (the modal is built on the same condition,
        # so a signed form can no longer open an empty dialog), the staff one stays
        signed_page = self.url_open(
            f"/my/operation_forms_detail/{form.id}?access_token={form.access_token}"
        )
        self.assertEqual(signed_page.status_code, 200)
        self.assertNotIn('data-bs-target="#modalaccept"', signed_page.text)
        self.assertIn('data-bs-target="#smodalaccept"', signed_page.text)
