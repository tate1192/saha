# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import urllib.parse

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

MOBILE_UA = {"user_agent": "Mozilla/5.0 (Linux; Android 14)"}
DESKTOP_UA = {"user_agent": "Mozilla/5.0 (Windows NT 10.0)"}


@tagged("post_install", "-at_install")
class TestFieldWhatsappMessage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ``contact_mobile`` on the operation is a read-only mirror of
        # ``contact_id.phone``: the number has to be set on the contact.
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Message Customer",
                "phone": "+90 (533) 444-55-66",
                "country_id": cls.env.ref("base.tr").id,
            }
        )
        cls.address_partner = cls.env["res.partner"].create(
            {
                "name": "Message Site",
                "phone": "0212 111 22 33",
                "country_id": cls.env.ref("base.tr").id,
            }
        )
        cls.operation = cls.env["field.operation"].create(
            {
                "name": "/",
                "subject": "Message Probe",
                "partner_id": cls.partner.id,
                "contact_id": cls.partner.id,
                "start_date": "2026-11-04 09:00:00",
            }
        )
        cls.wizard = cls.env["field.whatsapp.message"]

    def _wizard(self, **overrides):
        values = {"res_model": "field.operation", "res_id": self.operation.id}
        values.update(overrides)
        return self.wizard.with_context(
            active_model="field.operation", active_id=self.operation.id, **MOBILE_UA
        ).create(values)

    def _logs(self, operation=None):
        operation = operation or self.operation
        return self.env["field.whatsapp.log"].search(
            [("res_id", "=", operation.id), ("res_model", "=", "field.operation")]
        )

    # ------------------------------------------------------------------
    # Recipient phone
    # ------------------------------------------------------------------
    def test_the_default_get_prefers_the_operation_contact(self):
        wizard = self._wizard()
        self.assertEqual(wizard.contact_mobile, "+90 (533) 444-55-66")
        self.assertEqual(wizard.res_name, self.operation.display_name)
        self.assertEqual(wizard.partner_name, "Message Customer")

    def test_the_phone_falls_back_to_the_service_address(self):
        operation = self.env["field.operation"].create(
            {
                "name": "/",
                "subject": "Fallback Probe",
                "partner_id": self.partner.id,
                "address_id": self.address_partner.id,
                "contact_id": self.address_partner.id,
                "start_date": "2026-11-04 09:00:00",
            }
        )
        wizard = self.wizard.with_context(
            active_model="field.operation", active_id=operation.id
        ).create({"res_model": "field.operation", "res_id": operation.id})
        self.assertEqual(wizard.contact_mobile, "0212 111 22 33")

    def test_the_phone_falls_back_to_the_partner(self):
        """No contact and no service address: the customer's own phone is used."""
        operation = self.env["field.operation"].create(
            {
                "name": "/",
                "subject": "Partner Fallback Probe",
                "partner_id": self.partner.id,
                "start_date": "2026-11-04 09:00:00",
            }
        )
        operation.write({"contact_id": False, "address_id": False})
        wizard = self.wizard.with_context(
            active_model="field.operation", active_id=operation.id
        ).create({"res_model": "field.operation", "res_id": operation.id})
        self.assertEqual(wizard.contact_mobile, self.partner.phone)

    def test_the_country_comes_from_the_record(self):
        """The calling code follows the record's own country, not the company's.

        Measured before the fix: a German customer's "030 12345678" went out with
        the Turkish code because only ``partner_id`` was consulted and the
        company country was the fallback.
        """
        german = self.env["res.partner"].create(
            {
                "name": "German Customer",
                "phone": "030 12345678",
                "country_id": self.env.ref("base.de").id,
                "is_company": True,
            }
        )
        operation = self.env["field.operation"].create(
            {
                "name": "/",
                "subject": "German Phone Probe",
                "partner_id": german.id,
                "contact_id": german.id,
                "start_date": "2026-11-04 09:00:00",
            }
        )
        wizard = self.wizard.with_context(
            active_model="field.operation", active_id=operation.id
        ).create(
            {
                "res_model": "field.operation",
                "res_id": operation.id,
                "message": "Almanya",
            }
        )
        self.assertIn(
            "phone=493012345678",
            urllib.parse.unquote(wizard.action_send_whatsapp()["url"]),
        )

    def test_a_local_number_gets_the_country_code(self):
        """A number stored as "0530 ..." must reach WhatsApp as 90530....

        Half of the operations in the live database carry the local format; the
        old cleaning sent `phone=0530...` and WhatsApp answered "invalid number".
        """
        local = self.env["res.partner"].create(
            {
                "name": "Local Number Customer",
                "phone": "0530 515 81 42",
                "country_id": self.env.ref("base.tr").id,
            }
        )
        operation = self.env["field.operation"].create(
            {
                "name": "/",
                "subject": "Local Phone Probe",
                "partner_id": local.id,
                "contact_id": local.id,
                "start_date": "2026-11-04 09:00:00",
            }
        )
        wizard = self.wizard.with_context(
            active_model="field.operation", active_id=operation.id
        ).create(
            {
                "res_model": "field.operation",
                "res_id": operation.id,
                "message": "Yerel numara",
            }
        )
        self.assertIn(
            "phone=905305158142",
            urllib.parse.unquote(wizard.action_send_whatsapp()["url"]),
        )
        self.assertEqual(self._logs(operation).contact_mobile, "905305158142")

    def test_a_number_with_its_own_code_is_left_alone(self):
        for phone, expected in (
            ("+90 532 495 80 87", "905324958087"),
            ("0090 532 495 80 87", "905324958087"),
            ("905324958087", "905324958087"),
        ):
            partner = self.env["res.partner"].create(
                {
                    "name": f"Intl {expected}",
                    "phone": phone,
                    "country_id": self.env.ref("base.tr").id,
                }
            )
            operation = self.env["field.operation"].create(
                {
                    "name": "/",
                    "subject": "Intl Phone Probe",
                    "partner_id": partner.id,
                    "contact_id": partner.id,
                    "start_date": "2026-11-04 09:00:00",
                }
            )
            wizard = self.wizard.with_context(
                active_model="field.operation", active_id=operation.id
            ).create(
                {
                    "res_model": "field.operation",
                    "res_id": operation.id,
                    "message": "Intl",
                }
            )
            self.assertIn(
                f"phone={expected}",
                urllib.parse.unquote(wizard.action_send_whatsapp()["url"]),
            )

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def test_the_message_is_opened_in_the_mobile_and_desktop_urls(self):
        mobile_url = self._wizard(message="Merhaba").action_send_whatsapp()["url"]
        self.assertTrue(
            mobile_url.startswith("https://api.whatsapp.com/send?phone=905334445566")
        )
        desktop = self.wizard.with_context(
            active_model="field.operation",
            active_id=self.operation.id,
            **DESKTOP_UA,
        ).create(
            {
                "res_model": "field.operation",
                "res_id": self.operation.id,
                "message": "Merhaba",
            }
        )
        desktop_url = desktop.action_send_whatsapp()["url"]
        self.assertTrue(
            desktop_url.startswith("https://web.whatsapp.com/send?phone=905334445566")
        )

    def test_the_log_keeps_the_cleaned_number_and_the_message(self):
        wizard = self._wizard(message="Temiz numara")
        self.assertEqual(wizard.action_send_whatsapp()["type"], "ir.actions.act_url")
        log = self._logs()
        self.assertEqual(len(log), 1)
        self.assertEqual(log.contact_mobile, "905334445566")
        self.assertEqual(log.message_sent, "Temiz numara")
        self.assertEqual(log.company_id, self.operation.company_id)
        self.assertEqual(log.template_id, self.env["field.whatsapp.template"])

    def test_the_chatter_note_says_the_window_was_opened(self):
        """Odoo cannot know the message was delivered: it only opens WhatsApp."""
        wizard = self.wizard.with_context(
            active_model="field.operation",
            active_id=self.operation.id,
            lang="en_US",
            **MOBILE_UA,
        ).create(
            {
                "res_model": "field.operation",
                "res_id": self.operation.id,
                "message": "Chatter kontrolu",
            }
        )
        wizard.action_send_whatsapp()
        messages = self.env["mail.message"].search(
            [("model", "=", "field.operation"), ("res_id", "=", self.operation.id)]
        )
        self.assertTrue(
            any("WhatsApp opened" in message.body for message in messages),
            "no note says the WhatsApp window was opened: %s"
            % [message.body for message in messages],
        )

    def test_the_template_counter_is_incremented(self):
        template = self.env["field.whatsapp.template"].search(
            [("name", "=", "Welcome Message")], limit=1
        )
        before = template.usage_count
        wizard = self._wizard(message="Sablon sayaci")
        wizard.template_id = template
        wizard.action_send_whatsapp()
        self.assertEqual(template.usage_count, before + 1)

    def test_an_empty_phone_or_message_is_refused(self):
        with self.assertRaises(UserError):
            self._wizard(message="   ").action_send_whatsapp()
        wizard = self._wizard(message="telefon yok")
        wizard.contact_mobile = "   "
        with self.assertRaises(UserError):
            wizard.action_send_whatsapp()

    # ------------------------------------------------------------------
    # Service report link
    # ------------------------------------------------------------------
    def test_the_report_link_points_to_the_service_report_with_a_token(self):
        """The customer is not logged in: /web/content needs an access token.

        The report name used to be wrong ('field_operation.field_operation_pdf'
        does not exist in this suite), so the checkbox raised a UserError.
        """
        wizard = self._wizard(message="Rapor linki", include_report=True)
        url = urllib.parse.unquote(wizard.action_send_whatsapp()["url"])
        self.assertIn("/web/content/", url)
        self.assertIn("access_token=", url)

        log = self._logs()
        self.assertIn("Service Report:", log.message_sent)
        attachment = self.env["ir.attachment"].search(
            [("res_model", "=", "field.operation"), ("res_id", "=", self.operation.id)],
            limit=1,
        )
        self.assertTrue(attachment, "the report was rendered and attached")
        self.assertFalse(attachment.public, "a public attachment is readable by id")
        self.assertTrue(attachment.access_token)
        self.assertIn(attachment.access_token, url)
        self.assertGreater(len(attachment.datas), 1000)

    def test_the_report_link_is_refused_for_another_model(self):
        partner_wizard = self.wizard.with_context(
            active_model="res.partner", active_id=self.partner.id
        ).create(
            {
                "res_model": "res.partner",
                "res_id": self.partner.id,
                "contact_mobile": "905000000000",
                "message": "Rapor yok",
                "include_report": True,
            }
        )
        with self.assertRaises(UserError) as error:
            partner_wizard.action_send_whatsapp()
        self.assertIn("field.operation", str(error.exception))

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------
    def test_the_log_is_scoped_to_the_company_of_the_record(self):
        """A record rule, so it must be asserted with a non-superuser.

        TransactionCase runs as SUPERUSER, whose env bypasses ir.rule.
        """
        other_company = self.env["res.company"].create({"name": "Other Company"})
        self._wizard(message="A sirketi").action_send_whatsapp()
        self.env["field.whatsapp.log"].create(
            {
                "res_model": "field.operation",
                "res_id": self.operation.id,
                "contact_mobile": "905000000000",
                "message_sent": "B sirketi",
                "company_id": other_company.id,
            }
        )
        reader = self.env["res.users"].create(
            {
                "name": "WA Log Reader",
                "login": "wa_log_reader",
                "company_id": self.operation.company_id.id,
                "company_ids": [
                    Command.set([self.operation.company_id.id, other_company.id])
                ],
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("field_operation.service_group_user").id,
                        ]
                    )
                ],
            }
        )
        scoped = (
            self.env["field.whatsapp.log"]
            .with_user(reader)
            .with_context(allowed_company_ids=[self.operation.company_id.id])
        )
        self.assertEqual(len(scoped.search([("res_id", "=", self.operation.id)])), 1)
        self.assertNotIn(other_company, scoped.search([]).company_id)

    def test_the_log_unlink_is_manager_only(self):
        access = self.env["ir.model.access"].search(
            [("model_id.model", "=", "field.whatsapp.log")]
        )
        self.assertEqual(len(access), 2)
        by_group = {acl.group_id: acl for acl in access}
        user = by_group[self.env.ref("field_operation.service_group_user")]
        manager = by_group[self.env.ref("field_operation.service_group_manager")]
        self.assertFalse(user.perm_unlink)
        self.assertTrue(user.perm_read and user.perm_write and user.perm_create)
        self.assertTrue(manager.perm_unlink)

    def test_the_templates_are_read_only_for_field_users(self):
        """Templates are content: field users read them, managers maintain them.

        The wizard comment claimed read-only while the ACL granted 1/1/1/1, so a
        field user could delete the six shipped templates.
        """
        access = self.env["ir.model.access"].search(
            [("model_id.model", "=", "field.whatsapp.template")]
        )
        self.assertEqual(len(access), 2)
        by_group = {acl.group_id: acl for acl in access}
        user = by_group[self.env.ref("field_operation.service_group_user")]
        manager = by_group[self.env.ref("field_operation.service_group_manager")]
        self.assertEqual(
            (user.perm_read, user.perm_write, user.perm_create, user.perm_unlink),
            (True, False, False, False),
        )
        self.assertTrue(
            manager.perm_read
            and manager.perm_write
            and manager.perm_create
            and manager.perm_unlink
        )

    def test_the_report_checkbox_is_hidden_outside_the_operation(self):
        """The forms wizard must not offer a report it cannot render."""
        arch = self.env.ref(
            "field_operation_whatsapp.view_field_whatsapp_message_form"
        ).arch
        self.assertIn("res_model != 'field.operation'", arch)

    def test_the_operation_button_is_not_wrapped_in_a_second_button_box(self):
        """`position='inside'` must add the button, not another button box."""
        form = self.env.ref("field_operation.view_field_operation_form")
        arch = str(
            self.env["field.operation"].get_views([(form.id, "form")])["views"]["form"][
                "arch"
            ]
        )
        self.assertEqual(arch.count('name="button_box"'), 1)
        self.assertEqual(arch.count("action_message_send"), 1)
        # the resolved arch drops `groups`, so the gate is read from the view itself
        view_arch = self.env.ref(
            "field_operation_whatsapp.whatsapp_field_operation_form_view"
        ).arch
        self.assertIn("field_operation.service_group_user", view_arch)
