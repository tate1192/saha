from datetime import timedelta
from typing import Any

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import geo_helpers


class FieldOperationTeam(models.Model):
    _inherit = "field.operation.team"

    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))
    accuracy = fields.Float("Accuracy (m)", tracking=True)
    device_id = fields.Char("Device ID", tracking=True)
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
        tracking=True,
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
        tracking=True,
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
            url = maps_website.lat_lon_url.replace("{LATITUDE}", str(self.latitude))
            url = url.replace("{LONGITUDE}", str(self.longitude))
            if maps_website.requires_api_key and maps_website.api_key:
                url = url.replace("{API_KEY}", maps_website.api_key)
            else:
                url = url.replace("&key={API_KEY}", "").replace("?key={API_KEY}", "")
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
