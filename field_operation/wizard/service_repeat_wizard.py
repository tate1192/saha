# service_repeat_wizard.py

import logging
from datetime import datetime, time
from itertools import islice

import pytz
from dateutil import rrule

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

#: Upper bound on the operations one run may generate, overridable with the
#: ``max_recurring_operations`` context key.
DEFAULT_MAX_OPERATIONS = 500


class ServiceRepeatWizard(models.TransientModel):
    _name = "service.repeat.wizard"
    _description = "Service Repeat Wizard"

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        help="Customer for whom the recurring services will be scheduled",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    subject = fields.Char(string="Subject", required=True, default="Scheduled Service")
    service_type_id = fields.Many2one("field.operation.type", string="Service Type")

    # Recurrence settings
    dtstart = fields.Date(string="Start Date", required=True, default=fields.Date.today)
    rrule_freq = fields.Selection(
        [
            ("yearly", "Yearly"),
            ("monthly", "Monthly"),
            ("weekly", "Weekly"),
            ("daily", "Daily"),
        ],
        string="Frequency",
        default="monthly",
        required=True,
    )

    rrule_interval = fields.Integer(string="Interval", default=1, required=True)
    rrule_byweekday = fields.Selection(
        [
            ("MO", "Monday"),
            ("TU", "Tuesday"),
            ("WE", "Wednesday"),
            ("TH", "Thursday"),
            ("FR", "Friday"),
            ("SA", "Saturday"),
            ("SU", "Sunday"),
        ],
        string="On Weekday",
    )

    rrule_month_by = fields.Selection(
        [("date", "Day of the month"), ("day", "Day of the week")],
        string="Monthly Repeat By",
        default="date",
    )

    rrule_bymonthday = fields.Integer(
        string="Day of Month",
        compute="_compute_rrule_bymonthday",
        store=True,
        readonly=False,
        precompute=True,
        help="Enter a day from 1 to 31. It follows the start date, and the "
        "recurrence uses it as soon as you edit it.",
    )
    rrule_bysetpos = fields.Selection(
        [
            ("1", "First"),
            ("2", "Second"),
            ("3", "Third"),
            ("4", "Fourth"),
            ("-1", "Last"),
        ],
        string="Which Occurrence",
    )
    rrule_byweekday_pos = fields.Selection(
        [
            ("MO", "Monday"),
            ("TU", "Tuesday"),
            ("WE", "Wednesday"),
            ("TH", "Thursday"),
            ("FR", "Friday"),
            ("SA", "Saturday"),
            ("SU", "Sunday"),
        ],
        string="Weekday for Positional Repeat",
    )

    # End condition
    rrule_end_type = fields.Selection(
        [("count", "After a number of occurrences"), ("until", "On a specific date")],
        string="End Repetition",
        default="count",
        required=True,
    )

    rrule_count = fields.Integer(string="Number of Occurrences", default=10)
    rrule_until = fields.Date(string="End Date")

    # Visibility flags
    show_rrule_count = fields.Boolean(compute="_compute_visibility_flags")
    require_rrule_count = fields.Boolean(compute="_compute_visibility_flags")
    show_rrule_until = fields.Boolean(compute="_compute_visibility_flags")
    require_rrule_until = fields.Boolean(compute="_compute_visibility_flags")
    show_weekly_options = fields.Boolean(compute="_compute_visibility_flags")
    show_monthly_options = fields.Boolean(compute="_compute_visibility_flags")
    show_monthly_day_options = fields.Boolean(compute="_compute_visibility_flags")
    show_monthly_date_options = fields.Boolean(compute="_compute_visibility_flags")
    require_monthly_date_options = fields.Boolean(compute="_compute_visibility_flags")
    require_monthly_day_options = fields.Boolean(compute="_compute_visibility_flags")

    @api.depends("rrule_end_type", "rrule_freq", "rrule_month_by")
    def _compute_visibility_flags(self):
        for wizard in self:
            wizard.show_rrule_count = wizard.rrule_end_type == "count"
            wizard.require_rrule_count = wizard.rrule_end_type == "count"
            wizard.show_rrule_until = wizard.rrule_end_type == "until"
            wizard.require_rrule_until = wizard.rrule_end_type == "until"
            wizard.show_weekly_options = wizard.rrule_freq == "weekly"
            wizard.show_monthly_options = wizard.rrule_freq == "monthly"
            wizard.show_monthly_date_options = (
                wizard.rrule_freq == "monthly" and wizard.rrule_month_by == "date"
            )
            wizard.require_monthly_date_options = (
                wizard.rrule_freq == "monthly" and wizard.rrule_month_by == "date"
            )
            wizard.show_monthly_day_options = (
                wizard.rrule_freq == "monthly" and wizard.rrule_month_by == "day"
            )
            wizard.require_monthly_day_options = (
                wizard.rrule_freq == "monthly" and wizard.rrule_month_by == "day"
            )

    @api.depends("dtstart")
    def _compute_rrule_bymonthday(self):
        """Recur on the day of the start date, not on the day of today.

        The default used to be ``today.day``: a monthly rule starting on the 1st
        generated its operations on the 11th whenever today is the 11th.
        """
        for wizard in self:
            day_of = wizard.dtstart or fields.Date.context_today(wizard)
            wizard.rrule_bymonthday = day_of.day

    @api.constrains("rrule_interval")
    def _check_interval(self):
        for record in self:
            if record.rrule_interval <= 0:
                raise ValidationError(_("Interval must be a positive number."))

    @api.constrains("rrule_bymonthday", "rrule_freq", "rrule_month_by")
    def _check_bymonthday(self):
        for record in self:
            if record.rrule_freq == "monthly" and record.rrule_month_by == "date":
                if not (1 <= record.rrule_bymonthday <= 31):
                    raise ValidationError(
                        _(
                            "For monthly repetition by date, 'Day of Month' must be "
                            "between 1 and 31."
                        )
                    )

    @api.constrains("rrule_count", "rrule_end_type")
    def _check_rrule_count(self):
        for record in self:
            if record.rrule_end_type == "count" and record.rrule_count <= 0:
                raise ValidationError(
                    _(
                        "Number of occurrences must be positive if 'End Repetition' "
                        "is by count."
                    )
                )

    @api.constrains("dtstart", "rrule_until", "rrule_end_type")
    def _check_rrule_until_date(self):
        for record in self:
            if record.rrule_end_type == "until":
                if not record.rrule_until:
                    raise ValidationError(
                        _("End Date is required if 'End Repetition' is by date.")
                    )
                if record.dtstart and record.rrule_until < record.dtstart:
                    raise ValidationError(
                        _("End Date cannot be earlier than the Start Date.")
                    )

    def _prepare_rrule_params(self):
        self.ensure_one()
        params = {}
        freq_map = {
            "daily": rrule.DAILY,
            "weekly": rrule.WEEKLY,
            "monthly": rrule.MONTHLY,
            "yearly": rrule.YEARLY,
        }
        params["freq"] = freq_map[self.rrule_freq]
        start_datetime = datetime.combine(self.dtstart, time.min)
        params["dtstart"] = start_datetime

        if self.rrule_interval > 0:
            params["interval"] = self.rrule_interval

        if self.rrule_end_type == "count" and self.rrule_count > 0:
            params["count"] = self.rrule_count
        elif self.rrule_end_type == "until" and self.rrule_until:
            until_datetime = datetime.combine(self.rrule_until, time.max)
            params["until"] = until_datetime

        # Weekly options
        if self.rrule_freq == "weekly" and self.rrule_byweekday:
            weekday_map = {
                "MO": rrule.MO,
                "TU": rrule.TU,
                "WE": rrule.WE,
                "TH": rrule.TH,
                "FR": rrule.FR,
                "SA": rrule.SA,
                "SU": rrule.SU,
            }
            params["byweekday"] = [weekday_map[self.rrule_byweekday]]

        # Monthly options
        if self.rrule_freq == "monthly":
            if self.rrule_month_by == "date":
                params["bymonthday"] = self.rrule_bymonthday or self.dtstart.day
            elif self.rrule_month_by == "day":
                if self.rrule_bysetpos and self.rrule_byweekday_pos:
                    weekday_map_pos = {
                        "MO": rrule.MO,
                        "TU": rrule.TU,
                        "WE": rrule.WE,
                        "TH": rrule.TH,
                        "FR": rrule.FR,
                        "SA": rrule.SA,
                        "SU": rrule.SU,
                    }
                    pos = int(self.rrule_bysetpos)
                    weekday_rrule_obj = weekday_map_pos.get(self.rrule_byweekday_pos)
                    if weekday_rrule_obj:
                        params["byweekday"] = weekday_rrule_obj(pos)
        return params

    def _local_to_utc(self, local_dt):
        """Convert a naive datetime in the user timezone to a naive UTC
        datetime, as expected by stored ``Datetime`` fields."""
        tz_name = self.env.context.get("tz") or self.env.user.tz or "UTC"
        local = pytz.timezone(tz_name).localize(local_dt, is_dst=False)
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    def _prepare_operation_values(self, operation_date):
        self.ensure_one()
        return {
            "name": "/",  # the sequence assigns the real reference
            "subject": self.subject,
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "user_id": self.user_id.id,
            "service_type_id": self.service_type_id.id
            if self.service_type_id
            else False,
            "start_date": self._local_to_utc(operation_date),
            "status": "planned",
        }

    def action_generate_operations(self):
        self.ensure_one()
        FieldOperation = self.env["field.operation"]
        operations_to_create_vals = []
        created_ops = self.env["field.operation"]

        try:
            rrule_params = self._prepare_rrule_params()
            if not rrule_params.get("dtstart"):
                raise UserError(_("Start date for recurrence is not properly set."))

            max_ops = int(
                self.env.context.get("max_recurring_operations", DEFAULT_MAX_OPERATIONS)
            )
            # islice, so the cap holds while the dates are produced: `count` is a
            # free integer on the wizard, and materialising all of a large one
            # exhausted the worker before any check could run (measured: 100000
            # dates built in 0.14s and only then rejected).
            generated_dates = list(islice(rrule.rrule(**rrule_params), max_ops + 1))

            if not generated_dates:
                raise UserError(
                    _(
                        "No dates could be generated with the given recurrence rules. "
                        "Please check your settings."
                    )
                )

            if len(generated_dates) > max_ops:
                raise UserError(
                    _(
                        "The current settings would generate more than %s operations. "
                        "Please adjust the recurrence rules or end condition."
                    )
                    % max_ops
                )

            for op_date in generated_dates:
                operations_to_create_vals.append(
                    self._prepare_operation_values(op_date)
                )

            if operations_to_create_vals:
                created_ops = FieldOperation.create(operations_to_create_vals)

                # Post a note in the chatter
                self.env["mail.message"].create(
                    {
                        "body": _(
                            "%s recurring operations were generated successfully."
                        )
                        % len(created_ops),
                        "model": "field.operation",
                        "res_id": created_ops[0].id if created_ops else False,
                        "message_type": "notification",
                    }
                )

        except (UserError, ValidationError):
            raise
        except Exception as e:
            # Log the traceback: the UserError below is all the user sees.
            _logger.exception("Recurring operation generation failed")
            raise UserError(
                _(
                    "An unexpected error occurred while generating recurring "
                    "operations: %s"
                )
                % str(e)
            ) from e

        if created_ops:
            action = self.env["ir.actions.actions"]._for_xml_id(
                "field_operation.action_field_operation"
            )
            action["domain"] = [("id", "in", created_ops.ids)]
            action["display_name"] = _("Generated Operations (%s)") % len(created_ops)
            return action
        else:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Operations Generated"),
                    "message": _(
                        "No operations were generated based on the provided "
                        "recurrence rules."
                    ),
                    "sticky": False,
                    "type": "warning",
                },
            }
