# Copyright(C) 2025 - Today Softteknik Bilişim
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class MachineSparePart(models.Model):
    _name = "machine.spare.part"
    _description = "Machine Spare Part Usage"
    _inherit = ["mail.thread"]
    _order = "date desc"

    name = fields.Char(string="Reference", default="/", readonly=True, copy=False)
    machine_id = fields.Many2one(
        "machine.master", string="Machine", required=True, tracking=True
    )
    partner_id = fields.Many2one(
        "res.partner", string="Customer", related="machine_id.partner_id", store=True
    )
    date = fields.Date(
        string="Date",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    product_id = fields.Many2one(
        "product.product", string="Product", required=True, tracking=True
    )
    product_uom = fields.Many2one(
        "uom.uom", string="Unit of Measure", related="product_id.uom_id", store=True
    )
    product_code = fields.Char(
        string="Product Code", related="product_id.default_code", store=True
    )
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        groups="field_operation.service_group_user",
    )
    subtotal = fields.Monetary(
        string="Subtotal",
        compute="_compute_subtotal",
        store=True,
        currency_field="currency_id",
        groups="field_operation.service_group_user",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    source_type = fields.Selection(
        [
            ("stock", "From Stock"),
            ("purchase", "Purchased"),
            ("warranty", "Warranty Replacement"),
            ("external", "External"),
        ],
        string="Source Type",
        default="stock",
        tracking=True,
    )
    stock_move_id = fields.Many2one("stock.move", string="Stock Move", readonly=True)
    location_id = fields.Many2one(
        "stock.location",
        string="Source Location",
        default=lambda self: self.env.ref(
            "stock.stock_location_stock", raise_if_not_found=False
        ),
    )
    location_dest_id = fields.Many2one("stock.location", string="Destination Location")
    operation_id = fields.Many2one("field.operation", string="Service Operation")
    maintenance_id = fields.Many2one("machine.maintenance", string="Maintenance Record")
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
        "res.company", string="Company", default=lambda self: self.env.company
    )

    @api.depends("quantity", "unit_price")
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.quantity * rec.unit_price

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            # Cost of the spare part, not its sales price.
            self.unit_price = self.product_id.standard_price
            if not self.location_id:
                self.location_id = self.env.ref(
                    "stock.stock_location_stock", raise_if_not_found=False
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("machine.spare.part") or "/"
                )
        return super().create(vals_list)

    def _check_service_group(self):
        # Stock-affecting actions must be restricted to the service group.
        if not self.env.user.has_group("field_operation.service_group_user"):
            raise AccessError(_("You are not allowed to manage machine spare parts."))

    # Actions
    def action_confirm(self):
        self._check_service_group()
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft spare part records can be confirmed."))
        for rec in self:
            if rec.source_type == "stock" and not rec.stock_move_id:
                rec._create_stock_move()
            rec.write({"state": "confirmed"})

    def action_done(self):
        self._check_service_group()
        for rec in self:
            if rec.state != "confirmed":
                raise UserError(
                    _("Only confirmed spare part records can be completed.")
                )
            if rec.source_type == "stock" and not rec.stock_move_id:
                raise UserError(
                    _(
                        "Spare part %s has no stock move. Confirm it first so "
                        "the stock move is created.",
                        rec.display_name,
                    )
                )
        for rec in self:
            if rec.source_type == "stock":
                rec._apply_stock_move()
            rec.write({"state": "done"})

    def action_cancel(self):
        self._check_service_group()
        for rec in self:
            if rec.state == "cancelled":
                raise UserError(
                    _("Spare part %s is already cancelled.", rec.display_name)
                )
        for rec in self:
            move = rec.stock_move_id
            if move:
                if move.state == "done":
                    # The stock already left, so bring it back with a reversal.
                    rec._reverse_stock_move()
                elif move.state != "cancel":
                    move._action_cancel()
            rec.write({"state": "cancelled"})

    def _create_stock_move(self):
        """Create and confirm the stock move for a spare part consumption."""
        self.ensure_one()

        if not self.location_id:
            raise UserError(_("Please select a source location."))

        if not self.location_dest_id:
            # Goods leaving the company normally go to the customer location
            # (usage 'customer'), which is where field-consumed parts end up.
            # Kept as the fallback so the record field stays override-able.
            self.location_dest_id = self.env.ref(
                "stock.stock_location_customers", raise_if_not_found=False
            )

        move = self.env["stock.move"].create(
            {
                # Odoo 19 stock.move has no 'name' field (its rec name is 'reference');
                # the origin field carries the source document instead.
                "product_id": self.product_id.id,
                "product_uom": self.product_uom.id,
                "product_uom_qty": self.quantity,
                "location_id": self.location_id.id,
                "location_dest_id": self.location_dest_id.id,
                "origin": self.name,
                "company_id": self.company_id.id,
            }
        )
        move._action_confirm()
        self.stock_move_id = move.id

        return move

    def _validate_stock_move(self, move):
        """Reserve then validate a stock move, refusing when stock is short.

        Odoo 19 only processes a move flagged as ``picked`` in ``_action_done``
        (see ``stock.move._action_done``); validating a merely confirmed move
        is a no-op. So we reserve first, abort when the reserved quantity is
        short of the demand, and only then flag the move as picked.
        """
        move._action_assign()
        reserved = move.quantity
        if move.product_uom.compare(reserved, move.product_uom_qty) < 0:
            # Not enough stock: release the reservation so the move is not
            # left half-picked, then abort without touching stock.
            move._do_unreserve()
            raise UserError(
                _(
                    "Not enough stock for %(product)s: %(available)s available, "
                    "%(required)s required.",
                    product=move.product_id.display_name,
                    available=reserved,
                    required=move.product_uom_qty,
                )
            )
        move.picked = True
        move._action_done()
        return move

    def _apply_stock_move(self):
        """Reserve and validate the consumption move of this record."""
        self.ensure_one()
        self._validate_stock_move(self.stock_move_id)

    def _reverse_stock_move(self):
        """Validate a reverse move so a completed consumption returns stock."""
        self.ensure_one()
        move = self.stock_move_id
        reverse = self.env["stock.move"].create(
            {
                # No 'name' field on stock.move in Odoo 19; origin_returned_move_id
                # already links this reversal to the original move.
                "product_id": move.product_id.id,
                "product_uom": move.product_uom.id,
                "product_uom_qty": move.quantity,
                "location_id": move.location_dest_id.id,
                "location_dest_id": move.location_id.id,
                "origin": move.origin,
                "origin_returned_move_id": move.id,
                "company_id": move.company_id.id,
            }
        )
        reverse._action_confirm()
        self._validate_stock_move(reverse)
        return reverse

    def unlink(self):
        # A completed record carries a done stock move: deleting it would lose
        # the trace of the consumed stock, so block it and ask to cancel first
        # (cancelling creates the reversing move).
        if any(rec.stock_move_id.state == "done" for rec in self):
            raise UserError(
                _(
                    "You cannot delete a spare part record whose stock move is "
                    "done. Cancel it first to reverse the stock consumption."
                )
            )
        return super().unlink()

    def action_view_stock_move(self):
        self.ensure_one()
        if not self.stock_move_id:
            return False

        return {
            "type": "ir.actions.act_window",
            "name": _("Stock Move"),
            "res_model": "stock.move",
            "view_mode": "form",
            "res_id": self.stock_move_id.id,
        }


class SparePartConsumptionWizard(models.TransientModel):
    _name = "machine.spare.part.wizard"
    _description = "Spare Part Consumption Wizard"

    machine_id = fields.Many2one("machine.master", string="Machine", required=True)
    operation_id = fields.Many2one("field.operation", string="Service Operation")
    maintenance_id = fields.Many2one("machine.maintenance", string="Maintenance Record")
    line_ids = fields.One2many(
        "machine.spare.part.wizard.line", "wizard_id", string="Products"
    )
    part_ids = fields.Many2many(
        "machine.spare.part", string="Created Spare Parts", readonly=True
    )

    def action_create_spare_parts(self):
        """Create draft spare parts from the lines and confirm them."""
        self.ensure_one()
        self.env["machine.spare.part"]._check_service_group()
        if self.part_ids:
            # The wizard is single-shot: a second submission (for instance a
            # double click) would silently duplicate every line.
            raise UserError(
                _(
                    "Spare parts have already been created from this wizard. "
                    "Do not submit it twice."
                )
            )
        spare_parts = self.env["machine.spare.part"].create(
            [
                {
                    "machine_id": self.machine_id.id,
                    "operation_id": self.operation_id.id or False,
                    "maintenance_id": self.maintenance_id.id or False,
                    "product_id": line.product_id.id,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                    "source_type": "stock",
                }
                for line in self.line_ids
            ]
        )
        # Confirm so the stock moves are created: writing state='confirmed'
        # directly would skip this branch and never create a stock move.
        spare_parts.action_confirm()
        self.part_ids = [(6, 0, spare_parts.ids)]

        return {
            "type": "ir.actions.act_window",
            "name": _("Spare Parts"),
            "res_model": "machine.spare.part",
            "view_mode": "list,form",
            "domain": [("id", "in", spare_parts.ids)],
        }


class SparePartConsumptionWizardLine(models.TransientModel):
    _name = "machine.spare.part.wizard.line"
    _description = "Spare Part Consumption Wizard Line"

    wizard_id = fields.Many2one("machine.spare.part.wizard", string="Wizard")
    product_id = fields.Many2one("product.product", string="Product", required=True)
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    unit_price = fields.Float(string="Unit Price")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            # Cost of the spare part, not its sales price.
            self.unit_price = self.product_id.standard_price
