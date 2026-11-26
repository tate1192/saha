from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

COST_LINE_TYPES = [
    ("personnel", "Personnel"),
    ("material", "Material"),
    ("subcontractor", "Subcontractor"),
    ("vehicle", "Vehicle / Fuel"),
    ("other", "Other"),
]


class FieldOperationCostLine(models.Model):
    """One cost component of a field operation.

    Lines are either typed by hand or derived (``auto``): labour lines come from
    the assigned people and ``total_work``, materials from the installed stock /
    machine layers, subcontractor and vehicle lines from the matching amount
    fields on the operation. Derived lines are cleared and rebuilt on refresh so
    a re-plan never doubles the cost.
    """

    _name = "field.operation.cost.line"
    _description = "Field Operation Cost Line"
    _order = "operation_id, line_type, id"
    _check_company_auto = True

    operation_id = fields.Many2one(
        "field.operation",
        string="Operation",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    name = fields.Char(string="Description", required=True)
    line_type = fields.Selection(
        COST_LINE_TYPES, string="Cost Type", required=True, default="personnel"
    )
    employee_id = fields.Many2one("hr.employee", string="Employee")
    date = fields.Date(string="Date", default=fields.Date.context_today)
    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        digits=(16, 2),
        help="Hours on labour lines, units on every other type.",
    )
    unit_cost = fields.Monetary(string="Unit Cost", currency_field="currency_id")
    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
    )
    auto = fields.Boolean(
        string="Automatic",
        readonly=True,
        copy=False,
        help="Rebuilt by 'Refresh Costs'; delete or edit it by hand instead if "
        "the amount must not be overwritten.",
    )
    note = fields.Char(string="Note")
    currency_id = fields.Many2one(
        "res.currency", string="Currency", related="operation_id.currency_id"
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="operation_id.company_id",
        store=True,
        index=True,
    )

    @api.depends("quantity", "unit_cost")
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.unit_cost

    @api.constrains("quantity", "unit_cost")
    def _check_positive(self):
        for line in self:
            if line.quantity < 0 or line.unit_cost < 0:
                raise ValidationError(
                    _("Cost quantities and unit costs cannot be negative.")
                )
