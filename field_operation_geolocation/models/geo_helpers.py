"""Helpers shared by the models that expose the map and geolocation actions.

``field.operation`` and ``field.operation.forms`` both carry the coordinates of
the service address and both offer the same two buttons; the logic behind them
lives here (with the URL building in ``maps.website`` and the provider lookup in
``res.users``) instead of in one copy per model.

These are plain functions rather than an ``AbstractModel`` mixin on purpose.
An abstract mixin that defines no field of its own is not part of the
``models_to_check`` reflection pass, so while the models extending it are
reflected the mixin is not, ``_reflect_inherits`` then writes an
``ir_model_inherit`` row with a NULL parent and the registry refuses to load.
A plain Python mixin class is not an option either, because Odoo 19 reassigns
``Model.__bases__`` during setup.
"""

from odoo import _
from odoo.exceptions import UserError


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
