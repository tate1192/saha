from odoo import fields, models


class FieldDisinfectProduct(models.Model):
    _name = "field.disinfect.product"
    _description = "Field Disinfect Product"
    _order = "sequence, name"

    name = fields.Char(string="Name")
    sequence = fields.Integer(string="Sequence", default=1)
    active = fields.Boolean(string="Active", default=True)
    priority = fields.Selection(
        [("0", "Low"), ("1", "High")], default="0", index=True, string="Priority"
    )
    type = fields.Selection(
        [("dispenser", "Dispenser"), ("tank", "Tank")], string="Type"
    )
