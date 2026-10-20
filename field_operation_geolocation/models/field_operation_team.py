from datetime import timedelta
from typing import Any

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import geo_helpers


class FieldOperationTeam(models.Model):
    _inherit = "field.operation.team"

    base_location_id = fields.Many2one(
        "res.partner",
        string="Route Start (Depot)",
        domain=[("is_company", "=", True)],
        help="Where this team's route starts and ends when it starts at the "
        "company. When empty, the company address is used; when that has no "
        "coordinates either, the route starts at the first customer of the day.",
    )
    route_start_mode = fields.Selection(
        [("home", "Home"), ("company", "Company")],
        string="Route Start",
        default="home",
        required=True,
        help="Home: the day starts and ends at the team head's home address. "
        "Company: it starts and ends at the team's base or the company "
        "address.",
    )
    home_location_id = fields.Many2one(
        "res.partner",
        string="Home Address",
        related="team_head_id.home_location_id",
        readonly=False,
        domain=[("is_company", "=", False)],
        help="Home address of the team head. Used when the route starts from "
        "home; when it is empty or has no coordinates, the route falls back to "
        "the company address. Editing it here also updates the employee's home "
        "address, because both fields are the same value.",
    )
    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))
    accuracy = fields.Float("Accuracy (m)")
    device_id = fields.Char("Device ID")
    timestamp = fields.Datetime("GPS Timestamp")
    last_update = fields.Datetime("Last Update")
    # Not stored on purpose: "online" is relative to *now*, so a stored value is
    # only refreshed when last_update is written and stays True forever once the
    # pings stop. Non-stored computes on every read; nothing filters/groups on it.
    is_online = fields.Boolean("Online", compute="_compute_online_status")
    last_online = fields.Datetime("Last Online")
    location_history_ids = fields.One2many(
        "team.location.history", "team_id", string="Location History"
    )
    location_history_count = fields.Integer(
        string="History Count",
        compute="_compute_location_history_count",
    )
    status = fields.Selection(
        [
            ("idle", "Idle"),
            ("moving", "Moving"),
            ("working", "Working"),
            ("break", "On Break"),
        ],
        default="idle",
        string="Status",
    )
    battery_level = fields.Integer("Battery %")
    signal_strength = fields.Selection(
        [
            ("0", "No Signal"),
            ("1", "Weak"),
            ("2", "Fair"),
            ("3", "Good"),
            ("4", "Excellent"),
        ],
        string="Signal Strength",
    )

    @api.depends("location_history_ids")
    def _compute_location_history_count(self):
        counts = {}
        team_ids = [team.id for team in self if team.id]
        if team_ids:
            # A single grouped query for every team instead of one search_count
            # per record (N+1).
            groups = self.env["team.location.history"]._read_group(
                domain=[("team_id", "in", team_ids)],
                groupby=["team_id"],
                aggregates=["__count"],
            )
            counts = {team.id: count for team, count in groups}
        for team in self:
            team.location_history_count = counts.get(team.id, 0)

    @api.depends("last_update")
    def _compute_online_status(self):
        for team in self:
            if team.last_update:
                delta = fields.Datetime.now() - team.last_update
                team.is_online = delta.total_seconds() < 300
            else:
                team.is_online = False

    def _route_home_partner(self):
        """The home address of the team head, or an empty recordset."""
        self.ensure_one()
        return self.team_head_id.home_location_id

    def _route_company_partner(self):
        """The company point: the team's located base, else the company address."""
        self.ensure_one()
        if self._route_point_of(self.base_location_id):
            return self.base_location_id
        return self.company_id.partner_id

    def _route_point_of(self, partner):
        """The ``(lat, lon)`` of a partner, or None when it has no coordinates."""
        if partner and geo_helpers.has_point(
            partner.partner_latitude, partner.partner_longitude
        ):
            return (float(partner.partner_latitude), float(partner.partner_longitude))
        return None

    def _route_start_is_home(self):
        """Whether the route really starts at the home (not at the fallback)."""
        self.ensure_one()
        if self.route_start_mode != "home":
            return False
        return bool(self._route_point_of(self._route_home_partner()))

    def _route_start_partner(self):
        """The address the route really starts and ends at, or an empty set.

        ``home`` is only used when it carries coordinates: an employee without
        a located home must not leave the day without a start point, so the
        company address takes over. The caller can tell the two apart with
        :meth:`_route_start_is_home` and warn the dispatcher.
        """
        self.ensure_one()
        if self.route_start_mode == "home":
            home = self._route_home_partner()
            if self._route_point_of(home):
                return home
        return self._route_company_partner()

    def _route_start_point(self):
        """The team's departure and return point as ``(lat, lon)``, or None.

        The route is a loop: it leaves this point in the morning and comes back
        to it in the evening, so the same point is both the start and the end.
        It is the team head's home when the team starts from home and the home
        has coordinates, and the company/depot address otherwise.

        Returns None for an empty or multi-record recordset instead of raising:
        the route dialog is also opened before a team is picked, and a computed
        field must not crash that form.
        """
        if len(self) != 1:
            return None
        return self._route_point_of(self._route_start_partner())

    def action_show_day_route(self, day=None):
        """Open the route plan of this team for one day (default: today)."""
        self.ensure_one()
        day = fields.Date.to_date(day) if day else fields.Date.context_today(self)
        return {
            "type": "ir.actions.act_window",
            "name": _("Route Plan"),
            "res_model": "field.operation.route.plan",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_team_id": self.id,
                "default_date": day.isoformat(),
            },
        }

    def action_show_today_route(self):
        return self.action_show_day_route(fields.Date.context_today(self))

    def action_show_tomorrow_route(self):
        return self.action_show_day_route(
            fields.Date.context_today(self) + timedelta(days=1)
        )

    def action_start_gps_tracking(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "start_gps_tracking",
            "params": {"team_id": self.id},
        }

    def action_stop_gps_tracking(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "stop_gps_tracking",
            "params": {"team_id": self.id},
        }

    def action_show_on_map(self):
        self.ensure_one()
        if not geo_helpers.has_point(self.latitude, self.longitude):
            raise UserError(_("No GPS coordinates available"))

        maps_website = self.env.user.map_website_id
        if maps_website and maps_website.lat_lon_url:
            url = maps_website._get_lat_lon_url(self.latitude, self.longitude)
        else:
            url = (
                f"https://www.openstreetmap.org/?mlat={self.latitude}"
                f"&mlon={self.longitude}&zoom=15"
            )

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_show_team_locations(self) -> dict[str, Any]:
        if not self:
            raise UserError(_("No teams selected."))

        maps_website = (
            self.env.user.multi_locations_map_website_id or self.env.user.map_website_id
        )
        if not maps_website:
            raise UserError(_("Please configure a Multi-Location Map Provider."))

        coordinates = []
        for team in self:
            if geo_helpers.has_point(team.latitude, team.longitude):
                info = team.name
                if team.battery_level:
                    info += _(" (Bat: %s%%)") % team.battery_level
                coordinates.append((team.latitude, team.longitude, info))

        if not coordinates:
            raise UserError(_("No valid GPS coordinates found."))

        url = maps_website._get_multi_location_marker_url(coordinates)
        if not url:
            raise UserError(_("Provider does not support multi-markers."))

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_show_route_history(self):
        """Show the last 24 hours route history on map."""
        self.ensure_one()

        # Last 24 hours of points, newest first (at most 50 points).
        history = self.env["team.location.history"].search(
            [
                ("team_id", "=", self.id),
                ("timestamp", ">=", fields.Datetime.now() - timedelta(hours=24)),
            ],
            limit=50,
            order="timestamp desc",
        )

        if not history:
            raise UserError(_("No location history found for the last 24 hours."))

        # Format coordinates: [(lat, lon, timestamp), ...]
        coordinates = [(h.latitude, h.longitude, str(h.timestamp)) for h in history]

        # Build the map URL (multi-point display).
        maps_website = self.env.user.map_website_id
        if maps_website:
            url = maps_website._get_multi_location_marker_url(coordinates)
        else:
            # Fallback: GraphHopper
            points = "&".join(f"point={lat},{lon}" for lat, lon, _ in coordinates)
            url = f"https://graphhopper.com/maps/?{points}&layer=Omniscale"

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }
