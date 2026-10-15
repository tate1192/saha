# field_operation/models/field_operation_team.py
import json
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .field_operation import STATUS


class FieldOperationTeam(models.Model):
    _name = "field.operation.team"
    _description = "Field Operation Team"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char("Team Name", required=True, translate=True, tracking=True)
    active = fields.Boolean(default=True)
    color = fields.Integer(default=0)
    sequence = fields.Integer(index=True, default=10)
    team_head_id = fields.Many2one("hr.employee", "Team Head", tracking=True)
    team_leader_id = fields.Many2one("res.users", "Team Leader", tracking=True)
    team_members_ids = fields.Many2many(
        "hr.employee", string="Team Members", tracking=True
    )
    region_id = fields.Many2one("field.operation.region", string="Region", index=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    priority = fields.Selection(
        [
            ("0", "Low"),
            ("1", "High"),
            ("2", "Emergency"),
        ],
        default="0",
        index=True,
        string="Priority",
        tracking=True,
    )

    kanban_data = fields.Text(
        compute="_compute_kanban_data",
    )
    kanban_graph = fields.Text(
        compute="_compute_kanban_graph",
    )
    member_count = fields.Integer(
        string="Member Count", compute="_compute_member_count", store=True
    )

    service_count = fields.Integer(
        string="Service Count", compute="_compute_service_count"
    )

    operation_ids = fields.One2many("field.operation", "team_id", string="Services")

    # -------------------------------------------------------------------------
    # Computed Methods
    # -------------------------------------------------------------------------

    @api.depends("team_members_ids")
    def _compute_member_count(self):
        for team in self:
            team.member_count = len(team.team_members_ids)

    @api.depends("operation_ids")
    def _compute_service_count(self):
        counts = {}
        team_ids = [tid for tid in self.ids if tid]
        if team_ids:
            data = self.env["field.operation"]._read_group(
                domain=[("team_id", "in", team_ids)],
                groupby=["team_id"],
                aggregates=["__count"],
            )
            counts = {team.id: count for team, count in data}
        for team in self:
            team.service_count = counts.get(team.id, 0)

    @api.depends("team_members_ids", "region_id", "operation_ids")
    def _compute_kanban_data(self):
        data_map = self._get_kanban_data_batch()
        for team in self:
            team.kanban_data = json.dumps(data_map.get(team.id, {}))

    @api.depends("team_members_ids", "operation_ids")
    def _compute_kanban_graph(self):
        graph_map = self._get_graph_data_batch()
        for team in self:
            team.kanban_graph = json.dumps(graph_map.get(team.id, []))

    def _get_kanban_data(self):
        self.ensure_one()
        return self._get_kanban_data_batch()[self.id]

    def _empty_kanban_data(self):
        counts = {status: 0 for status, _label in STATUS}
        return {
            "member_count": 0,
            "today": {"counts": dict(counts), "total": 0, "completion_rate": 0.0},
            "week": {"counts": dict(counts), "total": 0},
            "month": {"counts": dict(counts), "total": 0},
            "show_company": self.env.user.has_group("base.group_multi_company"),
            "has_entries": False,
        }

    def _get_kanban_data_batch(self):
        """Kanban dashboard data for every team of ``self``.

        Today/week/month status counters are aggregated with one
        ``_read_group`` per period, whatever the number of teams.
        """
        result = {team.id: self._empty_kanban_data() for team in self}
        for team in self:
            result[team.id]["member_count"] = len(team.team_members_ids)

        team_ids = [tid for tid in self.ids if tid]
        if not team_ids:
            return result

        FieldOperation = self.env["field.operation"]
        today = fields.Date.context_today(self)
        for period in ("today", "week", "month"):
            domain = [("team_id", "in", team_ids)] + self._get_date_domain(
                period, today
            )
            counts_by_team = {}
            for team, status, count in FieldOperation._read_group(
                domain=domain, groupby=["team_id", "status"], aggregates=["__count"]
            ):
                counts_by_team.setdefault(team.id, {})[status] = count
            for team in self:
                counts = {status: 0 for status, _label in STATUS}
                counts.update(counts_by_team.get(team.id, {}))
                result[team.id][period]["counts"] = counts
                result[team.id][period]["total"] = sum(counts.values())

        for team in self:
            entry = result[team.id]
            entry["today"]["completion_rate"] = self._calculate_completion_rate(
                entry["today"]["counts"]
            )
            entry["has_entries"] = entry["today"]["total"] > 0
        return result

    def _get_graph_data_last_30_days(self):
        self.ensure_one()
        return self._get_graph_data_batch()[self.id]

    def _get_graph_data_batch(self):
        """Service counts per team over the last four weeks (one query per week).

        The shape is the one the core ``dashboard_graph`` widget reads: a list
        holding one series, whose ``values`` are the points — see ``web`` ›
        ``views/fields/journal_dashboard_graph/journal_dashboard_graph_field.js``,
        which does ``this.data[0].values``. ``account`` and ``mrp`` build theirs
        the same way. Feeding the widget the older ``{'label', 'value'}`` list
        instead makes it throw ``Cannot read properties of undefined (reading
        'map')`` as soon as a team has a service today, because the view only
        draws the graph for those teams: the kanban breaks exactly where it is
        supposed to be useful.
        """
        result = {team.id: [] for team in self}
        team_ids = [tid for tid in self.ids if tid]
        if not team_ids:
            return result

        FieldOperation = self.env["field.operation"]
        today = fields.Date.context_today(self)
        # One pass over the four weeks: the buckets are shared by every team.
        buckets = []
        for week_offset in range(4, 0, -1):
            week_start = today - timedelta(
                days=today.weekday() + (7 * (week_offset - 1))
            )
            week_end = week_start + timedelta(days=6)
            data = FieldOperation._read_group(
                domain=[("team_id", "in", team_ids)]
                + self._get_date_domain_range(week_start, week_end),
                groupby=["team_id"],
                aggregates=["__count"],
            )
            buckets.append(
                {
                    # `x` is the axis label; `name` carries the whole range, as the
                    # account dashboard does. The widget does not read it today, a
                    # tooltip of our own would.
                    "x": week_start.strftime("%d/%m"),
                    "name": f"{week_start:%d/%m} - {week_end:%d/%m}",
                    "counts": {team.id: count for team, count in data},
                }
            )

        for team in self:
            result[team.id] = [
                {
                    "key": _("Services"),
                    "values": [
                        {
                            "x": bucket["x"],
                            "y": bucket["counts"].get(team.id, 0),
                            "name": bucket["name"],
                        }
                        for bucket in buckets
                    ],
                    # Real counts, zeros included: a quiet team is not sample data.
                    "is_sample_data": False,
                }
            ]
        return result

    def _get_date_domain(self, period, today):
        if period == "today":
            start, end = today, today
        elif period == "week":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
        elif period == "month":
            start = today.replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        else:
            return [("id", "=", 0)]
        return self._get_date_domain_range(start, end)

    def _get_date_domain_range(self, date_from, date_to):
        """Return a domain matching records whose start_date falls within the
        given local (user timezone) date range, inclusive."""
        tz = self.env.tz
        start_utc = tz.localize(datetime.combine(date_from, time.min), is_dst=False)
        end_utc = tz.localize(datetime.combine(date_to, time.max), is_dst=False)
        return [
            ("start_date", ">=", start_utc.astimezone(pytz.utc).replace(tzinfo=None)),
            ("start_date", "<=", end_utc.astimezone(pytz.utc).replace(tzinfo=None)),
        ]

    def _calculate_completion_rate(self, status_counts):
        total = sum(status_counts.values())
        if not total:
            return 0.0
        completed = status_counts.get("done", 0)
        return round((completed / total) * 100, 1)

    # -------------------------------------------------------------------------
    # Action Methods
    # -------------------------------------------------------------------------

    def open_team_service(self):
        """Open team service list"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Team Services"),
            "res_model": "field.operation",
            "view_mode": "list,form,calendar",
            "domain": [("team_id", "=", self.id)],
            "context": {"search_default_team_id": self.id, "default_team_id": self.id},
        }

    def open_team_calendar(self):
        """Open team calendar view"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Team Schedule"),
            "res_model": "field.operation",
            "view_mode": "calendar,list",
            "domain": [("team_id", "=", self.id)],
            "context": {"search_default_team_id": self.id},
        }

    def action_create_service(self):
        """Quick create service"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Service"),
            "res_model": "field.operation",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_team_id": self.id,
                "default_region_id": self.region_id.id,
                "default_company_id": self.company_id.id,
            },
        }

    # -------------------------------------------------------------------------
    # Validation and Data Integrity
    # -------------------------------------------------------------------------

    def _ensure_leader_in_members(self):
        if self.team_leader_id:
            employee = self.env["hr.employee"].search(
                [("user_id", "=", self.team_leader_id.id)], limit=1
            )
            if employee and employee not in self.team_members_ids:
                self.team_members_ids = [(4, employee.id)]

    @api.onchange("team_leader_id")
    def _onchange_team_leader_add_to_members(self):
        self._ensure_leader_in_members()

    @api.constrains("team_leader_id", "team_members_ids")
    def _check_team_leader_in_members(self):
        for team in self:
            if team.team_leader_id:
                employee = self.env["hr.employee"].search(
                    [("user_id", "=", team.team_leader_id.id)], limit=1
                )
                if employee and employee not in team.team_members_ids:
                    raise ValidationError(
                        _("Team Leader must be a member of the team!")
                    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._ensure_leader_in_members()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "team_leader_id" in vals or "team_members_ids" in vals:
            for rec in self:
                rec._ensure_leader_in_members()
        return res
