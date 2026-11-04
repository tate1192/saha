# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import api, fields, models

GREASE_DUCT_SERVICE = "grease_duct"


class FieldOperationForms(models.Model):
    _inherit = "field.operation.forms"

    grease_duct_ids = fields.One2many(
        "field.operation.grease.duct.line",
        "forms_id",
        string="Grease Duct Measurements",
    )
    grease_duct_no = fields.Char(
        string="Certificate No",
        copy=False,
        readonly=True,
        index=True,
        help=(
            "Assigned from the field.grease sequence when the service type is "
            "grease duct."
        ),
    )
    grease_access_status = fields.Selection(
        [
            ("full", "Full Access"),
            ("partial", "Partial Access"),
            ("none", "No Access"),
        ],
        string="Duct Access",
    )
    grease_access_note = fields.Text(string="Access Note")
    grease_next_cleaning_date = fields.Date(string="Next Cleaning")
    grease_total_length = fields.Float(
        string="Total Duct Length",
        compute="_compute_grease_total_length",
        digits=(16, 2),
    )

    @api.depends("grease_duct_ids.length")
    def _compute_grease_total_length(self):
        for form in self:
            form.grease_total_length = sum(form.grease_duct_ids.mapped("length"))

    @api.model
    def _is_grease_duct_service(self, service_type_id):
        if not service_type_id:
            return False
        service_type = self.env["field.operation.type"].browse(service_type_id)
        return service_type.type == GREASE_DUCT_SERVICE

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self._is_grease_duct_service(vals.get("service_type_id")):
                vals["grease_duct_no"] = (
                    self.env["ir.sequence"].next_by_code("field.grease") or "/"
                )
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if "service_type_id" in vals:
            forms = self.filtered(
                lambda form: form.service_type == GREASE_DUCT_SERVICE
                and not form.grease_duct_no
            )
            for form in forms:
                form.grease_duct_no = (
                    self.env["ir.sequence"].next_by_code("field.grease") or "/"
                )
        return res
