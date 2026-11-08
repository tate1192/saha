from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

AGREEMENT_STATUS = [
    ("draft", "Draft"),
    ("active", "Active"),
    ("expired", "Expired"),
    ("cancelled", "Cancelled"),
]

# Single module-level source for the agreement types so views, templates and
# other models can import the very same list instead of repeating it.
AGREEMENT_TYPE = [
    ("maintenance", "Maintenance"),
    ("service", "Service"),
    ("pest_control", "Pest Control"),
    ("other", "Other"),
]


class FieldOperationAgreement(models.Model):
    _name = "field.operation.agreement"
    _description = "Field Operation Agreement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_name = "reference"
    _check_company_auto = True

    # --- Reference & Basic Info ---
    reference = fields.Char(string="Reference", default="/", index=True, copy=False)
    name = fields.Char(string="Agreement Name", required=True, tracking=True)
    description = fields.Html(string="Terms & Conditions")
    active = fields.Boolean(string="Active", default=True)

    # --- Dates ---
    start_date = fields.Date(
        string="Start Date", required=True, tracking=True, index=True
    )
    end_date = fields.Date(string="End Date", required=True, tracking=True, index=True)
    is_expired = fields.Boolean(
        string="Expired",
        compute="_compute_is_expired",
        help="Set when the end date has passed or the agreement was expired.",
    )

    # --- Classification ---
    agreement_type = fields.Selection(
        selection=AGREEMENT_TYPE,
        string="Agreement Type",
        default="service",
        required=True,
        tracking=True,
    )
    status = fields.Selection(
        selection=AGREEMENT_STATUS,
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )

    # --- Financial ---
    total_amount = fields.Monetary(
        string="Total Amount",
        tracking=True,
        currency_field="currency_id",
        groups="field_operation.service_group_user",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # --- Relations ---
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        index=True,
        tracking=True,
        domain="[('is_company', '=', True)]",
    )
    contact_id = fields.Many2one(
        "res.partner",
        string="Contact Person",
        domain="[('parent_id', '=', partner_id)]",
    )
    field_operation_ids = fields.One2many(
        "field.operation",
        "agreement_id",
        string="Field Operations",
    )
    operation_count = fields.Integer(
        string="Operation Count",
        compute="_compute_operation_count",
        store=True,
    )

    # --- Signature ---
    signed = fields.Boolean(string="Signed", copy=False)
    signed_on = fields.Datetime(string="Signed On", copy=False)
    signature = fields.Binary(string="Signature", copy=False, attachment=True)
    signed_by = fields.Char(string="Signed By", copy=False)

    # --- Company ---
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        readonly=True,
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    # --- User ---
    user_id = fields.Many2one(
        "res.users",
        string="Created By",
        default=lambda self: self.env.user,
        check_company=True,
    )

    # --- Template ---
    template_id = fields.Many2one(
        "field.operation.agreement.template",
        string="Template",
        domain="[('agreement_type', '=', agreement_type), "
        "('company_id', 'in', [company_id, False]), "
        "('active', '=', True)]",
    )

    _reference_uniq = models.Constraint(
        "unique (reference)",
        "The agreement reference must be unique!",
    )

    # ============================================================
    # Compute
    # ============================================================

    @api.depends("field_operation_ids")
    def _compute_operation_count(self):
        for agreement in self:
            agreement.operation_count = len(agreement.field_operation_ids)

    @api.depends("end_date", "status")
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_expired = rec.status == "expired" or bool(
                rec.end_date and rec.end_date < today
            )

    # ============================================================
    # Constraints
    # ============================================================

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(_("End date cannot be before start date."))

    @api.constrains("total_amount")
    def _check_amount(self):
        for rec in self:
            if rec.total_amount and rec.total_amount < 0:
                raise ValidationError(_("Total amount cannot be negative."))

    @api.constrains("partner_id", "contact_id")
    def _check_contact_partner(self):
        for rec in self:
            if (
                rec.partner_id
                and rec.contact_id
                and rec.contact_id.parent_id != rec.partner_id
            ):
                raise ValidationError(
                    _("The contact person must belong to the selected customer.")
                )

    @api.constrains("signed", "signature", "signed_by", "signed_on")
    def _check_signature(self):
        for rec in self:
            if rec.signed and (not rec.signature or not rec.signed_by):
                raise ValidationError(
                    _(
                        "A signed agreement requires both a signature file and "
                        "the signer name."
                    )
                )

    # ============================================================
    # CRUD
    # ============================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", "/") == "/":
                reference = self.env["ir.sequence"].next_by_code(
                    "field.operation.agreement"
                )
                if not reference:
                    # A missing sequence would make every record share the "/"
                    # placeholder and break the unique constraint later on.
                    raise UserError(
                        _(
                            "The 'field.operation.agreement' sequence is missing; "
                            "the agreement reference cannot be generated."
                        )
                    )
                vals["reference"] = reference
        return super().create(vals_list)

    def write(self, vals):
        # Signing is one act: uploading the signature stamps the signer and the
        # signing date on the same write, like field.operation does.
        if vals.get("signature"):
            if "signed_on" not in vals:
                vals["signed_on"] = fields.Datetime.now()
            if "signed" not in vals:
                vals["signed"] = True
            if "signed_by" not in vals and not all(self.mapped("signed_by")):
                vals["signed_by"] = self.env.user.name
        return super().write(vals)

    def unlink(self):
        self._check_manager_group("delete an agreement")
        if self.field_operation_ids:
            raise UserError(
                _(
                    "You cannot delete an agreement that is still linked to "
                    "field operations. Detach them first."
                )
            )
        return super().unlink()

    # ============================================================
    # Cron
    # ============================================================

    @api.model
    def _cron_expire_agreements(self):
        """Expire every active agreement whose end date has passed.

        Scheduled daily; the whole batch is expired with a single bulk write so
        the transition no longer happens inside a constraint.
        """
        expired = self.search(
            [
                ("status", "=", "active"),
                ("end_date", "<", fields.Date.context_today(self)),
            ]
        )
        expired.write({"status": "expired"})

    # ============================================================
    # Security helpers
    # ============================================================

    def _check_office_group(self, action):
        """Enforce on the model what the views already declare.

        The state-transition buttons are hidden from field workers in the form
        (``groups="field_operation.service_group_user"``); without the same
        check here the transitions stay reachable over RPC by anybody holding
        write access on ``field.operation.agreement``.
        """
        if not self.env.user.has_group("field_operation.service_group_user"):
            raise AccessError(_("Only office users are allowed to %s.", action))

    def _check_manager_group(self, action):
        """Restrict the action to the Admin group (e.g. deletion)."""
        if not self.env.user.has_group("field_operation.service_group_manager"):
            raise AccessError(_("Only managers are allowed to %s.", action))

    # ============================================================
    # Actions
    # ============================================================

    def action_draft(self):
        self.ensure_one()
        self._check_office_group("send an agreement back to draft")
        if self.status == "draft":
            raise ValidationError(_("The agreement is already in draft."))
        return self.write({"status": "draft"})

    def action_activate(self):
        self.ensure_one()
        self._check_office_group("activate an agreement")
        if self.status not in ("draft", "expired"):
            raise ValidationError(
                _("Only a draft or expired agreement can be activated.")
            )
        if self.end_date and self.end_date < fields.Date.context_today(self):
            raise ValidationError(
                _(
                    "Cannot activate — agreement end date %(date)s has already passed.",
                    date=self.end_date,
                )
            )
        return self.write({"status": "active"})

    def action_expire(self):
        self.ensure_one()
        self._check_office_group("expire an agreement")
        if self.status != "active":
            raise ValidationError(_("Only an active agreement can be expired."))
        return self.write({"status": "expired"})

    def action_cancel(self):
        self.ensure_one()
        self._check_office_group("cancel an agreement")
        if self.status == "cancelled":
            raise ValidationError(_("The agreement is already cancelled."))
        return self.write({"status": "cancelled"})

    def action_open_operations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Field Operations"),
            "res_model": "field.operation",
            "view_mode": "list,form",
            "domain": [("agreement_id", "=", self.id)],
            "context": {"default_agreement_id": self.id},
            "target": "current",
        }

    def action_load_template(self):
        """Load the selected template and render it with the agreement data."""
        self.ensure_one()
        self._check_office_group("load an agreement template")
        if not self.template_id:
            raise ValidationError(_("Please select a template first."))
        if self.description:
            raise ValidationError(
                _(
                    "The agreement terms already contain text. Clear them before "
                    "loading a template."
                )
            )
        self.description = self.template_id._render_content(self)
