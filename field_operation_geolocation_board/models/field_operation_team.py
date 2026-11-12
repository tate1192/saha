"""Data behind the dispatcher map board ("Daily Routes").

One request returns the whole day: every team with its stops in route order,
the closed-loop geometry, the day's kilometres, the missing-coordinate count and
the last known live position. The board is read-only; planning still happens in
the daily plan wizard, which shares the same day/order helper
(``field.operation._day_operations_for_team``) so the two screens can never
disagree about the day or the order of a team's stops.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.field_operation_geolocation.models import geo_helpers

#: Group allowed to open the board and to read every team's live position.
BOARD_GROUP = "field_operation.service_group_all"

#: Odoo's kanban colour list (web/static/src/scss/secondary_variables.scss).
#: Index 0 is the "no colour" grey, so a team with ``color=0`` gets an
#: automatic colour from 1..11 instead of blending into the background.
BOARD_COLORS = (
    "#a2a2a2",
    "#ee2d2d",
    "#dc8534",
    "#e8bb1d",
    "#5794dd",
    "#9f628f",
    "#db8865",
    "#41a9a2",
    "#304be0",
    "#ee2f8a",
    "#61c36e",
    "#9872e6",
)

#: Extra colours for the automatic assignment (Odoo's ``$o-colors-secondary``).
#: A team whose ``color`` was never picked by hand gets a stable colour out of
#: this larger pool, so a day with more than eleven teams stays readable.
BOARD_AUTO_COLORS = BOARD_COLORS[1:] + (
    "#aa4b6b",
    "#30c381",
    "#97743a",
    "#f7cd1f",
    "#4285f4",
    "#8e24aa",
    "#d6145f",
    "#173e43",
    "#348f50",
    "#aa3a38",
    "#795548",
    "#5e0231",
    "#6be585",
    "#999966",
    "#e9d362",
    "#b56969",
    "#bdc3c7",
    "#649173",
    "#ea00ff",
    "#ff0026",
    "#8bcc00",
    "#00bfaf",
    "#006aff",
    "#af00bf",
    "#bf001d",
    "#bf6300",
    "#8cff00",
    "#00f2ff",
    "#004ab3",
    "#ff00d0",
    "#ffa600",
    "#3acc00",
    "#00b6bf",
    "#0048ff",
    "#bf7c00",
    "#04ff00",
    "#00d0ff",
    "#0036bf",
    "#ff008c",
    "#00bf49",
    "#0092b3",
    "#0004ff",
    "#b20062",
    "#649173",
)

DEFAULT_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
DEFAULT_TILE_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">'
    "OpenStreetMap</a> contributors"
)


class FieldOperationTeam(models.Model):
    _inherit = "field.operation.team"

    # ------------------------------------------------------------------
    # Board data
    # ------------------------------------------------------------------
    @api.model
    def _board_check_access(self):
        """The board is a dispatcher screen; field workers must not read it.

        The check lives in the model (and not only in the menu groups) so the
        JSON endpoints cannot be called by a user who should not see the other
        teams' routes.
        """
        if not self.env.user.has_group(BOARD_GROUP):
            raise AccessError(
                _("You are not allowed to open the daily route board.")
            )

    @api.model
    def _board_team_ids(self, team_ids):
        """Normalise the ``team_ids`` argument to a list of positive ids.

        The controller receives whatever the browser sent: a list of integers,
        a single integer, numeric strings or garbage. Unusable values are
        dropped instead of raising; an explicit empty list means "no team", not
        "all teams" (``None`` is what means "all").
        """
        if isinstance(team_ids, (int, str)):
            team_ids = [team_ids]
        ids = []
        for value in team_ids or []:
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            if value > 0:
                ids.append(value)
        return ids

    @api.model
    def _board_team_domain(self, team_ids=None):
        """The team domain of the board, scoped to the user's companies.

        ``field.operation.team`` has no record rule of its own, so without this
        filter a Head Office user of a multi-company database would see (and get
        the live GPS of) teams of the other companies too.
        """
        domain = [("company_id", "in", self.env.companies.ids)]
        if team_ids is not None:
            domain.append(("id", "in", self._board_team_ids(team_ids)))
        return domain

    @api.model
    def _board_color(self, team, used_colors):
        """The ``(index, hex)`` colour of a team on the board.

        An explicit ``team.color`` wins (the same index the kanban uses, so the
        colour is consistent across Odoo). A team without a colour gets a stable
        colour out of :data:`BOARD_AUTO_COLORS`, keyed on its id and skipping the
        colours already used on this screen.
        """
        palette_size = len(BOARD_COLORS)
        if 0 < team.color < palette_size:
            used_colors.add(BOARD_COLORS[team.color])
            return team.color, BOARD_COLORS[team.color]
        index = team.id % len(BOARD_AUTO_COLORS)
        for _attempt in range(len(BOARD_AUTO_COLORS)):
            color = BOARD_AUTO_COLORS[index]
            if color not in used_colors:
                break
            index = (index + 1) % len(BOARD_AUTO_COLORS)
        used_colors.add(color)
        return 0, color

    @api.model
    def _board_map_config(self):
        """Tile layer configuration, reusing the soft_web_map parameters."""
        parameters = self.env["ir.config_parameter"].sudo()
        return {
            "tile_url": parameters.get_param("soft_web_map.tile_url", DEFAULT_TILE_URL),
            "attribution": parameters.get_param(
                "soft_web_map.copyright", DEFAULT_TILE_ATTRIBUTION
            ),
        }

    def _board_start_info(self):
        """The start/end point of the team's loop as the board needs it."""
        self.ensure_one()
        point = self._route_start_point()
        partner = self._route_start_partner()
        if self._route_start_is_home():
            kind = "home"
        elif self._route_point_of(self.base_location_id):
            kind = "depot"
        else:
            kind = "company"
        return {
            "lat": point[0] if point else False,
            "lon": point[1] if point else False,
            "label": partner.display_name if partner else "",
            "kind": kind,
            "has_start": bool(point),
        }

    def _board_live_info(self):
        """Last known live position of the team, or False when never seen."""
        self.ensure_one()
        if not geo_helpers.has_point(self.latitude, self.longitude):
            return False
        if not self.last_update:
            return False
        seconds = (fields.Datetime.now() - self.last_update).total_seconds()
        return {
            "lat": self.latitude,
            "lon": self.longitude,
            "online": self.is_online,
            "minutes_ago": max(0, int(seconds // 60)),
            "battery": self.battery_level or False,
            "accuracy": self.accuracy or False,
        }

    def _board_stop_info(self, operation, sequence, leg_km):
        """One stop line of a team's route, as the board shows it."""
        self.ensure_one()
        local_start = False
        if operation.start_date:
            local_start = fields.Datetime.context_timestamp(self, operation.start_date)
        point = geo_helpers.record_point(operation)
        return {
            "operation_id": operation.id,
            "seq": sequence,
            "label": operation.name,
            "customer": operation.partner_id.display_name or "",
            "subject": operation.subject or "",
            "district": operation.district_id or "",
            "address": (
                operation.address_id._display_address(without_company=True)
                if operation.address_id
                else ""
            ),
            "phone": operation.contact_mobile
            or (operation.partner_id.phone if operation.partner_id else "")
            or "",
            "time": local_start.strftime("%H:%M") if local_start else "",
            "start_date": (
                fields.Datetime.to_string(operation.start_date)
                if operation.start_date
                else False
            ),
            "status": operation.status,
            "located": bool(point),
            "lat": point[0] if point else False,
            "lon": point[1] if point else False,
            "leg_km": round(leg_km, 1),
        }

    # ------------------------------------------------------------------
    # Day operations (compatible with older geolocation versions)
    # ------------------------------------------------------------------
    @api.model
    def _board_day_operations(self, team, day):
        """The day's operations in route order, shared with the plan wizard.

        ``field_operation_geolocation`` >= 19.0.1.8.0 exposes
        ``_day_operations_for_team`` (the plan wizard and the board use the same
        order). The board also installs on the older 19.0.1.6.x versions of that
        module, where the same order is kept inside the plan wizard only: the
        fallback below reproduces it instead of forcing a geolocation upgrade
        just to open the board.
        """
        Operation = self.env["field.operation"]
        shared = getattr(Operation, "_day_operations_for_team", None)
        if shared is not None:
            return shared(team, day)
        return self._board_legacy_day_operations(team, day)

    @api.model
    def _board_legacy_day_operations(self, team, day):
        """The route order used by ``field_operation_geolocation`` 19.0.1.6.x."""
        Operation = self.env["field.operation"]
        operations = Operation.search(
            [("team_id", "=", team.id), ("status", "not in", ("done", "cancel"))]
            + Operation._plan_day_domain(day),
            order="start_date asc, sequence asc, id asc",
        )
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

    def _board_team_data(self, day, used_colors):
        """Everything the board shows for one team on one day."""
        self.ensure_one()
        operations = self._board_day_operations(self, day)
        start = self._board_start_info()
        start_point = (
            (start["lat"], start["lon"]) if start["has_start"] else None
        )
        color_index, color = self._board_color(self, used_colors)

        stops = []
        geometry = [start_point] if start_point else []
        previous = start_point
        last_point = None
        total_km = 0.0
        for sequence, operation in enumerate(operations, 1):
            point = geo_helpers.record_point(operation)
            leg_km = geo_helpers.haversine_km(previous, point)
            total_km += leg_km
            if point:
                previous = point
                last_point = point
                geometry.append(point)
            stops.append(self._board_stop_info(operation, sequence, leg_km))

        return_km = 0.0
        if start_point and last_point:
            return_km = geo_helpers.haversine_km(last_point, start_point)
            total_km += return_km
            geometry.append(start_point)

        return {
            "id": self.id,
            "name": self.name,
            "region": self.region_id.name or "",
            "color_index": color_index,
            "color": color,
            "total_km": round(total_km, 1),
            "return_km": round(return_km, 1),
            "stops_total": len(stops),
            "stops_missing": sum(1 for stop in stops if not stop["located"]),
            "route_saved": any(
                operation.route_sequence for operation in operations
            ),
            "start": start,
            # A day without a usable start point still draws a route, but the
            # dispatcher must see that it is not the usual home/depot loop.
            "start_fallback": not start["has_start"],
            "stops": stops,
            "geometry": geometry,
            "live": self._board_live_info(),
        }

    @api.model
    def _day_board_data(self, day=None, team_ids=None):
        """The whole day for the board: teams, stops, geometry and live state.

        :param day: a date (or ISO string); defaults to the user's today.
        :param team_ids: optional list of team ids to restrict the payload.
        """
        self._board_check_access()
        if day:
            try:
                day = fields.Date.to_date(day)
            except (TypeError, ValueError) as error:
                raise UserError(_("Invalid day: %s") % day) from error
        else:
            day = fields.Date.context_today(self)

        teams = self.search(
            self._board_team_domain(team_ids), order="sequence, id"
        )

        used_colors = set()
        payload_teams = [
            team._board_team_data(day, used_colors) for team in teams
        ]

        Operation = self.env["field.operation"]
        unassigned = Operation.search_count(
            [("team_id", "=", False), ("status", "not in", ("done", "cancel"))]
            + Operation._plan_day_domain(day)
        )
        return {
            "date": fields.Date.to_string(day),
            "generated_at": fields.Datetime.to_string(fields.Datetime.now()),
            "teams": payload_teams,
            "unassigned": unassigned,
            "map": self._board_map_config(),
        }

    @api.model
    def _live_positions(self, team_ids=None):
        """Only the live positions, for the small polling request."""
        self._board_check_access()
        positions = {}
        for team in self.search(self._board_team_domain(team_ids)):
            live = team._board_live_info()
            if live:
                positions[team.id] = live
        return {
            "generated_at": fields.Datetime.to_string(fields.Datetime.now()),
            "teams": positions,
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_open_day_board(self):
        """Open the board on this team's day (team form button)."""
        self.ensure_one()
        self._board_check_access()
        return {
            "type": "ir.actions.client",
            "name": _("Daily Routes"),
            "tag": "field_operation_geolocation_board.day_board",
            "params": {"team_id": self.id},
        }
