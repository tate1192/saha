from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FieldOperation(models.Model):
    _inherit = "field.operation"

    time_line_ids = fields.One2many(
        "field.operation.time.line", "operation_id", string="Time Lines"
    )
    time_draft = fields.Float(
        string="Draft Hours",
        compute="_compute_time_totals",
        store=True,
        help="Hours entered but not approved yet.",
    )
    time_approved = fields.Float(
        string="Approved Hours", compute="_compute_time_totals", store=True
    )
    time_expected = fields.Float(
        string="Expected Hours",
        compute="_compute_time_totals",
        store=True,
        help="Service duration x number of assigned people.",
    )
    time_difference = fields.Float(
        string="Difference",
        compute="_compute_time_totals",
        store=True,
        help="Approved hours minus expected hours: the gap the office has to "
        "explain before the operation is billed.",
    )

    @api.depends(
        "time_line_ids.duration",
        "time_line_ids.state",
        "total_work",
        "person_ids",
    )
    def _compute_time_totals(self):
        for operation in self:
            lines = operation.time_line_ids
            operation.time_draft = sum(
                lines.filtered(lambda line: line.state == "draft").mapped("duration")
            )
            operation.time_approved = sum(
                lines.filtered(lambda line: line.state == "approved").mapped("duration")
            )
            operation.time_expected = operation.total_work * len(operation.person_ids)
            operation.time_difference = (
                operation.time_approved - operation.time_expected
            )

    # ------------
    # Actions
    # ------------
    def action_generate_time_lines(self):
        """Propose one line per assigned person from the planned window."""
        self._check_office_group("propose time lines")
        line_model = self.env["field.operation.time.line"]
        for operation in self:
            if not operation.total_work:
                raise UserError(
                    _(
                        "Set the start and end date of %(operation)s first: the "
                        "proposal takes the duration from them.",
                        operation=operation.name,
                    )
                )
            if not operation.person_ids:
                raise UserError(
                    _(
                        "Assign at least one person to %(operation)s.",
                        operation=operation.name,
                    )
                )
            # ``sudo`` for the existence check only: the office user asking for
            # the proposal may not read every line, and an empty read would
            # propose a second line for a person who already has one that day.
            date = (operation.start_date or fields.Datetime.now()).date()
            planned = operation.sudo().time_line_ids.filtered(
                lambda line, date=date: line.date == date
            )
            vals_list = [
                {
                    "operation_id": operation.id,
                    "employee_id": employee.id,
                    "date": date,
                    "duration": operation.total_work,
                }
                for employee in operation.person_ids - planned.employee_id
            ]
            if vals_list:
                line_model.create(vals_list)
        return True

    def action_approve_time_lines(self):
        self._check_office_group("approve time lines")
        self.time_line_ids.filtered(lambda line: line.state == "draft").action_approve()
        return True

    def action_reset_time_lines(self):
        self._check_office_group("reset time lines to draft")
        self.time_line_ids.action_reset_draft()
        return True
