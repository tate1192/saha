# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64
import re
import urllib.parse
import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError

#: The service report of ``field.operation``; the only model this wizard can
#: render a report for.
SERVICE_REPORT_XMLID = "field_operation.field_operation_action_pdf"
REPORT_MODEL = "field.operation"


class FieldWhatsappMessage(models.TransientModel):
    _name = "field.whatsapp.message"
    _description = "Send WhatsApp Message"

    res_model = fields.Char(string="Related Document Model", required=True)
    res_id = fields.Integer(string="Related Document ID", required=True)
    res_name = fields.Char(string="Record Name", compute="_compute_res_name")
    partner_name = fields.Char(string="Customer", compute="_compute_partner_name")
    contact_name = fields.Char(string="Contact", compute="_compute_contact_name")
    contact_mobile = fields.Char(string="Phone", required=True)
    message = fields.Text(string="Message", required=True, default="")
    template_id = fields.Many2one(
        "field.whatsapp.template",
        string="Message Template",
        help="Select a template to auto-fill the message",
    )
    include_report = fields.Boolean(
        string="Include Service Report PDF",
        default=False,
        help="Attach the field operation PDF report link to the message",
    )

    @api.model
    def _open_action_for(self, res_model, res_id):
        """The act_window that opens this wizard pre-filled for a record.

        The field operation form carries the WhatsApp button; the "how to open
        me" knowledge lives with the wizard so the model only delegates.
        """
        return {
            "type": "ir.actions.act_window",
            "name": _("Send WhatsApp Message"),
            "res_model": self._name,
            "target": "new",
            "view_mode": "form",
            "context": {
                "default_res_model": res_model,
                "default_res_id": res_id,
                "active_model": res_model,
                "active_id": res_id,
            },
        }

    @api.depends("res_model", "res_id")
    def _compute_res_name(self):
        for wizard in self:
            record = wizard._get_source_record()
            wizard.res_name = record.display_name if record else _("Unknown")

    @api.depends("res_model", "res_id")
    def _compute_contact_name(self):
        for wizard in self:
            record = wizard._get_source_record()
            contact = record.contact_id if "contact_id" in record else record
            wizard.contact_name = (
                (contact or record).display_name if record else _("Unknown")
            )

    @api.depends("res_model", "res_id")
    def _compute_partner_name(self):
        for wizard in self:
            record = wizard._get_source_record()
            if record and "partner_id" in record and record.partner_id:
                wizard.partner_name = record.partner_id.name
            elif record:
                wizard.partner_name = record.display_name
            else:
                wizard.partner_name = _("Unknown")

    def _get_source_record(self):
        """Return the record the message is sent from, if it still exists."""
        self.ensure_one()
        if not self.res_model or not self.res_id or self.res_model not in self.env:
            return self.env["field.operation"]
        return self.env[self.res_model].browse(self.res_id).exists()

    @api.onchange("template_id")
    def _onchange_template_id(self):
        for record in self:
            source_record = record._get_source_record()
            if record.template_id and source_record:
                record.message = record.template_id.replace_template_fields(
                    source_record
                )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")
        if not active_model or not active_id:
            return res

        record = self.env[active_model].browse(active_id).exists()
        if not record:
            return res

        # field.operation carries contact_mobile; otherwise take the address of
        # the service, then the partner's phone.
        mobile = ""
        if "contact_mobile" in record and record.contact_mobile:
            mobile = record.contact_mobile
        elif "address_id" in record and record.address_id.phone:
            mobile = record.address_id.phone
        elif "partner_id" in record and record.partner_id.phone:
            mobile = record.partner_id.phone

        res.update(
            {
                "res_model": active_model,
                "res_id": active_id,
                "contact_mobile": mobile,
            }
        )
        return res

    def action_use_template(self):
        self.ensure_one()
        source_record = self._get_source_record()
        if self.template_id and source_record:
            self.message = self.template_id.replace_template_fields(source_record)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _detect_user_device(self):
        """Return the User-Agent of the request, if there is one."""
        user_agent = self.env.context.get("user_agent", "").lower()
        if user_agent:
            return user_agent
        try:
            from odoo.http import request
        except ImportError:  # pragma: no cover - request is always importable
            return ""
        try:
            return request.httprequest.headers.get("User-Agent", "").lower()
        except (AttributeError, RuntimeError):
            # called outside of a request (RPC from a script, cron, tests)
            return ""

    def _phone_country_code(self):
        """Calling code (digits) of the country the message is for, if known.

        Same order the wizard resolves the phone with: an operation carries a
        partner, a service form a customer; the contact and the service address
        add theirs. Only then the company's own country, which is a guess for a
        foreign customer.
        """
        self.ensure_one()
        source_record = self._get_source_record()
        if source_record:
            for field_name in (
                "partner_id",
                "customer_id",
                "contact_id",
                "address_id",
            ):
                if field_name in source_record:
                    country = source_record[field_name].country_id
                    if country:
                        return str(country.phone_code or "")
        company_country = self._get_company().country_id or self.env.company.country_id
        return str(company_country.phone_code or "")

    def _clean_phone_number(self, phone):
        """Return the number in the international form WhatsApp expects.

        The ``phone`` parameter of the deep link wants the country code and no
        '+'. A Turkish number stored as "0530 515 81 42" - the format of roughly
        half the operations in the live database - used to be sent as
        "05305158142", and WhatsApp answers with an invalid-number screen.
        """
        digits = re.sub(r"\D", "", phone or "")
        if not digits:
            return ""
        if digits.startswith("00"):
            # 0090... carries its own country code
            return digits[2:]
        if digits.startswith("0"):
            country_code = self._phone_country_code()
            local = digits.lstrip("0")
            if not country_code or not local:
                # Unknown country: prefixing a code would be a guess, keep the
                # number exactly as it was stored.
                return digits
            return f"{country_code}{local}"
        return digits

    def _generate_report_link(self):
        """Render the service report and return a link the customer can open.

        The attachment is created WITHOUT ``public`` (a public attachment is
        readable by anybody who guesses its sequential id) but with an
        ``access_token``, which is what ``/web/content`` accepts in place of
        access rights: the recipient of the WhatsApp message is not logged in.
        """
        self.ensure_one()
        if self.res_model != REPORT_MODEL:
            raise UserError(
                _(
                    "The service report only exists for %(model)s records; "
                    "%(current)s has none.",
                    model=REPORT_MODEL,
                    current=self.res_model,
                )
            )

        report = self.env.ref(SERVICE_REPORT_XMLID, raise_if_not_found=False)
        if not report:
            raise UserError(
                _("Report %s is not installed; the link cannot be generated.")
                % SERVICE_REPORT_XMLID
            )

        try:
            pdf_content, _content_type = self.env["ir.actions.report"]._render_qweb_pdf(
                report.report_name, [self.res_id]
            )
        except (UserError, ValueError) as error:
            # UserError covers wkhtmltopdf's own refusals, ValueError a report ref
            # that no longer resolves; anything else is a bug and must not be
            # hidden behind a friendly message.
            raise UserError(
                _("Report generation failed: %(error)s") % {"error": error}
            ) from error

        attachment = self.env["ir.attachment"].create(
            {
                "name": f"Service_Report_{self.res_name}.pdf",
                "type": "binary",
                "datas": base64.b64encode(pdf_content),
                "res_model": self.res_model,
                "res_id": self.res_id,
                "access_token": str(uuid.uuid4()),
            }
        )
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        return (
            f"{base_url}/web/content/{attachment.id}"
            f"?access_token={attachment.access_token}&download=true"
        )

    def action_send_whatsapp(self):
        """Open WhatsApp on the user's device with the message pre-filled.

        The message is NOT sent by Odoo: the browser opens the WhatsApp window
        and the user presses send, which is why the log and the chatter note say
        the window was opened, not that the message was delivered.
        """
        self.ensure_one()
        if not self.contact_mobile or not self.contact_mobile.strip():
            raise UserError(_("Phone number is missing."))
        if not self.message or not self.message.strip():
            raise UserError(_("Message cannot be empty."))

        clean_phone = self._clean_phone_number(self.contact_mobile.strip())
        if not clean_phone:
            raise UserError(_("Invalid phone number format."))

        final_message = self.message.strip()
        if self.include_report:
            final_message += f"\n\n📄 *Service Report:* {self._generate_report_link()}"

        encoded_message = urllib.parse.quote(final_message)
        user_agent = self._detect_user_device()
        if any(
            device in user_agent for device in ("android", "iphone", "ipad", "mobile")
        ):
            whatsapp_url = (
                f"https://api.whatsapp.com/send?phone={clean_phone}"
                f"&text={encoded_message}"
            )
        else:
            whatsapp_url = (
                f"https://web.whatsapp.com/send?phone={clean_phone}"
                f"&text={encoded_message}"
            )

        self.env["field.whatsapp.log"].create(
            {
                "template_id": self.template_id.id,
                "res_model": self.res_model,
                "res_id": self.res_id,
                "contact_mobile": clean_phone,
                "message_sent": final_message,
                "company_id": self._get_company().id,
            }
        )

        if self.template_id:
            # counter only: the template itself stays read-only for field users
            self.template_id.sudo().usage_count += 1

        source_record = self._get_source_record()
        # message_post is a method, so it must be probed with hasattr: `in` on a
        # recordset only answers for FIELD names.
        if hasattr(source_record, "message_post"):
            source_record.message_post(
                body=_("WhatsApp opened for %(phone)s")
                % {"phone": self.contact_mobile.strip()},
            )

        return {
            "type": "ir.actions.act_url",
            "url": whatsapp_url,
            "target": "new",
        }

    def _get_company(self):
        """Company of the source record, falling back to the user's company."""
        self.ensure_one()
        source_record = self._get_source_record()
        if source_record and "company_id" in source_record and source_record.company_id:
            return source_record.company_id
        return self.env.company
