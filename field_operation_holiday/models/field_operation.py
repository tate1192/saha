# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import api, fields, models

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
