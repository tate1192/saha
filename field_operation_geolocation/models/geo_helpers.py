"""Helpers shared by the models that expose the map and geolocation actions.

Several models carry the coordinates of their service address and offer the same
two buttons; the logic behind them lives here (with the URL building in
``maps.website`` and the provider lookup in ``res.users``) instead of in one copy
per model. ``field.operation`` uses it directly; the service form model is
extended by another module that reuses the same helpers.

These are plain functions rather than an ``AbstractModel`` mixin on purpose.
An abstract mixin that defines no field of its own is not part of the
``models_to_check`` reflection pass, so while the models extending it are
reflected the mixin is not, ``_reflect_inherits`` then writes an
``ir_model_inherit`` row with a NULL parent and the registry refuses to load.
A plain Python mixin class is not an option either, because Odoo 19 reassigns
``Model.__bases__`` during setup.

The distance helpers at the bottom back the daily route planner: they only need
the stored coordinates, so no external routing service (and no API key) is
involved in telling a dispatcher that a stop order zig-zags across the city.
"""

from itertools import pairwise
from math import asin, cos, radians, sin, sqrt

from odoo import _
from odoo.exceptions import UserError

# Mean earth radius, kilometres.
EARTH_RADIUS_KM = 6371.0

# A stop order is reported as geographically inconsistent only when a better
# order saves at least this much driving *and* this share of the current route.
# Small savings are noise: reordering a route around a one-way street or a
# bridge toll still costs more in practice than the few kilometres saved.
ROUTE_MIN_SAVING_KM = 5.0
ROUTE_MIN_SAVING_RATIO = 0.15


def has_point(latitude, longitude) -> bool:
    """Whether a latitude/longitude pair is a usable coordinate.

    A Float column cannot tell a missing value from ``0.0`` through the ORM:
    the column is NULL in the database but reads back as ``0.0``, so ``is None``
    never matches and a truthiness test would reject a valid latitude of ``0.0``
    (equator / prime meridian). A pair of zeros is therefore treated as "no
    coordinates" - a point exactly on (0, 0) does not occur - while ``lat=0.0``
    with a real longitude stays valid.

    Callers that hold the two values instead of a record with the
    ``service_*`` field names (``field.operation.team`` keeps plain
    ``latitude``/``longitude``) use this; :func:`has_coordinates` wraps it for
    the service-address models.
    """
    return bool(latitude or longitude)


def has_coordinates(record) -> bool:
    """Whether the record carries usable coordinates (see :func:`has_point`)."""
    record.ensure_one()
    return has_point(record.service_latitude, record.service_longitude)


def record_point(record):
    """The record's ``(latitude, longitude)`` pair, or None when it has none."""
    if not has_coordinates(record):
        return None
    return (float(record.service_latitude), float(record.service_longitude))


def coordinates_or_error(record) -> dict[str, float]:
    """The record's coordinates, or a ``UserError`` naming the record."""
    if not has_coordinates(record):
        raise UserError(
            _("Missing coordinates for operation '%s'.") % record.display_name
        )
    return {
        "latitude": float(record.service_latitude),
        "longitude": float(record.service_longitude),
    }


def open_map_action(record) -> dict:
    """Open the record's coordinates in the map provider of the current user."""
    record.ensure_one()
    maps_website = record.env.user._get_map_provider()
    coordinates = coordinates_or_error(record)
    url = maps_website._get_lat_lon_url(
        coordinates["latitude"], coordinates["longitude"]
    )
    if not url:
        raise UserError(
            _("Map provider '%s' is not properly configured.") % maps_website.name
        )
    return {"type": "ir.actions.act_url", "url": url, "target": "new"}


def geolocate_service_address(record):
    """Geolocate the record's service address in place.

    ``res.partner.geo_localize`` reports "no match" with a bus notification
    instead of raising, so callers must check ``has_coordinates(record)``
    afterwards to know whether it actually worked.
    """
    record.ensure_one()
    if not record.address_id:
        raise UserError(_("Please select an address first."))
    try:
        return record.address_id.geo_localize()
    except UserError as error:
        raise UserError(
            _("Geolocation failed: %(error)s") % {"error": error}
        ) from error


def geolocation_notification(record) -> dict:
    """The notification for a finished geolocation attempt.

    ``geo_localize`` does not raise when the address cannot be matched, so a
    success toast would be a claim the code cannot back up.
    """
    if has_coordinates(record):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Geolocation completed successfully."),
                "type": "success",
                "sticky": False,
            },
        }
    return {
        "type": "ir.actions.client",
        "tag": "display_notification",
        "params": {
            "title": _("Location Not Found"),
            "message": _("No coordinates could be found for the selected address."),
            "type": "warning",
            "sticky": False,
        },
    }


# ---------------------------------------------------------------------------
# Distance and stop-order helpers (daily route planner)
# ---------------------------------------------------------------------------


def haversine_km(first, second) -> float:
    """Great-circle distance in kilometres between two ``(lat, lon)`` points."""
    if not first or not second:
        return 0.0
    lat1, lon1 = first
    lat2, lon2 = second
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    haversine = (
        sin(delta_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(haversine))


def route_length_km(points, end=None) -> float:
    """Total length of the polyline through ``points`` (None entries skipped).

    ``end`` closes the tour with a return leg from the last usable point, which
    is how a route that starts and ends at home is measured.
    """
    usable = [point for point in points if point]
    length = sum(haversine_km(first, second) for first, second in pairwise(usable))
    if end and usable:
        length += haversine_km(usable[-1], end)
    return length


def path_length_km(points, order=None, start=None, end=None) -> float:
    """Length of the route visiting ``points`` in the given ``order``.

    ``start`` is an optional start point and ``end`` an optional return point;
    ``order`` indexes into ``points`` and defaults to the current order. Points
    that are None (a stop without coordinates) are skipped, exactly as the URL
    builders do.
    """
    indexes = range(len(points)) if order is None else order
    route = ([start] if start else []) + [
        points[index] for index in indexes if points[index]
    ]
    return route_length_km(route, end=end)


def suggest_route_order(points, start=None, end=None):
    """A shorter visiting order for ``points``, as a list of indexes.

    Nearest-neighbour from ``start`` (or from the first stop when no start is
    known) followed by a 2-opt pass. When ``end`` is given the tour is closed:
    the cost includes the leg from the last stop back to ``end``, so a stop
    next to the office/home is not left as the last one of the day. Stops
    without coordinates are appended at the end in their original order, so a
    dispatcher still sees them.

    The first stop stays first when there is no start point: the dispatcher
    planned the day around that first appointment, and a suggestion that also
    moves the starting point is a bigger change than the warning asked for.
    """
    located = [index for index, point in enumerate(points) if point]
    missing = [index for index, point in enumerate(points) if not point]
    if len(located) < 3:
        return located + missing
    order = _nearest_neighbour_order(points, located, start)
    order = _two_opt_order(points, order, start, end)
    return order + missing


def distance_gain_is_significant(current_km, suggested_km) -> bool:
    """Whether a suggested order saves enough driving to be worth reporting."""
    if not current_km or suggested_km is None:
        return False
    saving = current_km - suggested_km
    return (
        saving >= ROUTE_MIN_SAVING_KM and saving / current_km >= ROUTE_MIN_SAVING_RATIO
    )


def _nearest_neighbour_order(points, located, start):
    remaining = list(located)
    if start:
        order = []
        current = start
    else:
        first = remaining.pop(0)
        order = [first]
        current = points[first]
    while remaining:
        nearest = min(remaining, key=lambda index: haversine_km(current, points[index]))
        remaining.remove(nearest)
        order.append(nearest)
        current = points[nearest]
    return order


def _two_opt_order(points, order, start, end=None, max_passes=50):
    """Improve ``order`` by reversing segments while that shortens the path."""
    order = list(order)
    # Without a start point the first stop is the anchor and must not move.
    first_movable = 1 if start is None else 0
    best = path_length_km(points, order, start, end)
    for _pass in range(max_passes):
        improved = False
        for i in range(first_movable, len(order) - 1):
            for j in range(i + 1, len(order)):
                candidate = (
                    order[:i] + list(reversed(order[i : j + 1])) + order[j + 1 :]
                )
                length = path_length_km(points, candidate, start, end)
                if length < best - 1e-9:
                    order = candidate
                    best = length
                    improved = True
        if not improved:
            break
    return order
