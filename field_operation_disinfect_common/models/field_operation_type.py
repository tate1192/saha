from odoo import fields, models


class FieldOperationType(models.Model):
    _inherit = "field.operation.type"

    type = fields.Selection(
        selection_add=[
            ("disinfect", "Disinfect"),
        ],
    )
