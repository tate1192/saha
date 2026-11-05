# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

LEAVE_SERVICE = "leave"


class FieldOperation(models.Model):
    _inherit = "field.operation"

    leave_id = fields.Many2one(
        "hr.leave",
        string="Time Off",
        ondelete="cascade",
        index=True,
        copy=False,
        readonly=True,
    )
    is_leave_marker = fields.Boolean(
        string="Leave Marker",
        compute="_compute_is_leave_marker",
        store=True,
        help="Set on the operations generated for an approved employee leave.",
    )

    @api.depends("service_type_id.type")
    def _compute_is_leave_marker(self):
        for operation in self:
            operation.is_leave_marker = operation.service_type_id.type == LEAVE_SERVICE

    @api.constrains("person_ids", "start_date", "end_date", "status")
    def _check_team_integrity(self):
        """Keep the base check for real services and skip the leave markers.

        A marker exists precisely because its employee is on leave, so the base
        check ("is on leave and cannot be assigned on these dates") would refuse
        every marker it is meant to describe.
        """
        super(
            FieldOperation,
            self.filtered(
                lambda operation: operation.service_type_id.type != LEAVE_SERVICE
            ),
        )._check_team_integrity()

    def _check_leave_conflicts(self):
        """Refuse a service planned while one of its employees is on leave.

        This is the ``hr.leave`` half of ``_check_team_integrity``, moved here
        when the core module dropped its ``hr_holidays`` dependency. The leave
        lookup is batched: one query for every involved employee, whatever the
        number of records being checked.
        """
        employees = self.mapped("person_ids")
        leaves = self.env["hr.leave"].search(
            [
                ("employee_id", "in", employees.ids),
                ("state", "=", "validate"),
            ]
        )
        for operation in self:
            date_from, date_to = operation.start_date.date(), operation.end_date.date()
            leave = leaves.filtered(
                lambda leave,
                df=date_from,
                dt=date_to,
                emps=operation.person_ids: leave.employee_id in emps
                and leave.request_date_from
                and leave.request_date_to
                and leave.request_date_from <= dt
                and leave.request_date_to >= df
            )[:1]
            if leave:
                raise ValidationError(
                    _(
                        "%(employee)s is on leave/sick leave (%(leave_type)s) "
                        "and cannot be assigned on these dates."
                    )
                    % {
                        "employee": leave.employee_id.name,
                        "leave_type": leave.holiday_status_id.display_name,
                    }
                )
