# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    field_operation_ids = fields.One2many(
        "field.operation", "sale_id", string="Services"
    )
    field_operation_count = fields.Integer(
        compute="_compute_field_operation_count", string="Service Count"
    )
    order_types = fields.Selection(
        [("service", "Service"), ("stock", "Stock")], string="Sale Type"
    )

    @api.depends("field_operation_ids")
    def _compute_field_operation_count(self):
        """Number of services pointing at this order.

        The dependency goes through the ``field.operation.sale_id`` one2many, otherwise
        the counter never moves when a service is created or relinked for this order.
        """
        for order in self:
            order.field_operation_count = len(order.field_operation_ids)

    def show_field_operation(self):
        """Open the only linked service, or the list when there are several."""
        self.ensure_one()
        services = self.field_operation_ids
        if len(services) == 1:
            return {
                "name": _("Field Operation"),
                "res_model": "field.operation",
                "view_mode": "form",
                "type": "ir.actions.act_window",
                "res_id": services.id,
            }
        return {
            "name": _("Field Operations"),
            "res_model": "field.operation",
            "view_mode": "list,form",
            "type": "ir.actions.act_window",
            "domain": [("sale_id", "=", self.id)],
            "context": {"default_sale_id": self.id},
        }

    def _prepare_invoice(self):
        """Carry the service reference over to the invoice.

        The only link between an order and its services is
        ``field.operation.sale_id``; the first service is written to the invoice so the
        "Services" stat button on the invoice can find its way back.
        """
        res = super()._prepare_invoice()
        operation = self.field_operation_ids[:1]
        if operation:
            res["field_operation_id"] = operation.id
        return res

    def create_sale_service(self):
        """Create one ``field.operation`` per product line of a service order.

        Each service keeps the line it was born from (``sale_line_id``) and inherits the
        order's currency; the company context follows the order, so a service can never
        land in another company with a foreign amount. The order side of the link is
        ``field.operation.sale_id``, which is what the counter and the stat button read.
        """
        for order in self:
            if order.order_types != "service":
                continue
            if order.state == "cancel":
                raise UserError(
                    _(
                        "This sale order is cancelled, no service is created: %s.",
                        order.name,
                    )
                )
            if not self.env.user.has_group(
                "field_operation_sale.group_field_operation_sale_enabled"
            ):
                raise AccessError(
                    _("You are not allowed to create services from a sale order.")
                )
            if order.field_operation_ids:
                raise UserError(
                    _(
                        "This sale order already has services: %s.",
                        ", ".join(order.field_operation_ids.mapped("name")),
                    )
                )

            operations = self.env["field.operation"].with_company(order.company_id)
            created = self.env["field.operation"]
            for line in order.order_line:
                if line.display_type or not line.product_id:
                    continue
                created |= operations.create(
                    {
                        "sale_id": order.id,
                        "sale_line_id": line.id,
                        "partner_id": order.partner_id.id,
                        "subject": line.name or line.product_id.display_name,
                        "start_date": fields.Datetime.now(),
                        "description": order.note or "",
                        "service_type_id": line.product_id.service_type_id.id,
                        "service_price": line.price_subtotal,
                        "currency_id": order.currency_id.id,
                    }
                )

            if not created:
                raise UserError(
                    _("There are no product lines to create service operations.")
                )
        return True
