# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import api, fields, models


class FieldOperation(models.Model):
    _inherit = "field.operation"

    sale_id = fields.Many2one("sale.order", "Sales Order", tracking=True)
    sale_line_id = fields.Many2one(
        "sale.order.line",
        "Sales Order Line",
        ondelete="set null",
        copy=False,
        index=True,
        help="Product line the service was created from, when the service comes from a "
        "sale order line. Empty for services created the other way round (service "
        "first, sale order afterwards).",
    )
    sale_count = fields.Integer(compute="_compute_sale_count", string="Sale")

    @api.depends("sale_id")
    def _compute_sale_count(self):
        """``1`` when the service has a sale order, ``0`` otherwise.

        It used to count ``sale.order.field_operation_id``, a field the wizard is the
        only writer of, so the counter stayed at 0 for every service linked the other
        way round (``sale_id``, the link the sale-order flow populates).
        """
        for operation in self:
            operation.sale_count = 1 if operation.sale_id else 0

    def action_view_sale(self):
        """Open the sale order of this service, or close if there is none."""
        self.ensure_one()
        if not self.sale_id:
            return {"type": "ir.actions.act_window_close"}
        return {
            "name": self.sale_id.display_name,
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_id.id,
            "target": "current",
        }
