# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import fields, models


class FieldOperationGreaseDuctLine(models.Model):
    _name = "field.operation.grease.duct.line"
    _description = "Grease Duct Measurement Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    forms_id = fields.Many2one(
        "field.operation.forms",
        string="Operation Form",
        required=True,
        ondelete="cascade",
        index=True,
    )
    duct_type = fields.Selection(
        [
            ("hood", "Hood"),
            ("vertical", "Vertical Duct"),
            ("horizontal", "Horizontal Duct"),
            ("filter", "Filter"),
            ("other", "Other"),
        ],
        string="Type",
        required=True,
        default="hood",
    )
    quantity = fields.Integer(string="Qty", default=1)
    length = fields.Float(
        string="Length",
        digits=(16, 2),
        help="Duct length in meters, printed as MT on the certificate.",
    )
    note = fields.Char()
