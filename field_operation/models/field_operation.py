# field_operation/models/field_operation.py

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

STATUS = [
    ("draft", "Draft"),
    ("planned", "Planned"),
    ("progress", "Progress"),
    ("done", "Done"),
    ("cancel", "Cancel"),
]


class FieldOperation(models.Model):
    _name = "field.operation"
    _description = "Field Operation"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "create_date desc"
    _check_company_auto = True

    @api.onchange("team_id")
    def _get_team_members(self):
        if self.team_id:
            self.person_ids = self.team_id.team_members_ids
            self.team_leader_id = self.team_id.team_leader_id
            self.team_head = self.team_id.team_head_id
        else:
            self.person_ids = False
            self.team_leader_id = False
            self.team_head = False

    @api.model
    def search_panel_select_range(self, field_name, **kwargs):
        """Keep archived teams out of the search panel's team category.

        The web client groups the operations by ``team_id`` and lists every
        value it finds, so one operation left pointing at an archived team keeps
        that team in the panel forever. Passing a ``comodel_domain`` makes the
        panel read the teams themselves with the active filter instead of
        trusting the group image.
        """
        if field_name == "team_id":
            kwargs["comodel_domain"] = [("active", "=", True)] + list(
                kwargs.get("comodel_domain") or []
            )
        return super().search_panel_select_range(field_name, **kwargs)

    def _get_default_currency(self):
        return self.env.company.currency_id

    name = fields.Char(string="Reference", default="/", index=True)
    subject = fields.Char(string="Subject")
    district_id = fields.Char(
        string="District", related="partner_id.city", store=True, index=True
    )
    description = fields.Html(string="Description")
    solution = fields.Html(string="Solution")
    active = fields.Boolean(string="Active", default=True)
    start_date = fields.Datetime(string="Start Date", tracking=True, index=True)
    end_date = fields.Datetime(string="End Date", index=True)
    close_date = fields.Datetime(string="Close Date")
    color = fields.Integer(default=0)
    sequence = fields.Integer(default=10)
    service_price = fields.Monetary(
        string="Prices", tracking=True, currency_field="currency_id"
    )
    total_work = fields.Float(
        compute="_compute_total_work", string="Total Work", store=True, readonly=True
    )

    signed = fields.Boolean(string="Signed", copy=False)
    signed_on = fields.Datetime(string="Signature Date", copy=False)
    form_signature = fields.Binary(string="Signature", copy=False, attachment=True)
    signed_by = fields.Char(string="Signature Name", copy=False)
    staff_signature = fields.Binary(
        string="Staff Signature", copy=False, attachment=True
    )
    staff_signed_by = fields.Char(string="Staff Name", copy=False)

    currency_id = fields.Many2one(
        "res.currency", string="Currency", default=_get_default_currency
    )
    partner_id = fields.Many2one(
        "res.partner", string="Customer", index=True, tracking=True
    )
    contact_id = fields.Many2one(
        "res.partner",
        string="Contact",
        compute="_compute_service_contact",
        store=True,
        readonly=False,
    )
    contact_mobile = fields.Char(
        string="Phone",
        related="contact_id.phone",
        store=True,
        readonly=True,
        help="Read-only mirror of the contact's phone. Correct the number on "
        "the contact record: a writable related field would silently rewrite "
        "the partner's phone for every document.",
    )
    address_id = fields.Many2one(
        "res.partner",
        string="Service Address",
        compute="_compute_service_address",
        store=True,
        readonly=False,
    )
    service_latitude = fields.Float(
        string="Latitude",
        compute="_compute_service_coordinates",
        store=True,
        digits=(10, 7),
    )
    service_longitude = fields.Float(
        string="Longitude",
        compute="_compute_service_coordinates",
        store=True,
        digits=(10, 7),
    )
    date_localization = fields.Datetime(
        string="Geolocation Date",
        readonly=True,
        help="Set when the service address coordinates are captured.",
    )
    service_type_id = fields.Many2one("field.operation.type", string="Service Type")
    region_id = fields.Many2one(
        "field.operation.region",
        string="Region",
        related="team_id.region_id",
        store=True,
        readonly=True,
    )
    team_id = fields.Many2one(
        "field.operation.team", string="Service Team", tracking=True
    )
    team_head = fields.Many2one("hr.employee", string="Team Head", tracking=True)
    team_leader_id = fields.Many2one("res.users", string="Team Leader", tracking=True)
    person_ids = fields.Many2many(
        "hr.employee",
        relation="field_operation_person_rel",
        column1="operation_id",
        column2="employee",
        string="Assigned Person",
        tracking=True,
    )

    user_id = fields.Many2one(
        "res.users",
        string="Created",
        default=lambda self: self.env.user,
        check_company=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        readonly=True,
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    priority = fields.Selection(
        [
            ("0", "Low"),
            ("1", "High"),
        ],
        default="0",
        index=True,
        string="Priority",
        tracking=True,
    )
    tag_ids = fields.Many2many("field.operation.tags", string="Tags")
    status = fields.Selection(
        selection=STATUS,
        string="Status",
        default="draft",
        tracking=True,
    )

    def _compute_access_url(self):
        for record in self:
            record.access_url = f"/my/operation_detail/{record.id}"

    @api.constrains("person_ids", "start_date", "end_date", "status")
    def _check_team_integrity(self):
        """Refuse a service planned while a member is on leave or busy elsewhere.

        The two lookups are batched: one query for the validated leaves and one
        for the competing services of every involved employee, whatever the
        number of records being written.
        """
        checked = self.filtered(
            lambda rec: rec.person_ids
            and rec.start_date
            and rec.end_date
            and rec.status in ("planned", "progress")
        )
        if not checked:
            return

        employees = checked.mapped("person_ids")
        leaves = self.env["hr.leave"].search(
            [
                ("employee_id", "in", employees.ids),
                ("state", "=", "validate"),
            ]
        )
        for rec in checked:
            date_from, date_to = rec.start_date.date(), rec.end_date.date()
            leave = leaves.filtered(
                lambda leave,
                df=date_from,
                dt=date_to,
                emps=rec.person_ids: leave.employee_id in emps
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

        competitors = self.search(
            [
                ("id", "not in", checked.ids),
                ("status", "in", ["planned", "progress"]),
                ("person_ids", "in", employees.ids),
            ]
        )
        for rec in checked:
            overlap = competitors.filtered(
                lambda other, rec=rec: other.person_ids & rec.person_ids
                and other.start_date
                and other.end_date
                and other.start_date <= rec.end_date
                and other.end_date >= rec.start_date
            )[:1]
            if overlap:
                # Common employees as a recordset: no closure over the loop variable.
                assigned = overlap.person_ids & rec.person_ids
                raise ValidationError(
                    _(
                        "%s is already assigned to job %s (%s - %s). There cannot "
                        "be another job during the same time period."
                    )
                    % (
                        assigned[:1].name or rec.person_ids[:1].name,
                        overlap.name,
                        overlap.start_date.strftime("%d-%m %H:%M"),
                        overlap.end_date.strftime("%H:%M"),
                    )
                )

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(_("End date cannot be before start date."))

    @api.constrains("service_price")
    def _check_price(self):
        for rec in self:
            if rec.service_price < 0:
                raise ValidationError(_("Service price cannot be negative."))

    @api.onchange("staff_signature")
    def _onchange_staff_signature(self):
        for rec in self:
            if rec.staff_signature and not rec.signed_on:
                rec.signed_on = fields.Datetime.now()
                rec.signed = True
                if not rec.staff_signed_by:
                    rec.staff_signed_by = rec.team_leader_id.name

    def portal_signature(self):
        return not self.form_signature

    def action_portal_operation(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "target": "current",
            "url": self.get_portal_url(),
        }

    # ------------
    # Compute
    # ------------
    @api.depends("start_date", "end_date")
    def _compute_total_work(self):
        for work in self:
            if work.start_date and work.end_date:
                delta = work.end_date - work.start_date
                work.total_work = delta.total_seconds() / 3600.0
            else:
                work.total_work = 0.0

    @api.depends("partner_id")
    def _compute_service_address(self):
        for order in self:
            order.address_id = (
                order.partner_id.address_get(["delivery"])["delivery"]
                if order.partner_id
                else False
            )

    @api.depends("partner_id", "address_id")
    def _compute_service_contact(self):
        for order in self:
            contact = False
            if order.address_id:
                contact = order.address_id.address_get(["contact"])["contact"]
                contact = order.env["res.partner"].browse(contact)
                if contact.is_company:
                    contact = False
            if not contact and order.partner_id:
                contact = order.partner_id.address_get(["contact"])["contact"]
                contact = order.env["res.partner"].browse(contact)
                if contact.is_company:
                    contact = False
            order.contact_id = contact

    @api.depends("address_id.partner_latitude", "address_id.partner_longitude")
    def _compute_service_coordinates(self):
        for operation in self:
            operation.service_latitude = operation.address_id.partner_latitude
            operation.service_longitude = operation.address_id.partner_longitude

    # ---------------------------------------------------
    # CRUD
    # ---------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self._prepare_number(vals)
        operations = super().create(vals_list)
        operations._invalidate_partner_counts(operations.mapped("partner_id"))
        return operations

    def write(self, vals):
        has_staff_signature = bool(vals.get("staff_signature"))
        if has_staff_signature:
            if "signed_on" not in vals:
                vals["signed_on"] = fields.Datetime.now()
            if "signed" not in vals:
                vals["signed"] = True
            if "staff_signed_by" not in vals and vals.get("team_leader_id"):
                vals["staff_signed_by"] = (
                    self.env["res.users"].browse(vals["team_leader_id"]).name
                )

        partners_to_update = self.env["res.partner"]
        if "partner_id" in vals:
            partners_to_update = self.mapped("partner_id")

        res = super().write(vals)

        if "partner_id" in vals:
            self._invalidate_partner_counts(
                partners_to_update | self.mapped("partner_id")
            )

        if (
            has_staff_signature
            and "staff_signed_by" not in vals
            and not vals.get("team_leader_id")
        ):
            for rec in self.filtered(
                lambda r: r.team_leader_id and not r.staff_signed_by
            ):
                rec.staff_signed_by = rec.team_leader_id.name
        return res

    def unlink(self):
        partners = self.mapped("partner_id")
        res = super().unlink()
        self._invalidate_partner_counts(partners)
        return res

    def _invalidate_partner_counts(self, partners):
        """Mark the stored service counter of ``partners`` and their parents
        for recomputation (the counter aggregates child contacts too)."""
        partners = partners.filtered("id") if partners else partners
        if not partners:
            return
        targets = self.env["res.partner"].search([("id", "parent_of", partners.ids)])
        self.env.add_to_compute(
            self.env["res.partner"]._fields["field_operation_count"], targets
        )

    def _prepare_number(self, values):
        seq = self.env["ir.sequence"]
        if "company_id" in values:
            seq = seq.with_company(values["company_id"])
        return seq.next_by_code("field.operation") or "/"

    # ------------
    # Actions
    # ------------
    def action_send_report_mail(self):
        self.ensure_one()
        mail_template = self.env.ref(
            "field_operation.service_customer_delivery_mail", False
        )

        ctx = {
            "default_model": "field.operation",
            "default_res_ids": self.ids,
            "default_template_id": mail_template.id if mail_template else None,
            "default_composition_mode": "comment",
            "force_email": True,
        }

        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(False, "form")],
            "view_id": False,
            "target": "new",
            "context": ctx,
        }

    def action_draft(self):
        self._check_office_group("send a service back to draft")
        return self.write({"status": "draft"})

    def action_planned(self):
        return self.write({"status": "planned"})

    def action_progress(self):
        return self.write({"status": "progress"})

    def action_done(self):
        self.write({"status": "done"})
        # Done services drop out of the default list domain: go back to the list.
        return {
            "type": "ir.actions.act_window",
            "res_model": "field.operation",
            "view_mode": "list,form",
            "target": "current",
        }

    def action_cancel(self):
        self._check_office_group("cancel a service")
        return self.write({"status": "cancel"})

    def _check_office_group(self, action):
        """Enforce on the model what the form view already declares.

        ``action_cancel`` and ``action_draft`` are hidden from field workers in
        the form (``groups="field_operation.service_group_user"``); without the
        same check here the transitions stay reachable over RPC by anybody
        holding write access on ``field.operation``.
        """
        if not self.env.user.has_group("field_operation.service_group_user"):
            raise AccessError(_("Only office users are allowed to %s.", action))
