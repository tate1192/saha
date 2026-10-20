"""Daily route planner used by the office team that dispatches the field crews.

The wizard is intentionally transient: the dispatcher opens it for one team and
one day, sees the stops in the order the plan implies, is told when that order
drives across the city and back, and can fix it. What it saves on the operations
is the resulting order and - optionally - the start times, not a planning
document of its own.
"""

from datetime import datetime

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import geo_helpers


class FieldOperationRoutePlan(models.TransientModel):
    _name = "field.operation.route.plan"
    _description = "Daily Route Plan"

    team_id = fields.Many2one(
        "field.operation.team",
        string="Team",
        required=True,
        default=lambda self: self._default_team_id(),
        help="Preselected from the planner's own team so the office does not "
        "have to pick one; only the stops of one team belong to one route.",
    )
    date = fields.Date(
        string="Day",
        required=True,
        default=fields.Date.context_today,
        help="The route of this day: a job started the day before but still "
        "running counts for the day it ends on.",
    )
    line_ids = fields.One2many(
        "field.operation.route.plan.line", "plan_id", string="Stops"
    )
    route_start_mode = fields.Selection(
        related="team_id.route_start_mode", string="Route Start", readonly=True
    )
    start_location_id = fields.Many2one(
        "res.partner",
        string="Start / End",
        compute="_compute_route",
        help="The address the route really starts and ends at: the home when "
        "it has coordinates, otherwise the company address. Empty when "
        "neither has coordinates.",
    )
    shift_times = fields.Boolean(
        string="Shift start times with the order",
        help="When enabled, the start times already planned for the day are "
        "redistributed over the new order, so the route and the appointment "
        "times stay in the same sequence. Leave it off when the appointment "
        "times are committed to the customer.",
    )
    total_km = fields.Float(
        string="Route (km)",
        compute="_compute_route",
        digits=(10, 1),
        help="The whole loop: start -> stops -> start, including the return leg.",
    )
    return_km = fields.Float(
        string="Return (km)",
        compute="_compute_route",
        digits=(10, 1),
        help="Distance from the last stop back to the start point.",
    )
    suggested_km = fields.Float(
        string="Suggested (km)", compute="_compute_route", digits=(10, 1)
    )
    is_consistent = fields.Boolean(
        string="Order is consistent", compute="_compute_route"
    )
    missing_count = fields.Integer(
        string="Stops without coordinates", compute="_compute_route"
    )
    info = fields.Char(string="Route Check", compute="_compute_route")

    @api.model
    def _default_team_id(self):
        """The team this planner most likely wants, so nothing has to be picked.

        Order: the team the user leads, then the team the user's employee is a
        head/member of, then the only team of the database. With several teams
        and no link between the user and any of them, the field stays empty -
        guessing a team would plan the wrong route.
        """
        Team = self.env["field.operation.team"]
        team = Team.search(
            [("team_leader_id", "=", self.env.user.id)], limit=1, order="sequence, id"
        )
        if team:
            return team
        employee = (
            self.env["hr.employee"]
            .sudo()
            .search([("user_id", "=", self.env.user.id)], limit=1)
        )
        if employee:
            team = Team.search(
                [
                    "|",
                    ("team_head_id", "=", employee.id),
                    ("team_members_ids", "in", employee.id),
                ],
                limit=1,
                order="sequence, id",
            )
            if team:
                return team
        teams = Team.search([], limit=2, order="sequence, id")
        return teams if len(teams) == 1 else Team

    @api.model_create_multi
    def create(self, vals_list):
        plans = super().create(vals_list)
        for plan, vals in zip(plans, vals_list, strict=False):
            if not vals.get("line_ids"):
                plan._load_stops()
        return plans

    def _day_operations(self):
        """The operations of this team and day, in their current route order."""
        self.ensure_one()
        Operation = self.env["field.operation"]
        domain = [
            ("team_id", "=", self.team_id.id),
            ("status", "not in", ("done", "cancel")),
        ] + Operation._plan_day_domain(self.date)
        operations = Operation.search(
            domain, order="start_date asc, sequence asc, id asc"
        )
        # A dispatcher who already fixed this day's order gets it back, and a
        # job added afterwards must not wipe that order: sequenced stops keep
        # their saved position, the new ones land at the end (earliest start
        # first) where the dispatcher can see and place them. A day without any
        # manual order keeps the planned start time order.
        sequenced = operations.filtered("route_sequence").sorted(
            lambda operation: (
                operation.route_sequence,
                operation.start_date,
                operation.id,
            )
        )
        unsequenced = (operations - sequenced).sorted(
            lambda operation: (
                operation.start_date,
                operation.sequence or 0,
                operation.id,
            )
        )
        return operations.browse(
            [operation.id for operation in sequenced]
            + [operation.id for operation in unsequenced]
        )

    def _load_stops(self):
        """(Re)build the stop lines from the current plan of this team and day."""
        self.ensure_one()
        self.line_ids.unlink()
        if not self.team_id or not self.date:
            return
        self.line_ids = [
            (0, 0, {"operation_id": operation.id, "sequence": (index + 1) * 10})
            for index, operation in enumerate(self._day_operations())
        ]

    def _start_point(self):
        """The point the day's loop starts and ends at, or None."""
        if not self.team_id:
            return None
        return self.team_id._route_start_point()

    def _start_partner(self):
        """The address the route really uses as its start and end.

        Empty when the selected point has no coordinates: the form must not
        claim a start point the distance calculation cannot use.
        """
        if not self.team_id:
            return self.env["res.partner"]
        partner = self.team_id._route_start_partner()
        if self.team_id._route_point_of(partner):
            return partner
        return self.env["res.partner"]

    def _point_of(self, operation):
        # A stop line whose operation disappeared must not take the dialog down
        # with a singleton error; it simply has no coordinates.
        if not operation:
            return None
        return geo_helpers.record_point(operation)

    def _ordered_lines(self):
        self.ensure_one()
        return self.line_ids.sorted(lambda line: (line.sequence or 0, line.id or 0))

    @api.onchange("team_id", "date")
    def _onchange_team_or_date(self):
        """Load the stops as soon as a team and a day are picked."""
        if not self.team_id or not self.date:
            self.line_ids = [(5, 0, 0)]
            return
        self.line_ids = [(5, 0, 0)] + [
            (0, 0, {"operation_id": operation.id, "sequence": (index + 1) * 10})
            for index, operation in enumerate(self._day_operations())
        ]

    @api.depends(
        "line_ids.sequence",
        "line_ids.operation_id",
        "team_id",
        "date",
        "team_id.route_start_mode",
        "team_id.team_head_id.home_location_id",
        "team_id.base_location_id",
    )
    def _compute_route(self):
        for plan in self:
            if not plan.team_id or not plan.date:
                # The dialog is also opened from the menu, without a team yet:
                # there is nothing to measure and no start point to look up.
                plan.total_km = 0.0
                plan.return_km = 0.0
                plan.suggested_km = 0.0
                plan.start_location_id = False
                plan.is_consistent = True
                plan.missing_count = 0
                plan.info = _("Select a team and a day to load the stops.")
                continue
            start = plan._start_point()
            plan.start_location_id = plan._start_partner()
            ordered = plan._ordered_lines()
            points = [plan._point_of(line.operation_id) for line in ordered]

            # Distance of the current order. The per-leg distance is a field of
            # the line (its own compute); a plan compute writes nothing on
            # another model.
            total = 0.0
            previous = start
            last_point = None
            for point in points:
                if previous and point:
                    total += geo_helpers.haversine_km(previous, point)
                if point:
                    previous = point
                    last_point = point
            # The day is a loop: drive back to where it started. Without a
            # start point there is nothing to return to, so the route stays
            # open and the return leg is zero.
            return_km = (
                geo_helpers.haversine_km(last_point, start)
                if start and last_point
                else 0.0
            )
            plan.total_km = total + return_km
            plan.return_km = return_km
            plan.missing_count = sum(1 for point in points if not point)

            # The suggestion must optimize the loop, not the one-way trip:
            # otherwise it leaves the stop next to home as the last one.
            suggestion = geo_helpers.suggest_route_order(points, start=start, end=start)
            plan.suggested_km = geo_helpers.path_length_km(
                points, suggestion, start=start, end=start
            )
            plan.is_consistent = not geo_helpers.distance_gain_is_significant(
                plan.total_km, plan.suggested_km
            )

            messages = []
            if plan.missing_count:
                messages.append(
                    _(
                        "%(count)s stop(s) have no coordinates and are left out "
                        "of the route.",
                        count=plan.missing_count,
                    )
                )
            team = plan.team_id
            # Only warn about a home that is configured but unusable. A team
            # without a home address is a normal state (it starts at the
            # company); warning on every plan would train the dispatcher to
            # ignore the message.
            home = team._route_home_partner()
            if (
                team.route_start_mode == "home"
                and home
                and not team._route_start_is_home()
            ):
                if start:
                    messages.append(
                        _(
                            "Home address has no coordinates; the route starts "
                            "and ends at the company."
                        )
                    )
                else:
                    messages.append(
                        _(
                            "Neither the home nor the company address has "
                            "coordinates; the route starts at the first stop and "
                            "has no return."
                        )
                    )
            elif not start:
                messages.append(
                    _(
                        "The company address has no coordinates; the route "
                        "starts at the first stop and has no return."
                    )
                )
            if plan.is_consistent:
                if start:
                    messages.append(
                        _(
                            "Order looks consistent: %(km)s km (return "
                            "%(return_km)s km).",
                            km=round(plan.total_km, 1),
                            return_km=round(plan.return_km, 1),
                        )
                    )
                else:
                    messages.append(
                        _(
                            "Order looks consistent: %(km)s km.",
                            km=round(plan.total_km, 1),
                        )
                    )
            elif start:
                messages.append(
                    _(
                        "Order looks inconsistent: %(current)s km now, "
                        "%(suggested)s km if reordered (%(saving)s km saved); "
                        "return is %(return_km)s km.",
                        current=round(plan.total_km, 1),
                        suggested=round(plan.suggested_km, 1),
                        saving=round(plan.total_km - plan.suggested_km, 1),
                        return_km=round(plan.return_km, 1),
                    )
                )
            else:
                messages.append(
                    _(
                        "Order looks inconsistent: %(current)s km now, "
                        "%(suggested)s km if reordered (%(saving)s km saved).",
                        current=round(plan.total_km, 1),
                        suggested=round(plan.suggested_km, 1),
                        saving=round(plan.total_km - plan.suggested_km, 1),
                    )
                )
            plan.info = " ".join(messages)

    def _reopen(self):
        """Return the action that reloads this dialog after a write."""
        return {
            "type": "ir.actions.act_window",
            "name": _("Route Plan"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context),
        }

    def action_reload(self):
        """Rebuild the stops after the team or the day changed."""
        self.ensure_one()
        self._load_stops()
        return self._reopen()

    def action_suggest_order(self):
        """Apply the shorter (nearest-neighbour + 2-opt) visiting order."""
        self.ensure_one()
        start = self._start_point()
        ordered = self._ordered_lines()
        points = [self._point_of(line.operation_id) for line in ordered]
        suggestion = geo_helpers.suggest_route_order(points, start=start, end=start)
        for position, index in enumerate(suggestion):
            ordered[index].sequence = (position + 1) * 10
        return self._reopen()

    def _shift_start_times(self, operations):
        """Redistribute the day's planned start times over the new order.

        Only the time of day moves: each stop keeps its own day, and an end
        time moves by the same amount as its start so the duration is kept.
        """
        # A job that started on another day (still running from yesterday) keeps
        # its start: moving it would move work across days, and its time of day
        # is not part of today's appointment pool.
        scheduled = [
            operation
            for operation in operations
            if operation.start_date
            and fields.Datetime.context_timestamp(self, operation.start_date).date()
            == self.date
        ]
        if len(scheduled) < 2:
            return
        slots = sorted(operation.start_date for operation in scheduled)
        tz = pytz.timezone(self.env.user.tz or "UTC")
        for operation, slot in zip(scheduled, slots, strict=False):
            local_day = fields.Datetime.context_timestamp(
                self, operation.start_date
            ).date()
            local_slot = fields.Datetime.context_timestamp(self, slot).time()
            new_start = (
                tz.localize(datetime.combine(local_day, local_slot))
                .astimezone(pytz.utc)
                .replace(tzinfo=None)
            )
            delta = new_start - operation.start_date
            if not delta:
                continue
            vals = {"start_date": new_start}
            if operation.end_date:
                vals["end_date"] = operation.end_date + delta
            operation.write(vals)

    def action_save_order(self):
        """Store the visible order on the operations and close the dialog."""
        self.ensure_one()
        operations = self._ordered_lines().mapped("operation_id")
        if self.shift_times:
            self._shift_start_times(operations)
        for position, operation in enumerate(operations):
            operation.route_sequence = (position + 1) * 10
        self.env.user._bus_send(
            "simple_notification",
            {
                "type": "success",
                "title": _("Route saved"),
                "message": _(
                    "%(count)s stops saved in this order for %(team)s.",
                    count=len(operations),
                    team=self.team_id.display_name,
                ),
                "sticky": False,
            },
        )
        return {"type": "ir.actions.act_window_close"}

    def action_geolocate_stops(self):
        """Geolocate the day's stops that still have no coordinates."""
        self.ensure_one()
        operations = self._ordered_lines().mapped("operation_id")
        targets = operations.filtered(
            lambda operation: operation.address_id and not operation.is_located
        )
        if not targets:
            self.env.user._bus_send(
                "simple_notification",
                {
                    "type": "info",
                    "title": _("Nothing to do"),
                    "message": _(
                        "All stops of this day already have coordinates, or "
                        "have no address."
                    ),
                    "sticky": False,
                },
            )
            return self._reopen()

        located = 0
        failed = []
        for operation in targets:
            try:
                geo_helpers.geolocate_service_address(operation)
            except UserError:
                failed.append(operation.display_name)
                continue
            operation.invalidate_recordset(
                ["service_latitude", "service_longitude", "is_located"]
            )
            if geo_helpers.has_coordinates(operation):
                operation.date_localization = fields.Datetime.now()
                located += 1
            else:
                failed.append(operation.display_name)

        if failed:
            message = _(
                "%(located)s of %(total)s stops located; %(failed)s not found: "
                "%(names)s",
                located=located,
                total=len(targets),
                failed=len(failed),
                names=", ".join(failed[:5]),
            )
        else:
            message = _(
                "%(located)s of %(total)s stops located.",
                located=located,
                total=len(targets),
            )
        self.env.user._bus_send(
            "simple_notification",
            {
                "type": "success" if not failed else "warning",
                "title": _("Geolocation"),
                "message": message,
                "sticky": bool(failed),
            },
        )
        return self._reopen()

    def action_open_map(self):
        """Open the planned route in the user's route map provider."""
        self.ensure_one()
        maps_website = self.env.user.route_map_website_id
        if not maps_website:
            raise UserError(_("Please configure a Route Map Provider."))

        operations = self._ordered_lines().mapped("operation_id")
        located = operations.filtered("is_located")
        missing = operations - located
        if len(operations) < 2:
            raise UserError(
                _("This day has fewer than 2 stops; there is no route to draw.")
            )
        if len(located) < 2:
            names = missing.mapped("display_name")
            raise UserError(
                _(
                    "At least 2 stops of this day need coordinates to build a "
                    "route. Without coordinates: %(names)s. Use 'Geolocate "
                    "Stops' to locate them first.",
                    names=", ".join(names[:5]),
                )
            )

        start = self._start_point()
        points = [start] if start else []
        points.extend(
            (float(operation.service_latitude), float(operation.service_longitude))
            for operation in located
        )
        if start:
            # Close the loop: the same point is the destination of the day.
            points.append(start)
        url = maps_website._get_route_url_for_points(points)
        if not url:
            raise UserError(_("Map provider does not support multi-point routing."))
        if missing:
            missing._notify_missing_stops()
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}


class FieldOperationRoutePlanLine(models.TransientModel):
    _name = "field.operation.route.plan.line"
    _description = "Daily Route Plan Stop"
    _order = "sequence, id"

    plan_id = fields.Many2one(
        "field.operation.route.plan", required=True, ondelete="cascade"
    )
    sequence = fields.Integer(default=10)
    operation_id = fields.Many2one(
        "field.operation", string="Operation", required=True, ondelete="cascade"
    )
    partner_id = fields.Many2one(
        "res.partner", string="Customer", related="operation_id.partner_id"
    )
    district = fields.Char(string="District", related="operation_id.district_id")
    start_time = fields.Datetime(string="Start", related="operation_id.start_date")
    is_located = fields.Boolean(related="operation_id.is_located")
    leg_km = fields.Float(
        string="Leg (km)",
        digits=(10, 1),
        compute="_compute_leg_km",
        help="Distance driven from the previous stop (or from the start point).",
    )

    @api.depends(
        "plan_id.line_ids.sequence",
        "plan_id.line_ids.operation_id",
        "plan_id.team_id",
        "plan_id.team_id.route_start_mode",
        "sequence",
        "operation_id",
    )
    def _compute_leg_km(self):
        """Distance from the previous stop (or the start point) to this one."""
        for line in self:
            plan = line.plan_id
            line.leg_km = 0.0
            if not plan:
                continue
            previous = plan._start_point()
            for candidate in plan._ordered_lines():
                point = plan._point_of(candidate.operation_id)
                if candidate == line:
                    if previous and point:
                        line.leg_km = geo_helpers.haversine_km(previous, point)
                    break
                if point:
                    previous = point
