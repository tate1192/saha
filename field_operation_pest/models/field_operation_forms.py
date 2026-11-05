from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError


class FieldOperationForms(models.Model):
    _inherit = "field.operation.forms"

    @api.model
    def _default_picking_transfer(self):
        return self.env["stock.picking.type"].search(
            [
                ("warehouse_id.company_id", "=", self.env.company.id),
                ("code", "=", "outgoing"),
            ],
            limit=1,
        )

    @api.model
    def _default_location_id(self):
        company_user = self.env.user.company_id
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", company_user.id)], limit=1
        )
        if warehouse:
            return warehouse.lot_stock_id.id

    @api.model
    def _default_out_location_id(self):
        company_id = self.env.context.get("default_company_id") or self.env.company.id
        return self.env["stock.location"].search(
            [("usage", "=", "customer"), ("company_id", "in", [company_id, False])],
            limit=1,
        )

    # Biocidal
    hygiene = fields.Boolean(string="Hygiene")
    infestation = fields.Boolean(string="Infestation")
    insulation = fields.Boolean(string="Insulation")
    storage = fields.Boolean(string="Storage")
    efk_ift = fields.Boolean(string="EFK-IFT")
    monitors = fields.Boolean(string="Monitors")
    others = fields.Boolean(string="Others")
    residence = fields.Char(string="Number of Residential Flats")
    place = fields.Char(string="Area of the Place Built")
    application_method = fields.Char(string="Application Method")
    security_precautions = fields.Html(string="Security Precautions")
    responsible_manager_id = fields.Many2one(
        "hr.employee", string="Responsible Manager"
    )
    application_place = fields.Selection(
        [
            ("house", "House"),
            ("workplace", "Workplace"),
            ("other", "Other"),
        ],
        string="Application Place",
        tracking=True,
    )

    pesticide_ids = fields.One2many(
        "field.operation.pesticide", "forms_id", string="Pesticide Product"
    )
    pest_type_ids = fields.Many2many("field.operation.pest.type", string="Pest Type")
    # service_type_id / service_type are declared once in field_operation_forms;
    # redeclaring them here silently overrode the base definition (readonly=False).
    # Picking & Locations
    stock_picking_id = fields.Many2one("stock.picking")
    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Operation Type",
        copy=True,
        readonly=False,
        store=True,
        default=_default_picking_transfer,
        required=True,
        check_company=True,
        index=True,
    )
    source_location_id = fields.Many2one(
        "stock.location", string="Source Location", default=_default_location_id
    )
    destination_location_id = fields.Many2one(
        "stock.location",
        string="Destination Location",
        default=_default_out_location_id,
    )

    # Declared here with the transfer logic it belongs to.
    picking_count = fields.Integer(
        compute="_compute_picking_count", string="Delivery Orders"
    )

    @api.depends("stock_picking_id")
    def _compute_picking_count(self):
        for form in self:
            form.picking_count = 1 if form.stock_picking_id else 0

    def action_transfer(self):
        """Create the delivery order carrying the pesticide lines of this form."""
        self.ensure_one()
        if not self.env.user.has_group("field_operation_forms.forms_user"):
            raise AccessError(_("You are not allowed to create the delivery order."))
        if not self.pesticide_ids:
            raise UserError(_("Add at least one pesticide line before the transfer."))
        if self.source_location_id == self.destination_location_id:
            raise UserError(
                _("Source and destination locations are the same: change one of them.")
            )
        picking = (
            self.env["stock.picking"]
            .sudo()
            .create(
                {
                    "partner_id": self.customer_id.id,
                    "picking_type_id": self.picking_type_id.id,
                    "location_id": self.source_location_id.id,
                    "location_dest_id": self.destination_location_id.id,
                    "origin": self.name,
                    "field_operation_form_id": self.id,
                    "move_ids": [
                        Command.create(
                            {
                                "product_id": line.product_id.id,
                                "product_uom": line.product_uom.id,
                                "product_uom_qty": line.product_qty,
                                "picked": True,
                                "location_id": self.source_location_id.id,
                                "location_dest_id": self.destination_location_id.id,
                            }
                        )
                        for line in self.pesticide_ids
                    ],
                }
            )
        )
        picking.action_confirm()
        self.stock_picking_id = picking
        return True

    def action_view_picking(self):
        """Open the delivery order created from this form."""
        self.ensure_one()
        if not self.stock_picking_id:
            return {"type": "ir.actions.act_window_close"}
        return {
            "name": self.stock_picking_id.display_name,
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.stock_picking_id.id,
            "type": "ir.actions.act_window",
        }
