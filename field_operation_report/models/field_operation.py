# field_operation_report/models/field_operation.py

from datetime import timezone
from zoneinfo import ZoneInfo

from odoo import api, fields, models


class FieldOperation(models.Model):
    _inherit = "field.operation"

    report_date = fields.Date(
        string="Report Date",
        compute="_compute_report_date",
        store=True,
        index=True,
        help="Calendar day of the planned start, in the company timezone, used "
        "to group services by day, week or month. Falls back to the creation "
        "date when no start date is set.",
    )
    person_count = fields.Integer(
        string="Team Size",
        compute="_compute_person_count",
        store=True,
        help="Number of staff assigned to the service.",
    )
    duration_per_person = fields.Float(
        string="Duration per Person (hours)",
        compute="_compute_duration_per_person",
        store=True,
        help="Worked hours (the core 'Total Work' value) divided by the number "
        "of staff assigned to the service.",
    )

    def _report_timezone(self):
        """Timezone used to cut the calendar day of ``report_date``.

        A stored compute must not depend on the request context, so the company
        timezone is used instead of the user one: the stored day is the same for
        everybody and does not change when another user recomputes the field.
        """
        tz_name = self.env.company.partner_id.tz or "UTC"
        try:
            return ZoneInfo(tz_name)
        except Exception:  # unknown / misspelled timezone on the company
            return timezone.utc

    @api.depends("start_date", "create_date")
    def _compute_report_date(self):
        tz = self._report_timezone()
        for operation in self:
            moment = operation.start_date or operation.create_date
            operation.report_date = (
                moment.replace(tzinfo=timezone.utc).astimezone(tz).date()
                if moment
                else False
            )

    @api.depends("person_ids")
    def _compute_person_count(self):
        for operation in self:
            operation.person_count = len(operation.person_ids)

    @api.depends("total_work", "person_count")
    def _compute_duration_per_person(self):
        for operation in self:
            operation.duration_per_person = (
                round(operation.total_work / operation.person_count, 2)
                if operation.person_count
                else 0.0
            )
