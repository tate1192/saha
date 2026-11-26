from odoo import _, api, fields, models
from odoo.exceptions import AccessError

COST_GROUP = "field_operation.service_group_all"
COST_TYPE_KEYS = ("personnel", "material", "subcontractor", "vehicle", "other")


class FieldOperation(models.Model):
    _inherit = "field.operation"

    # Money is an office concern: cost, revenue and margin stay with the head
    # office group, exactly like ``service_price`` is hidden from field workers.
    cost_line_ids = fields.One2many(
        "field.operation.cost.line",
        "operation_id",
        string="Cost Lines",
        groups=COST_GROUP,
    )
    total_cost = fields.Monetary(
        string="Total Cost",
        currency_field="currency_id",
        compute="_compute_cost_totals",
        store=True,
        groups=COST_GROUP,
    )
    personnel_cost = fields.Monetary(
        string="Personnel Cost",
        currency_field="currency_id",
        compute="_compute_cost_totals",
        store=True,
        groups=COST_GROUP,
    )
    material_cost = fields.Monetary(
        string="Material Cost",
        currency_field="currency_id",
        compute="_compute_cost_totals",
        store=True,
        groups=COST_GROUP,
    )
    external_cost = fields.Monetary(
        string="Subcontractor / Vehicle",
        currency_field="currency_id",
        compute="_compute_cost_totals",
        store=True,
        groups=COST_GROUP,
    )
    other_cost = fields.Monetary(
        string="Other Cost",
        currency_field="currency_id",
        compute="_compute_cost_totals",
        store=True,
        groups=COST_GROUP,
    )
    cost_hours = fields.Float(
        string="Costed Hours",
        compute="_compute_cost_totals",
        store=True,
        groups=COST_GROUP,
        help="Personnel hours behind the labour cost lines. Compare it with "
        "real worked hours before trusting the margin.",
    )
    revenue_amount = fields.Monetary(
        string="Revenue",
        currency_field="currency_id",
        compute="_compute_profitability",
        store=True,
        groups=COST_GROUP,
    )
    profit_amount = fields.Monetary(
        string="Profit",
        currency_field="currency_id",
        compute="_compute_profitability",
        store=True,
        groups=COST_GROUP,
    )
    profit_percent = fields.Float(
        string="Margin (%)",
        compute="_compute_profitability",
        store=True,
        groups=COST_GROUP,
    )
    contractor_cost = fields.Monetary(
        string="Subcontractor Cost",
        currency_field="currency_id",
        groups=COST_GROUP,
        tracking=True,
    )
    vehicle_cost = fields.Monetary(
        string="Vehicle / Fuel Cost",
        currency_field="currency_id",
        groups=COST_GROUP,
        tracking=True,
    )

    @api.depends(
        "cost_line_ids.amount",
        "cost_line_ids.quantity",
        "cost_line_ids.line_type",
    )
    def _compute_cost_totals(self):
        # Every read below is head-office restricted, while a field worker
        # closing a job still stores the totals: read through ``sudo`` or the
        # protected fields either raise for the worker or come back empty and
        # zero the margin of the operation.
        for operation in self:
            by_type = dict.fromkeys(COST_TYPE_KEYS, 0.0)
            hours = 0.0
            for line in operation.sudo().cost_line_ids:
                by_type[line.line_type] = by_type.get(line.line_type, 0.0) + line.amount
                if line.line_type == "personnel":
                    hours += line.quantity
            operation.personnel_cost = by_type["personnel"]
            operation.material_cost = by_type["material"]
            operation.external_cost = by_type["subcontractor"] + by_type["vehicle"]
            operation.other_cost = by_type["other"]
            operation.total_cost = sum(by_type.values())
            operation.cost_hours = hours

    @api.depends("service_price", "total_cost")
    def _compute_profitability(self):
        """Revenue is the price typed on the operation, or the contract line
        when the recurring-service layer is installed and priced the job."""
        has_contract_line = "contract_line_id" in self._fields
        for operation in self:
            protected = operation.sudo()
            revenue = protected.service_price or 0.0
            if not revenue and has_contract_line and protected.contract_line_id:
                revenue = protected.contract_line_id.price_subtotal
            operation.revenue_amount = revenue
            operation.profit_amount = revenue - protected.total_cost
            operation.profit_percent = (
                (operation.profit_amount / revenue) * 100.0 if revenue else 0.0
            )

    # ------------
    # Cost refresh
    # ------------
    def action_refresh_costs(self):
        """Rebuild the derived lines from the plan.

        Gated on the cost group, not the office group: the button lives in the
        head-office "Costs" page and the lines themselves are head-office only,
        so an office user who never sees a cost line has no business rewriting
        them over RPC either.
        """
        if not self.env.user.has_group(COST_GROUP):
            raise AccessError(
                _("Only head office users are allowed to recalculate service costs.")
            )
        self._refresh_auto_cost_lines()
        return True

    def _refresh_auto_cost_lines(self):
        """Rebuild the derived lines, keeping the ones typed by hand.

        Runs with ``sudo``: closing a service is a field action, and the derived
        cost of it must not depend on the closer's access to money fields.
        Without it the previous automatic lines are invisible to a worker, so
        the rebuild adds a second set instead of replacing the first.
        """
        line_model = self.env["field.operation.cost.line"].sudo()
        for operation in self:
            operation.sudo().cost_line_ids.filtered("auto").unlink()
            vals_list = operation._prepare_auto_cost_vals()
            if vals_list:
                line_model.create(vals_list)

    def _prepare_auto_cost_vals(self):
        self.ensure_one()
        protected = self.sudo()
        vals_list = []
        hours = protected.total_work
        if hours:
            for employee in protected.person_ids:
                rate = employee.hourly_cost
                if not rate:
                    continue
                vals_list.append(
                    {
                        "operation_id": self.id,
                        "auto": True,
                        "line_type": "personnel",
                        "employee_id": employee.id,
                        "name": _("Labour: %(employee)s", employee=employee.name),
                        "quantity": hours,
                        "unit_cost": rate,
                        "date": (self.start_date or fields.Datetime.now()).date(),
                    }
                )
        material = protected._get_material_cost()
        if material:
            vals_list.append(
                {
                    "operation_id": self.id,
                    "auto": True,
                    "line_type": "material",
                    "name": _("Materials issued"),
                    "quantity": 1.0,
                    "unit_cost": material,
                }
            )
        labels = {"subcontractor": _("Subcontractor"), "vehicle": _("Vehicle / Fuel")}
        for cost_type, amount in (
            ("subcontractor", protected.contractor_cost),
            ("vehicle", protected.vehicle_cost),
        ):
            if not amount:
                continue
            vals_list.append(
                {
                    "operation_id": self.id,
                    "auto": True,
                    "line_type": cost_type,
                    "name": labels[cost_type],
                    "quantity": 1.0,
                    "unit_cost": amount,
                }
            )
        return vals_list

    def _get_material_cost(self):
        """Material cost contributed by optional layers (stock, machine parts).

        Probing ``_fields`` keeps this module installable without the stock or
        machine modules: whichever is present simply adds its total.
        """
        self.ensure_one()
        protected = self.sudo()
        total = 0.0
        for field_name in ("total_stock_all", "spare_part_total"):
            if field_name in self._fields:
                total += getattr(protected, field_name) or 0.0
        return total

    def write(self, vals):
        res = super().write(vals)
        if vals.get("status") == "done":
            self._refresh_auto_cost_lines()
        return res
