# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FieldOperation(models.Model):
    _inherit = "field.operation"

    # Stock Lines
    stock_line_ids = fields.One2many(
        "field.operation.stock.line",
        "operation_id",
        string="Stock Consumption Lines",
    )
    stock_line_count = fields.Integer(
        string="Stock Lines",
        compute="_compute_stock_line_count",
    )
    # Costs are office data; the worker role reads the operation without them.
    total_stock_cost = fields.Monetary(
        string="Service Stock Cost",
        compute="_compute_stock_costs",
        currency_field="currency_id",
        store=True,
        groups="field_operation.service_group_user",
    )
    total_warranty_cost = fields.Monetary(
        string="Warranty Stock Cost",
        compute="_compute_stock_costs",
        currency_field="currency_id",
        store=True,
        groups="field_operation.service_group_user",
    )
    total_stock_all = fields.Monetary(
        string="Total Stock Cost",
        compute="_compute_stock_costs",
        currency_field="currency_id",
        store=True,
        groups="field_operation.service_group_user",
    )

    @api.depends("stock_line_ids")
    def _compute_stock_line_count(self):
        for rec in self:
            rec.stock_line_count = len(rec.stock_line_ids)

    @api.depends(
        "stock_line_ids.subtotal",
        "stock_line_ids.consumption_type",
        "stock_line_ids.state",
    )
    def _compute_stock_costs(self):
        for rec in self:
            done_lines = rec.stock_line_ids.filtered(
                lambda line: line.state in ("confirmed", "done")
            )
            rec.total_stock_cost = sum(
                done_lines.filtered(
                    lambda line: line.consumption_type == "serviced"
                ).mapped("subtotal")
            )
            rec.total_warranty_cost = sum(
                done_lines.filtered(
                    lambda line: line.consumption_type == "warranty"
                ).mapped("subtotal")
            )
            rec.total_stock_all = rec.total_stock_cost + rec.total_warranty_cost

    # Actions
    def action_confirm_stock(self):
        """Confirm all draft stock lines and create stock picking."""
        self.ensure_one()
        draft_lines = self.stock_line_ids.filtered(lambda line: line.state == "draft")
        if not draft_lines:
            raise UserError(_("There are no draft stock lines to confirm."))
        draft_lines._create_stock_picking(draft_lines)
        return True

    def action_view_stock_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Stock Consumption"),
            "res_model": "field.operation.stock.line",
            "view_mode": "list,form",
            "domain": [("operation_id", "=", self.id)],
            "context": {
                "default_operation_id": self.id,
            },
        }

    def action_view_stock_pickings(self):
        self.ensure_one()
        pickings = self.stock_line_ids.mapped("stock_picking_id")
        if len(pickings) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Stock Picking"),
                "res_model": "stock.picking",
                "view_mode": "form",
                "res_id": pickings.id,
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Stock Pickings"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", pickings.ids)],
        }
