# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models


class HrLeave(models.Model):
    _inherit = "hr.leave"

    operation_ids = fields.One2many(
        "field.operation",
        "leave_id",
        string="Leave Operations",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        leaves._sync_leave_operations()
        return leaves

    def write(self, vals):
        res = super().write(vals)
        if {"state", "date_from", "date_to", "employee_id"} & set(vals):
            self._sync_leave_operations()
        return res

    def _sync_leave_operations(self):
        """Rebuild the operations of each leave: one operation per leave day.

        The operations are touched as sudo on purpose: the user who approves or
        cancels a leave (HR) usually has no create/unlink right on
        ``field.operation`` - the field workers only have read - and the
        generated records are derived data, not hand-written ones.
        """
        operations = self.env["field.operation"].sudo()
        for leave in self:
            operations.search([("leave_id", "=", leave.id)]).unlink()
            if leave.state == "validate" and leave.employee_id:
                leave._create_leave_operations()

    def _leave_day_ranges(self):
        """Split the leave into one (start, end) range per local calendar day.

        ``date_from``/``date_to`` are UTC, the days a planner sees are local:
        cutting at UTC midnight would turn the middle days into 24h UTC blocks
        (in Istanbul 03:00 -> 02:59 the next day) and leave the morning of the
        first day uncovered. The boundaries therefore come from the leave
        timezone (``leave.tz``) and are converted back to UTC.
        """
        self.ensure_one()
        tz = pytz.timezone(self.tz or "UTC")
        day = pytz.utc.localize(self.date_from).astimezone(tz).date()
        last_day = pytz.utc.localize(self.date_to).astimezone(tz).date()
        ranges = []
        while day <= last_day:
            day_start = (
                tz.localize(datetime.combine(day, time.min))
                .astimezone(pytz.utc)
                .replace(tzinfo=None)
            )
            day_end = (
                tz.localize(datetime.combine(day, time.max))
                .astimezone(pytz.utc)
                .replace(tzinfo=None)
            )
            start = max(self.date_from, day_start)
            end = min(self.date_to, day_end)
            if start < end:
                ranges.append((start, end))
            day += timedelta(days=1)
        return ranges

    def _create_leave_operations(self):
        self.ensure_one()
        service_type = self.env.ref(
            "field_operation_holiday.operation_type_leave", raise_if_not_found=False
        )
        if not service_type:
            return
        start = fields.Datetime.context_timestamp(self, self.date_from)
        end = fields.Datetime.context_timestamp(self, self.date_to)
        # Read the type as sudo: leave types are not visible to every approver,
        # and the marker text still needs its name.
        leave_type_name = self.holiday_status_id.sudo().display_name
        subject = _(
            "On leave: %(employee)s (%(leave_type)s)",
            employee=self.employee_id.name,
            leave_type=leave_type_name,
        )
        description = _(
            "<p>%(employee)s is on approved leave from %(start)s to %(end)s.</p>",
            employee=self.employee_id.name,
            start=start.strftime("%d.%m.%Y %H:%M"),
            end=end.strftime("%d.%m.%Y %H:%M"),
        )
        values = [
            {
                "subject": subject,
                "description": description,
                "service_type_id": service_type.id,
                "person_ids": [(6, 0, self.employee_id.ids)],
                "start_date": day_start,
                "end_date": day_end,
                "status": "planned",
                "leave_id": self.id,
            }
            for day_start, day_end in self._leave_day_ranges()
        ]
        if values:
            self.env["field.operation"].with_company(self.company_id).sudo().create(
                values
            )
