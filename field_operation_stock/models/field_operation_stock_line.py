# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FieldOperationStockLine(models.Model):
    _name = "field.operation.stock.line"
    _description = "Field Operation Stock Consumption Line"
    _inherit = "mail.thread"
    _order = "id desc"

    name = fields.Char(
        string="Reference",
        default="/",
        readonly=True,
        copy=False,
    )
    operation_id = fields.Many2one(
        "field.operation",
        string="Operation",
        required=True,
        tracking=True,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        related="operation_id.partner_id",
        store=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        tracking=True,
        domain=[("type", "in", ["consu", "product"])],
    )
    product_code = fields.Char(
        string="Product Code",
        related="product_id.default_code",
        store=True,
    )
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        required=True,
    )
    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        required=True,
        tracking=True,
    )
    unit_price = fields.Float(
        string="Unit Price",
        tracking=True,
        groups="field_operation.service_group_user",
    )
    subtotal = fields.Float(
        string="Subtotal",
        compute="_compute_subtotal",
        store=True,
        groups="field_operation.service_group_user",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    consumption_type = fields.Selection(
        [
            ("serviced", "Servise Dahil"),
            ("warranty", "Garanti / Ücretsiz"),
        ],
        string="Consumption Type",
        default="serviced",
        required=True,
        tracking=True,
    )
    stock_move_id = fields.Many2one(
        "stock.move",
        string="Stock Move",
        readonly=True,
        copy=False,
    )
    stock_picking_id = fields.Many2one(
        "stock.picking",
        string="Stock Picking",
        readonly=True,
        copy=False,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    notes = fields.Text(string="Notes")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    @api.depends("quantity", "unit_price")
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.quantity * rec.unit_price

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id
            self.unit_price = self.product_id.standard_price
            self.name = self.product_id.display_name

    @api.constrains("quantity")
    def _check_quantity(self):
        for rec in self:
            if rec.quantity <= 0:
                raise UserError(_("Quantity must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("field.operation.stock.line")
                    or "/"
                )
        return super().create(vals_list)

    def action_confirm(self):
        """Move a single draft line to `confirmed` (RPC / integration only).

        The line form deliberately has no Confirm button: this transition does
        not create any stock move, and `action_confirm_stock` only picks up
        draft lines, so a line confirmed this way would never reach the stock
        while still entering the operation cost totals. Kept as an API for
        integrations that need the intermediate state.
        """
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft lines can be confirmed."))
            rec.write({"state": "confirmed"})

    def unlink(self):
        """Refuse to delete a line whose stock has already been consumed.

        A done line is the only trace of the stock move it created: deleting it
        would drop the operation cost and leave the validated transfer behind.
        """
        consumed = self.filtered(lambda line: line.state == "done")
        if consumed:
            raise UserError(
                _(
                    "A consumption line whose stock move is done cannot be "
                    "deleted. Cancel the operation or reverse the transfer "
                    "instead."
                )
            )
        return super().unlink()

    def action_cancel(self):
        for rec in self:
            if rec.state == "done" and rec.stock_move_id:
                raise UserError(
                    _(
                        "Cannot cancel a line that has a completed stock move. "
                        "Please use Odoo stock to reverse the move."
                    )
                )
            rec.write({"state": "cancelled"})

    def _create_stock_picking(self, lines):
        """Create a single stock.picking from multiple confirmed lines.

        Called from field.operation action_confirm_stock method.
        """
        if not lines:
            return False

        operation = lines[0].operation_id

        source_location = self.env.ref(
            "stock.stock_location_stock",
            raise_if_not_found=False,
        )
        dest_location = self.env.ref(
            "stock.stock_location_customers",
            raise_if_not_found=False,
        )

        if not source_location or not dest_location:
            raise UserError(
                _("Default stock locations not found. Please configure your warehouse.")
            )

        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("company_id", "=", operation.company_id.id),
            ],
            limit=1,
        )
        if not picking_type:
            raise UserError(_("No outgoing picking type found for this company."))

        picking_vals = {
            "origin": operation.name,
            "partner_id": operation.partner_id.id if operation.partner_id else False,
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": dest_location.id,
            "company_id": operation.company_id.id,
            "move_ids": [],
        }

        for line in lines:
            move_vals = {
                "product_id": line.product_id.id,
                "product_uom": line.product_uom_id.id,
                "product_uom_qty": line.quantity,
                "location_id": source_location.id,
                "location_dest_id": dest_location.id,
                "company_id": operation.company_id.id,
                "origin": operation.name,
            }
            picking_vals["move_ids"].append((0, 0, move_vals))

        picking = self.env["stock.picking"].create(picking_vals)

        lines.write(
            {
                "stock_picking_id": picking.id,
                "state": "confirmed",
            }
        )

        picking.action_confirm()
        picking.action_assign()

        unavailable = picking.move_ids.filtered(lambda m: m.state != "assigned")
        if unavailable:
            products = ", ".join(unavailable.mapped("product_id.display_name"))
            raise UserError(
                _("Insufficient stock for: %s. Please check inventory levels.")
                % products
            )

        for move in picking.move_ids:
            if move.state == "assigned":
                # A move is validated only when it is picked: `_action_done`
                # filters out any move with `picked = False` (true since 18.0,
                # not a 19.0 change), so setting the quantity alone would leave
                # the stock untouched.
                move.quantity = move.product_uom_qty
                move.picked = True

        try:
            picking._action_done()
        except UserError as exc:
            # Only a core validation error is re-branded with the picking
            # reference: anything else must surface untouched instead of being
            # hidden behind a generic message.
            raise UserError(
                _(
                    "Stock picking could not be validated. "
                    "Please check the picking %s manually."
                )
                % picking.name
            ) from exc

        for line in lines:
            move = picking.move_ids.filtered(
                lambda m, p=line.product_id: m.product_id == p
            )
            if move:
                line.write(
                    {
                        "stock_move_id": move[:1].id,
                        "state": "done",
                    }
                )

        return picking
