# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class FieldOperationCreateSaleWizard(models.TransientModel):
    _name = "field.operation.create.sale.wizard"
    _description = "Create Sale from Field Operation"

    operation_ids = fields.Many2many(
        "field.operation",
        "field_operation_create_sale_rel",
        "wizard_id",
        "operation_id",
        string="Field Operations",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        domain=[("sale_ok", "=", True)],
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Only trust ``active_ids`` launched from a field operation: coming from any
        # other model they are ids of foreign records, not services.
        if self.env.context.get(
            "active_model"
        ) == "field.operation" and self.env.context.get("active_ids"):
            res["operation_ids"] = [fields.Command.set(self.env.context["active_ids"])]
        if "product_id" in fields_list:
            product = self._default_product()
            if product:
                res["product_id"] = product.id
        return res

    @api.model
    def _default_product(self):
        """Return the product configured in the settings, if it still exists.

        The parameter is a raw ``ir.config_parameter`` value: it used to be fed to
        ``int()`` unguarded, so a deleted product (or any other junk value) made the
        wizard fail to open at all.
        """
        product_id = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("field_operation_sale.default_product_id")
        )
        if not product_id or not str(product_id).isdigit():
            return self.env["product.product"]
        return self.env["product.product"].browse(int(product_id)).exists()

    def _order_pricelist(self, operation):
        """Pick a pricelist that makes the order speak the service's currency.

        The order price comes straight from the service: ``service_price`` is written
        as-is into ``price_unit``, never converted. So the order must be priced in the
        service's currency — the customer's own pricelist when it already is, otherwise
        any pricelist of the service's company (company-specific first, company-neutral
        fallback) in the same currency.

        An empty recordset is not always an error: when the service is already in the
        company currency, an order without a pricelist lands in that same currency, so
        no conversion can happen. It only becomes a refusal when the service speaks a
        foreign currency, because then the order would silently price the amount in
        another currency. The caller makes that call.
        """
        if not operation.currency_id:
            return self.env["product.pricelist"]
        partner_pricelist = operation.partner_id.with_company(
            operation.company_id
        ).property_product_pricelist
        if partner_pricelist and partner_pricelist.currency_id == operation.currency_id:
            return partner_pricelist
        pricelist_model = self.env["product.pricelist"].with_company(
            operation.company_id
        )
        company_pricelist = pricelist_model.search(
            [
                ("currency_id", "=", operation.currency_id.id),
                ("company_id", "=", operation.company_id.id),
            ],
            limit=1,
        )
        if company_pricelist:
            return company_pricelist
        return pricelist_model.search(
            [
                ("currency_id", "=", operation.currency_id.id),
                ("company_id", "=", False),
            ],
            limit=1,
        )

    def action_create_sale(self):
        """Create one draft sale order per selected service."""
        self.ensure_one()

        if not self.env.user.has_group(
            "field_operation_sale.group_field_operation_sale_enabled"
        ):
            raise AccessError(
                _("You are not allowed to create sale orders from services.")
            )
        if not self.operation_ids:
            raise UserError(_("Please select at least one field operation."))

        without_customer = self.operation_ids.filtered(lambda op: not op.partner_id)
        if without_customer:
            raise UserError(
                _(
                    "These services have no customer, no sale order can be created: %s",
                    ", ".join(without_customer.mapped("name")),
                )
            )

        already_sold = self.operation_ids.filtered("sale_id")
        if already_sold:
            raise UserError(
                _(
                    "These services already have a sale order, "
                    "no second one is created: %s",
                    ", ".join(already_sold.mapped("name")),
                )
            )

        # Validate every service up front. Checking inside the loop would leave the
        # earlier services with their draft orders behind whenever the caller runs
        # outside a web request (server action, cron), which rolls nothing back.
        # ``not pricelist`` (not ``pricelist in recordset``): recordsets are compared
        # with their environment, and the helper returns a ``with_company`` copy.
        pricelists = {}
        for operation in self.operation_ids:
            if not operation.currency_id:
                raise UserError(
                    _(
                        "The service %(operation)s has no currency: set one first.",
                        operation=operation.name,
                    )
                )
            pricelist = self._order_pricelist(operation)
            if (
                not pricelist
                and operation.currency_id != operation.company_id.currency_id
            ):
                raise UserError(
                    _(
                        "No pricelist in %(service_currency)s is available for "
                        "%(operation)s: the order price comes from the service price "
                        "and will not be converted. Create a pricelist in that "
                        "currency or price the service in the customer's currency.",
                        service_currency=operation.currency_id.name,
                        operation=operation.name,
                    )
                )
            pricelists[operation.id] = pricelist

        created_sales = self.env["sale.order"]
        for operation in self.operation_ids:
            sale = self.env["sale.order"].create(
                {
                    "partner_id": operation.partner_id.id,
                    "company_id": operation.company_id.id,
                    "pricelist_id": pricelists[operation.id].id,
                    "order_types": "service",
                    "note": operation.description or "",
                }
            )
            sale_line = self.env["sale.order.line"].create(
                {
                    "order_id": sale.id,
                    "product_id": self.product_id.id,
                    "name": operation.subject or "",
                    "price_unit": operation.service_price or 0.0,
                    "product_uom_qty": 1.0,
                }
            )
            operation.write({"sale_id": sale.id, "sale_line_id": sale_line.id})
            created_sales |= sale

        return {
            "name": _("Created Sales"),
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", created_sales.ids)],
        }
