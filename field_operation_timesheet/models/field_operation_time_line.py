from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

STATE = [("draft", "Draft"), ("approved", "Approved")]
UNLOCK = "field_operation_time_unlock"


class FieldOperationTimeLine(models.Model):
    """Hours one employee spent on one field operation.

    Draft lines are editable by whoever can reach the operation; approving
    locks them so the hours behind a cost report cannot change afterwards.
    """

    _name = "field.operation.time.line"
    _description = "Field Operation Time Line"
    _order = "date desc, id desc"
    _check_company_auto = True

    operation_id = fields.Many2one(
        "field.operation",
        string="Operation",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, index=True
    )
    date = fields.Date(
        string="Date", required=True, default=fields.Date.context_today, index=True
    )
    duration = fields.Float(
        string="Duration",
        required=True,
        digits=(16, 2),
        help="Hours spent on the operation by this employee.",
    )
    state = fields.Selection(
        STATE, string="Status", default="draft", required=True, copy=False, index=True
    )
    approved_by = fields.Many2one(
        "res.users", string="Approved By", readonly=True, copy=False
    )
    approved_on = fields.Datetime(string="Approved On", readonly=True, copy=False)
    note = fields.Char(string="Note")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="operation_id.company_id",
        store=True,
        index=True,
    )

    @api.constrains("duration")
    def _check_duration(self):
        for line in self:
            if line.duration <= 0:
                raise ValidationError(_("Duration must be greater than zero."))

    @api.constrains("employee_id", "operation_id")
    def _check_employee_assigned(self):
        for line in self:
            operation = line.operation_id
            if (
                line.employee_id
                and operation.person_ids
                and line.employee_id not in operation.person_ids
            ):
                raise ValidationError(
                    _(
                        "%(employee)s is not assigned to service %(operation)s.",
                        employee=line.employee_id.name,
                        operation=operation.name,
                    )
                )

    def action_approve(self):
        self._check_office_group("approve time lines")
        now = fields.Datetime.now()
        for line in self.filtered(lambda rec: rec.state == "draft"):
            line.write(
                {
                    "state": "approved",
                    "approved_by": self.env.user.id,
                    "approved_on": now,
                }
            )
        return True

    def action_reset_draft(self):
        self._check_office_group("reset time lines to draft")
        self.with_context(**{UNLOCK: True}).write(
            {"state": "draft", "approved_by": False, "approved_on": False}
        )
        return True

    def write(self, vals):
        if not self.env.context.get(UNLOCK):
            locked = self.filtered(lambda rec: rec.state == "approved")
            if locked:
                raise UserError(
                    _(
                        "Approved time lines are locked: reset them to draft "
                        "before changing the hours."
                    )
                )
        return super().write(vals)

    def unlink(self):
        locked = self.filtered(lambda rec: rec.state == "approved")
        if locked:
            raise UserError(
                _("Approved time lines cannot be deleted: reset them to draft first.")
            )
        return super().unlink()

    def _check_office_group(self, action):
        """Mirror the core: the button is hidden, the RPC has to be refused."""
        if not self.env.user.has_group("field_operation.service_group_user"):
            raise AccessError(_("Only office users are allowed to %s.", action))
