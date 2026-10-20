import logging
from datetime import timedelta
from typing import Any

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import geo_helpers

_logger = logging.getLogger(__name__)


class FieldOperation(models.Model):
    """Map, route and geolocation actions for the operation model.

    The shared parts live in ``geo_helpers`` so another module can expose the
    same map/geolocation actions on a different model without a second copy.

    This is also the model a dispatcher plans the day on: every operation
    carries the coordinates of its service address, so the day's stops can be
    ordered (``route_sequence``) and drawn on a map without any routing service.
    """

    _inherit = "field.operation"

    route_sequence = fields.Integer(
        string="Route Order",
        default=0,
        help="Manual position of this operation in its day's route. Zero means "
        "the route keeps the planned start time order; a dispatcher who fixes "
        "a zig-zagging route stores explicit values here.",
    )
    is_located = fields.Boolean(
        string="Located",
        compute="_compute_is_located",
        store=True,
        help="Whether the service address carries usable coordinates. Stored so "
        "the dispatcher can filter and group on it; the rule itself lives in "
        "geo_helpers.has_coordinates.",
    )

    @api.depends("service_latitude", "service_longitude")
    def _compute_is_located(self):
        for operation in self:
            operation.is_located = geo_helpers.has_coordinates(operation)

    @api.onchange("address_id")
    def _onchange_address_id(self):
        warning = {}
        for operation in self:
            if not operation.address_id:
                continue
            # Skip when the operation already carries coordinates (the pair of
            # zeros means "none": see geo_helpers.has_point).
            if geo_helpers.has_coordinates(operation):
                continue
            try:
                result = operation.address_id.geo_localize()
                if result:
                    operation.date_localization = fields.Datetime.now()
                    _logger.info(
                        "Geolocation successful for operation %s", operation.name
                    )
                else:
                    warning = {
                        "warning": {
                            "title": _("Location Not Found"),
                            "message": _(
                                "No geographic coordinates could be found "
                                "automatically for the selected address."
                            ),
                        }
                    }
            except UserError as error:
                _logger.warning(
                    "Geolocation failed for address %s: %s",
                    operation.address_id.id,
                    error,
                )
                warning = {
                    "warning": {
                        "title": _("Error"),
                        "message": _(
                            "An error occurred while retrieving the location: %s"
                        )
                        % error,
                    }
                }
        if warning:
            return warning
        return {}

    @api.model
    def _plan_day_domain(self, day):
        """Domain of the operations that overlap ``day`` (a date in user time).

        A job that started yesterday and still runs today belongs to today's
        plan, so the filter is an interval overlap and not ``start_date is
        today``. A job without an end date counts as still running, but only
        from the day after it started: most of the open jobs in this database
        carry no end date, and pulling all of them into every day would bury
        the day's real stops. Unscheduled operations have no ``start_date`` and
        are therefore never part of a day.
        """
        day_end = day + timedelta(days=1)
        previous_day = day - timedelta(days=1)
        return [
            "&",
            ("start_date", "<", day_end),
            "|",
            "|",
            ("start_date", ">=", day),
            ("end_date", ">=", day),
            "&",
            ("end_date", "=", False),
            ("start_date", ">=", previous_day),
        ]

    def _sorted_for_route(self):
        """The records in driving order: saved route order, then start time.

        A record with a saved ``route_sequence`` keeps its place; the records
        without one (added after the route was saved, or never sequenced) come
        last by start time instead of silently resetting the whole order.
        Records without a start time follow at the very end.
        """
        sequenced = self.filtered("route_sequence").sorted(
            lambda operation: (
                operation.route_sequence,
                operation.start_date,
                operation.sequence or 0,
                operation.id or 0,
            )
        )
        remaining = (
            (self - sequenced)
            .filtered("start_date")
            .sorted(
                lambda operation: (
                    operation.start_date,
                    operation.sequence or 0,
                    operation.id or 0,
                )
            )
        )
        unscheduled = (self - sequenced - remaining).sorted(
            lambda operation: (operation.sequence or 0, operation.id or 0)
        )
        return self.browse(
            [operation.id for operation in sequenced + remaining + unscheduled]
        )

    def _shared_start_point(self):
        """The depot of the selection's single team, when it has one.

        A route usually starts at the team's base, not at the first customer.
        Only used when the whole selection belongs to one team; a mixed
        selection keeps its first stop as the start.
        """
        teams = self.team_id
        if len(teams) == 1:
            return teams._route_start_point()
        return None

    def _route_url_for_records(self, maps_website, records, start_point=None):
        """Route URL through the located records, optionally from a start point.

        When a start point is known the route is closed: it ends at the same
        point it started from, which is how a day that leaves from and returns
        to home or the office is drawn.
        """
        located = records.filtered("is_located")
        if len(located) < 2:
            return False
        points = []
        if start_point:
            points.append(start_point)
        points.extend(
            (float(operation.service_latitude), float(operation.service_longitude))
            for operation in located
        )
        if start_point:
            points.append(start_point)
        return maps_website._get_route_url_for_points(points)

    def _notify_missing_stops(self):
        """Tell the user which stops were left out of the route (and why)."""
        names = self.mapped("display_name")
        self.env.user._bus_send(
            "simple_notification",
            {
                "type": "warning",
                "title": _("Route is incomplete"),
                "message": _(
                    "%(count)s operation(s) have no coordinates and were left "
                    "out: %(names)s",
                    count=len(names),
                    names=", ".join(names[:5]),
                ),
                "sticky": True,
            },
        )

    def action_open_map(self) -> dict[str, Any]:
        """Open this operation's coordinates in the user's map provider."""
        self.ensure_one()
        return geo_helpers.open_map_action(self)

    def action_show_multi_locations_mark(self) -> dict[str, Any]:
        if not self:
            raise UserError(_("No records selected."))

        maps_website = (
            self.env.user.multi_locations_map_website_id or self.env.user.map_website_id
        )
        if not maps_website:
            raise UserError(_("Please configure a Multi-Location Map Provider."))

        coordinates = []
        for record in self:
            if geo_helpers.has_coordinates(record):
                coordinates.append(
                    (
                        float(record.service_latitude),
                        float(record.service_longitude),
                        record.display_name or "",
                    )
                )

        if not coordinates:
            raise UserError(_("No valid coordinates found."))

        url = maps_website._get_multi_location_marker_url(coordinates)
        if not url:
            raise UserError(
                _("The selected map provider does not support multi-markers.")
            )

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_show_selected_routes(self) -> dict[str, Any]:
        """Show the selected operations as one route, in driving order.

        The order is the manual route order when a dispatcher saved one, and
        the planned start time otherwise; the recordset order a list happens to
        arrive in is never the route. Stops without coordinates are left out
        with a warning instead of aborting the whole route: one unlocated job
        must not hide the other nine.
        """
        if not self or len(self) < 2:
            raise UserError(
                _("Please select at least 2 operations for route planning.")
            )

        maps_website = self.env.user.route_map_website_id
        if not maps_website:
            raise UserError(_("Please configure a Route Map Provider."))

        records = self._sorted_for_route()
        located = records.filtered("is_located")
        missing = records - located
        if len(located) < 2:
            raise UserError(
                _("At least 2 selected operations need coordinates to build a route.")
            )

        url = self._route_url_for_records(
            maps_website, located, start_point=self._shared_start_point()
        )
        if not url:
            raise UserError(_("Map provider does not support multi-point routing."))

        if missing:
            missing._notify_missing_stops()

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_open_route_plan(self):
        """Open the daily planner on the team and day of this selection.

        The office works from the Field Service list: selecting a few rows (a
        team's day) and opening the planner from there must land on that day,
        not on an empty dialog that asks for a team and a date again. Without a
        selection the planner falls back to today and the user's team.
        """
        if self:
            record = self[0]
            team = record.team_id
            if record.start_date:
                day = fields.Datetime.context_timestamp(self, record.start_date).date()
            else:
                day = fields.Date.context_today(self)
        else:
            team = self.env["field.operation.team"]
            day = fields.Date.context_today(self)
        context = {"default_date": day.isoformat()}
        if team:
            context["default_team_id"] = team.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Route Plan"),
            "res_model": "field.operation.route.plan",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def action_geolocate_operation(self):
        """Geolocate the service address and report what actually happened."""
        self.ensure_one()
        geo_helpers.geolocate_service_address(self)
        self.date_localization = fields.Datetime.now()
        return geo_helpers.geolocation_notification(self)

    def action_geolocate_selected(self):
        """Geolocate every selected operation that still has no coordinates."""
        targets = self.filtered(
            lambda operation: operation.address_id and not operation.is_located
        )
        if not targets:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Nothing to do"),
                    "message": _(
                        "The selected operations already have coordinates or "
                        "have no service address."
                    ),
                    "type": "info",
                    "sticky": False,
                },
            }

        located = self.env["field.operation"]
        failed = self.env["field.operation"]
        for operation in targets:
            try:
                geo_helpers.geolocate_service_address(operation)
            except UserError as error:
                _logger.warning(
                    "Bulk geolocation failed for %s: %s", operation.name, error
                )
                failed |= operation
                continue
            if geo_helpers.has_coordinates(operation):
                operation.date_localization = fields.Datetime.now()
                located |= operation
            else:
                failed |= operation

        if failed:
            message = _(
                "%(located)s of %(total)s operations located; %(failed)s could "
                "not be found: %(names)s",
                located=len(located),
                total=len(targets),
                failed=len(failed),
                names=", ".join(failed.mapped("display_name")[:5]),
            )
        else:
            message = _(
                "%(located)s of %(total)s operations located.",
                located=len(located),
                total=len(targets),
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Geolocation") if not failed else _("Location Not Found"),
                "message": message,
                "type": "success" if not failed else "warning",
                "sticky": bool(failed),
            },
        }
