from datetime import datetime, time

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class ReconciliationLine(models.TransientModel):
    _name = "field.operation.timesheet.reconciliation.line"
    _description = "Field time vs attendance line"
    _order = "employee_id"

    wizard_id = fields.Many2one(
        "field.operation.timesheet.reconciliation", required=True, ondelete="cascade"
    )
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    timesheet_hours = fields.Float(string="Approved Timesheet")
    draft_hours = fields.Float(string="Draft Timesheet")
    attendance_hours = fields.Float(string="Attendance")
    difference = fields.Float(string="Difference")


class Reconciliation(models.TransientModel):
    """Month-end check between field time lines and HR attendance.

    Approved time is what the operation is costed on; attendance is what the
    company pays. Printing both and the gap next to them is the only way the
    two numbers stay believable.
    """

    _name = "field.operation.timesheet.reconciliation"
    _description = "Field time vs attendance reconciliation"

    date_from = fields.Date(
        string="From",
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(string="To", required=True, default=fields.Date.context_today)
    employee_ids = fields.Many2many(
        "hr.employee",
        string="Employees",
        help="Leave empty to check every employee having field time or "
        "attendance in the period.",
    )
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    line_ids = fields.One2many(
        "field.operation.timesheet.reconciliation.line",
        "wizard_id",
        string="Reconciliation",
    )

    def action_compute(self):
        # The report reads everybody's hours in the period, so it is office
        # work: the menu already hides it behind the group, the RPC must too.
        if not self.env.user.has_group("field_operation.service_group_user"):
            raise AccessError(
                _("Only office users are allowed to reconcile field time.")
            )
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("The start date cannot be after the end date."))
        if "hr.attendance" not in self.env:
            raise UserError(
                _(
                    "Install the Attendance module (hr_attendance) to compare "
                    "field time with HR attendance."
                )
            )
        self.line_ids.unlink()

        start = datetime.combine(self.date_from, time.min)
        end = datetime.combine(self.date_to, time.max)
        line_model = self.env["field.operation.time.line"]
        attendance_model = self.env["hr.attendance"]

        employees = self.employee_ids
        if not employees:
            employees = (
                line_model.search(
                    [
                        ("company_id", "=", self.company_id.id),
                        ("date", ">=", self.date_from),
                        ("date", "<=", self.date_to),
                    ]
                ).employee_id
                | attendance_model.search(
                    [
                        ("employee_id.company_id", "=", self.company_id.id),
                        ("check_in", ">=", start),
                        ("check_in", "<=", end),
                    ]
                ).employee_id
            )

        vals_list = []
        for employee in employees:
            lines = line_model.search(
                [
                    ("employee_id", "=", employee.id),
                    ("date", ">=", self.date_from),
                    ("date", "<=", self.date_to),
                    ("operation_id.company_id", "=", self.company_id.id),
                ]
            )
            approved = sum(
                lines.filtered(lambda rec: rec.state == "approved").mapped("duration")
            )
            draft = sum(
                lines.filtered(lambda rec: rec.state == "draft").mapped("duration")
            )
            attendance = sum(
                attendance_model.search(
                    [
                        ("employee_id", "=", employee.id),
                        ("check_in", ">=", start),
                        ("check_in", "<=", end),
                    ]
                ).mapped("worked_hours")
            )
            vals_list.append(
                {
                    "wizard_id": self.id,
                    "employee_id": employee.id,
                    "timesheet_hours": approved,
                    "draft_hours": draft,
                    "attendance_hours": attendance,
                    "difference": approved - attendance,
                }
            )
        if vals_list:
            self.env["field.operation.timesheet.reconciliation.line"].create(vals_list)

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }
