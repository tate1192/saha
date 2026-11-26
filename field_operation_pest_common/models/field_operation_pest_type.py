from random import randint

from odoo import fields, models

_name_uniq = models.Constraint(
    "unique (name)",
    "Pest name already exists!",
)


class FieldOperationPestType(models.Model):
    _name = "field.operation.pest.type"
    _description = "Field Operation Pest Type"

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string="Name", required=True)
    sequence = fields.Integer(string="Sequence", default=1)
    color = fields.Integer(string="Color")
