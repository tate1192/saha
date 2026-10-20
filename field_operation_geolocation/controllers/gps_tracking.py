import logging

from odoo import _, fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

# Accepted coordinate ranges: reject clearly corrupted device payloads.
MIN_LATITUDE, MAX_LATITUDE = -90.0, 90.0
MIN_LONGITUDE, MAX_LONGITUDE = -180.0, 180.0

# A route-history point is kept every five minutes at most.
HISTORY_MIN_INTERVAL_SECONDS = 300


def _to_float(value):
    """Return ``value`` as a float, or None when it is not numeric."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp_battery_level(value):
    """Return the battery level as an integer inside the 0-100 range."""
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return 0


class FieldTeamAPI(http.Controller):
    def _get_user_team(self, user):
        """Return the field team the user belongs to, or None when there is none."""
        employee = (
            request.env["hr.employee"]
            .sudo()
            .search([("user_id", "=", user.id)], limit=1)
        )
        if not employee:
            return None
        return (
            request.env["field.operation.team"]
            .sudo()
            .search(
                [
                    "|",
                    ("team_members_ids", "in", employee.id),
                    ("team_head_id", "=", employee.id),
                ],
                limit=1,
            )
        )

    def _selection_values(self, field_name):
        """Return the allowed values of a field.operation.team Selection field."""
        field = request.env["field.operation.team"]._fields[field_name]
        selection = field.selection
        if callable(selection):
            selection = selection(request.env["field.operation.team"])
        return {value for value, _label in selection}

    def _clean_selection_value(self, field_name, value, default=None):
        """Return a valid Selection value, or ``default`` when it is unknown.

        An outdated client may send a value the server no longer knows (for
        instance ``status='started'``). Dropping it keeps the remaining
        position fields writable instead of failing the whole request.
        """
        if value is None:
            value = default
        if value is None:
            return None
        value = str(value)
        if value not in self._selection_values(field_name):
            _logger.warning(
                "Ignoring unknown field.operation.team.%s value %r", field_name, value
            )
            return None
        return value

    @staticmethod
    def _parse_timestamp(value):
        """Return ``value`` as a datetime, or None when it is missing/invalid."""
        if not value:
            return None
        try:
            return fields.Datetime.to_datetime(value)
        except (TypeError, ValueError):
            return None

    @http.route("/field_team/get_my_team", type="jsonrpc", auth="user")
    def get_my_team(self):
        """Return the field team assigned to the logged-in user."""
        try:
            team = self._get_user_team(request.env.user)
        except (AccessError, UserError):
            _logger.exception(
                "Could not resolve the field team of user %s",
                request.env.user.id,
            )
            return {"error": _("Could not retrieve your team.")}
        if not team:
            return {"error": _("You have not been assigned to any field team.")}
        return {
            "team_id": team.id,
            "team_name": team.name,
            "interval": 5,
            "status": team.status,
        }

    @http.route(
        "/field_team/update_gps",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def update_gps(self, **kwargs):
        """Store the GPS position reported by a field worker's device."""
        team_id = kwargs.get("team_id")
        raw_latitude = kwargs.get("latitude")
        raw_longitude = kwargs.get("longitude")

        if team_id is None or raw_latitude is None or raw_longitude is None:
            return {
                "error": _(
                    "Missing required parameters (team_id, latitude, longitude)."
                )
            }

        latitude = _to_float(raw_latitude)
        longitude = _to_float(raw_longitude)
        if latitude is None or not MIN_LATITUDE <= latitude <= MAX_LATITUDE:
            return {"error": _("Invalid latitude.")}
        if longitude is None or not MIN_LONGITUDE <= longitude <= MAX_LONGITUDE:
            return {"error": _("Invalid longitude.")}

        user_team = self._get_user_team(request.env.user)
        if not user_team or user_team.id != team_id:
            return {"error": _("You are not authorized to update this team.")}

        timestamp = self._parse_timestamp(kwargs.get("timestamp"))
        if kwargs.get("timestamp") and timestamp is None:
            return {"error": _("Invalid timestamp.")}

        now = fields.Datetime.now()
        accuracy = _to_float(kwargs.get("accuracy"))
        battery_level = _clamp_battery_level(kwargs.get("battery_level", 0))
        update_vals = {
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "last_update": now,
            "last_online": now,
            "timestamp": timestamp or now,
            "battery_level": battery_level,
        }
        # An unknown Selection value is dropped, never aborting the whole write.
        for field_name, default in (("status", "working"), ("signal_strength", "3")):
            value = self._clean_selection_value(
                field_name, kwargs.get(field_name), default
            )
            if value is not None:
                update_vals[field_name] = value

        device_id = kwargs.get("device_id")
        if device_id:
            update_vals["device_id"] = device_id

        team = request.env["field.operation.team"].sudo().browse(team_id)
        try:
            # A GPS ping is telemetry, not a business change: it must never
            # write a tracking message into the team's chatter. The telemetry
            # fields are no longer tracked, and this context keeps any future
            # tracked field written here out of the log as well.
            team.with_context(tracking_disable=True).write(update_vals)
            history_saved = self._store_history(
                team_id,
                latitude,
                longitude,
                accuracy,
                battery_level,
                update_vals["timestamp"],
                now,
            )
        except (AccessError, UserError, ValidationError):
            _logger.exception("GPS update failed for team %s", team_id)
            return {"error": _("Could not update the GPS position.")}

        return {
            "status": "success",
            "team_id": team.id,
            "timestamp": now,
            "message": _("Location updated successfully."),
            "history_saved": history_saved,
        }

    def _store_history(
        self, team_id, latitude, longitude, accuracy, battery_level, timestamp, now
    ):
        """Append a route-history point, at most once per interval."""
        history = request.env["team.location.history"].sudo()
        last_record = history.search(
            [("team_id", "=", team_id)], limit=1, order="timestamp desc"
        )
        if last_record and last_record.timestamp:
            elapsed = (now - last_record.timestamp).total_seconds()
            if elapsed < HISTORY_MIN_INTERVAL_SECONDS:
                return False
        history.create(
            {
                "team_id": team_id,
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": accuracy,
                "battery_level": battery_level,
                "timestamp": timestamp,
            }
        )
        return True
