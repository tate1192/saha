# Copyright(C) 2025 - Today Softteknik Bilişim
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

# Single source of truth for maintenance types: the maintenance record and the
# periodic schedule share the same selection so a scheduled record can never
# carry a type the maintenance model does not know.
MAINTENANCE_TYPE_SELECTION = [
    ("preventive", "Preventive Maintenance"),
    ("corrective", "Corrective Maintenance"),
    ("periodic", "Periodic Check"),
    ("emergency", "Emergency Repair"),
    ("installation", "Installation"),
    ("inspection", "Inspection"),
]


class MachineMaintenance(models.Model):
    _name = "machine.maintenance"
    _description = "Machine Maintenance Record"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc"

    name = fields.Char(string="Reference", default="/", readonly=True, copy=False)
    machine_id = fields.Many2one(
        "machine.master", string="Machine", required=True, tracking=True
    )
    partner_id = fields.Many2one(
        "res.partner", string="Customer", related="machine_id.partner_id", store=True
    )
    maintenance_type = fields.Selection(
        MAINTENANCE_TYPE_SELECTION,
        string="Maintenance Type",
        default="preventive",
        tracking=True,
    )
    date = fields.Date(
        string="Date",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    next_maintenance_date = fields.Date(string="Next Maintenance Date", tracking=True)
    days_until_next = fields.Integer(
        string="Days Until Next", compute="_compute_days_until_next"
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("done", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    priority = fields.Selection(
        [
            ("0", "Low"),
            ("1", "Normal"),
            ("2", "High"),
            ("3", "Urgent"),
        ],
        string="Priority",
        default="1",
        tracking=True,
    )
    description = fields.Html(string="Description")
    work_performed = fields.Html(string="Work Performed")
    result = fields.Selection(
        [
            ("success", "Successful"),
            ("partial", "Partially Completed"),
            ("failed", "Failed"),
        ],
        string="Result",
    )

    operation_id = fields.Many2one("field.operation", string="Service Operation")
    technician_id = fields.Many2one("hr.employee", string="Technician", tracking=True)
    technician_user_id = fields.Many2one(
        "res.users",
        string="Technician User",
        related="technician_id.user_id",
        store=True,
    )
    duration_hours = fields.Float(string="Duration (Hours)")
    labor_cost = fields.Monetary(
        string="Labor Cost",
        currency_field="currency_id",
        groups="field_operation.service_group_user",
    )
    parts_cost = fields.Monetary(
        string="Parts Cost",
        compute="_compute_parts_cost",
        store=True,
        currency_field="currency_id",
        groups="field_operation.service_group_user",
    )
    total_cost = fields.Monetary(
        string="Total Cost",
        compute="_compute_total_cost",
        store=True,
        currency_field="currency_id",
        groups="field_operation.service_group_user",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    # Spare parts consumed for this maintenance; the inverse is
    # machine.spare.part.maintenance_id.
    spare_part_ids = fields.One2many(
        "machine.spare.part", "maintenance_id", string="Spare Parts"
    )
    # Traceability back to the schedule that generated this record.
    schedule_id = fields.Many2one(
        "machine.maintenance.schedule", string="Schedule", copy=False
    )
    internal_notes = fields.Text(string="Internal Notes")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )

    image_before = fields.Binary(string="Before Image", attachment=True)
    image_after = fields.Binary(string="After Image", attachment=True)

    @api.depends("spare_part_ids.subtotal")
    def _compute_parts_cost(self):
        # Depend on the related subfield, not on the one2many name, so editing a
        # spare part line retriggers the computation.
        for rec in self:
            rec.parts_cost = sum(rec.spare_part_ids.mapped("subtotal"))

    @api.depends("labor_cost", "parts_cost")
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = (rec.labor_cost or 0) + (rec.parts_cost or 0)

    @api.depends("next_maintenance_date")
    def _compute_days_until_next(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.next_maintenance_date:
                rec.days_until_next = (rec.next_maintenance_date - today).days
            else:
                rec.days_until_next = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("machine.maintenance") or "/"
                )
        return super().create(vals_list)

    def _check_service_user(self):
        # State transitions are limited to the service user group, which is the
        # group the ACLs grant write access to.
        if not self.env.user.has_group("field_operation.service_group_user"):
            raise AccessError(
                _("Only service users are allowed to change the maintenance state.")
            )

    def _check_source_state(self, allowed_states):
        # Guard the state machine so records cannot skip or reopen a step.
        labels = dict(self._fields["state"].selection)
        for rec in self:
            if rec.state not in allowed_states:
                raise UserError(
                    _("This action is not allowed from state '%s'.")
                    % labels.get(rec.state, rec.state)
                )

    # Actions
    def action_schedule(self):
        self._check_service_user()
        self._check_source_state(["draft"])
        self.write({"state": "scheduled"})

    def action_start(self):
        self._check_service_user()
        self._check_source_state(["draft", "scheduled"])
        self.write({"state": "in_progress"})

    def action_done(self):
        self._check_service_user()
        self._check_source_state(["scheduled", "in_progress"])
        for rec in self:
            rec.state = "done"
            # Schedule the next visit for recurring maintenance types.
            if (
                rec.maintenance_type in ("preventive", "periodic")
                and not rec.next_maintenance_date
            ):
                # Default to a three month horizon for periodic maintenance.
                today = fields.Date.context_today(rec)
                rec.next_maintenance_date = today + timedelta(days=90)

    def action_cancel(self):
        self._check_service_user()
        self._check_source_state(["draft", "scheduled", "in_progress"])
        self.write({"state": "cancelled"})

    # Cron for maintenance reminders
    @api.model
    def _cron_notify_upcoming_maintenance(self):
        """Notify for maintenance due within the next 7 days."""
        today = fields.Date.context_today(self)
        reminder_date = today + timedelta(days=7)
        records = self.search(
            [
                ("next_maintenance_date", "<=", reminder_date),
                ("next_maintenance_date", ">=", today),
                ("state", "=", "done"),
            ]
        )
        for rec in records:
            # Notify the machine owner, falling back to the cron user.
            machine = rec.machine_id
            machine.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=machine.partner_id.user_id.id or self.env.user.id,
                note=_("Scheduled maintenance for %s on %s")
                % (machine.display_name, rec.next_maintenance_date),
            )


class MaintenanceSchedule(models.Model):
    _name = "machine.maintenance.schedule"
    _description = "Periodic Maintenance Schedule"

    name = fields.Char(string="Name", required=True)
    machine_id = fields.Many2one("machine.master", string="Machine", required=True)
    interval_type = fields.Selection(
        [
            ("days", "Days"),
            ("weeks", "Weeks"),
            ("months", "Months"),
            ("years", "Years"),
        ],
        string="Interval Type",
        default="months",
    )
    interval_number = fields.Integer(string="Interval", default=3)

    next_date = fields.Date(string="Next Maintenance Date", required=True)
    last_date = fields.Date(string="Last Maintenance Date")
    maintenance_type = fields.Selection(
        MAINTENANCE_TYPE_SELECTION,
        string="Maintenance Type",
        default="preventive",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )

    _interval_number_positive = models.Constraint(
        "CHECK (interval_number > 0)",
        "The interval number must be strictly positive.",
    )

    def _next_date_from(self, base_date):
        # Use calendar-aware arithmetic (relativedelta) instead of fixed 30/365
        # day approximations for month and year intervals.
        self.ensure_one()
        number = self.interval_number
        if self.interval_type == "days":
            return base_date + relativedelta(days=number)
        if self.interval_type == "weeks":
            return base_date + relativedelta(weeks=number)
        if self.interval_type == "months":
            return base_date + relativedelta(months=number)
        return base_date + relativedelta(years=number)

    @api.model
    def _cron_generate_maintenance(self):
        """Generate maintenance records from schedules."""
        today = fields.Date.context_today(self)
        for schedule in self.search([("next_date", "<=", today)]):
            self.env["machine.maintenance"].create(
                {
                    "machine_id": schedule.machine_id.id,
                    "maintenance_type": schedule.maintenance_type,
                    "date": today,
                    "state": "scheduled",
                    "name": "/",
                    "schedule_id": schedule.id,
                }
            )
            # Advance from the schedule's own next_date, not from today, so a
            # delayed cron run does not shift the cadence.
            previous_next = schedule.next_date
            schedule.last_date = today
            schedule.next_date = schedule._next_date_from(previous_next)
