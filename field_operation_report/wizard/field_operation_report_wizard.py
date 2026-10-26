# field_operation_report/wizard/field_operation_report_wizard.py

from odoo import api, fields, models

CLOSED_STATUSES = ("done",)
OPEN_STATUSES = ("draft", "planned", "progress")


class FieldOperationReportWizard(models.TransientModel):
    _name = "field.operation.report.wizard"
    _description = "Field Operation Team Report"

    date_from = fields.Date(
        string="Start Date",
        required=True,
        default="_default_date_from",
    )
    date_to = fields.Date(
        string="End Date",
        required=True,
        default="_default_date_to",
    )
    team_ids = fields.Many2many(
        "field.operation.team",
        string="Teams",
        help="Leave empty to report every team.",
    )
    service_type_ids = fields.Many2many(
        "field.operation.type",
        string="Service Types",
        help="Leave empty to report every service type.",
    )
    operation_count = fields.Integer(
        string="Services in Scope",
        compute="_compute_operation_count",
    )
    multi_currency = fields.Boolean(
        string="Mixed Currencies",
        compute="_compute_multi_currency",
        help="True when the services in scope are priced in more than one "
        "currency: the printed totals are not converted.",
    )

    @api.model
    def _default_date_from(self):
        return fields.Date.context_today(self).replace(day=1)

    @api.model
    def _default_date_to(self):
        return fields.Date.context_today(self)

    @api.depends("date_from", "date_to", "team_ids", "service_type_ids")
    def _compute_operation_count(self):
        operation_model = self.env["field.operation"]
        for wizard in self:
            wizard.operation_count = operation_model.search_count(wizard._get_domain())

    @api.depends("date_from", "date_to", "team_ids", "service_type_ids")
    def _compute_multi_currency(self):
        """Flag services priced in more than one currency.

        The totals are printed in the company currency without conversion, so
        the report says so instead of showing a silently wrong amount.
        """
        operation_model = self.env["field.operation"]
        for wizard in self:
            groups = operation_model._read_group(
                wizard._get_domain(),
                ["currency_id"],
                ["__count"],
            )
            wizard.multi_currency = len([group for group in groups if group[0]]) > 1

    def _get_domain(self):
        """Services of the period, cancelled ones excluded."""
        self.ensure_one()
        domain = [
            ("report_date", ">=", self.date_from),
            ("report_date", "<=", self.date_to),
            ("status", "!=", "cancel"),
        ]
        if self.team_ids:
            domain.append(("team_id", "in", self.team_ids.ids))
        if self.service_type_ids:
            domain.append(("service_type_id", "in", self.service_type_ids.ids))
        return domain

    def _get_report_data(self):
        """Aggregate the services of the period per team and per type."""
        self.ensure_one()
        operation_model = self.env["field.operation"]
        domain = self._get_domain()

        team_rows = []
        for team, services, duration_total, amount in operation_model._read_group(
            domain,
            ["team_id"],
            ["__count", "total_work:sum", "service_price:sum"],
        ):
            base = domain + [("team_id", "=", team.id if team else False)]
            measured = operation_model.search_count(base + [("total_work", ">", 0)])
            team_rows.append(
                {
                    "team": team.name if team else self.env._("Unassigned"),
                    "services": services,
                    "done": operation_model.search_count(
                        base + [("status", "in", CLOSED_STATUSES)]
                    ),
                    "open": operation_model.search_count(
                        base + [("status", "in", OPEN_STATUSES)]
                    ),
                    "signed": operation_model.search_count(
                        base + [("signed", "=", True)]
                    ),
                    "measured": measured,
                    "duration_total": duration_total,
                    "duration_avg": (
                        round(duration_total / measured, 2) if measured else 0.0
                    ),
                    "amount": amount,
                }
            )
        team_rows.sort(key=lambda row: (-row["services"], row["team"]))

        type_rows = []
        for (
            service_type,
            services,
            duration_total,
            amount,
        ) in operation_model._read_group(
            domain,
            ["service_type_id"],
            ["__count", "total_work:sum", "service_price:sum"],
        ):
            base = domain + [
                ("service_type_id", "=", service_type.id if service_type else False)
            ]
            measured = operation_model.search_count(base + [("total_work", ">", 0)])
            type_rows.append(
                {
                    "service_type": service_type.name
                    if service_type
                    else self.env._("Unspecified"),
                    "services": services,
                    "amount": amount,
                    "duration_avg": (
                        round(duration_total / measured, 2) if measured else 0.0
                    ),
                }
            )
        type_rows.sort(key=lambda row: -row["services"])

        return {
            "teams": team_rows,
            "types": type_rows,
            "currency": self.env.company.currency_id,
            "totals": {
                "services": sum(row["services"] for row in team_rows),
                "done": sum(row["done"] for row in team_rows),
                "open": sum(row["open"] for row in team_rows),
                "signed": sum(row["signed"] for row in team_rows),
                "measured": sum(row["measured"] for row in team_rows),
                "amount": sum(row["amount"] for row in team_rows),
            },
        }

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "field_operation_report.action_report_field_operation_team"
        ).report_action(self)
