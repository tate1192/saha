from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = "res.users"

    def _get_map_provider(self, map_field="map_website_id"):
        """The map provider this user picked, or a clear error when there is none.

        Shared by every model that opens a map link (``field.operation`` here,
        and the service form extension in its own module): the action is useless
        without a provider, and the message must tell the user where to set one.
        """
        self.ensure_one()
        provider = self[map_field]
        if not provider:
            raise UserError(
                _(
                    "Map provider is not configured. "
                    "Please set it in your user preferences."
                )
            )
        return provider

    map_website_id = fields.Many2one(
        "maps.website",
        string="Default Map Provider",
        default=lambda self: self._default_map_website(),
        domain=[("lat_lon_url", "!=", False), ("active", "=", True)],
    )

    multi_locations_map_website_id = fields.Many2one(
        "maps.website",
        string="Multi-Location Map Provider",
        default=lambda self: self._default_map_website(),
        domain=[("active", "=", True)],
    )

    route_map_website_id = fields.Many2one(
        "maps.website",
        string="Default Route Map Provider",
        default=lambda self: self._default_route_map_website(),
        domain=[("route_lat_lon_url", "!=", False), ("active", "=", True)],
    )

    @api.model
    def _default_map_website(self):
        """Return the default map provider, preferring OpenStreetMap.

        Archived providers are excluded so a decommissioned entry is never
        picked as the default.
        """
        osm = self.env["maps.website"].search(
            [
                ("provider_type", "=", "openstreetmap"),
                ("active", "=", True),
            ],
            limit=1,
        )
        return osm or self.env["maps.website"].search(
            [("active", "=", True)], limit=1, order="sequence, id"
        )

    @api.model
    def _default_route_map_website(self):
        """Return the default route map provider, preferring OpenStreetMap."""
        osm = self.env["maps.website"].search(
            [
                ("provider_type", "=", "openstreetmap"),
                ("route_lat_lon_url", "!=", False),
                ("active", "=", True),
            ],
            limit=1,
        )
        return osm or self._default_map_website()

    def action_set_default_map_settings(self):
        """Reset the current user's map settings to the defaults (OpenStreetMap)."""
        self.ensure_one()
        default_map = self._default_map_website()
        default_route_map = self._default_route_map_website()

        update_vals = {}
        if default_map:
            update_vals["map_website_id"] = default_map.id
            update_vals["multi_locations_map_website_id"] = default_map.id
        if default_route_map:
            update_vals["route_map_website_id"] = default_route_map.id

        if update_vals:
            self.write(update_vals)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Map Settings Updated"),
                "message": _("Default map settings (OpenStreetMap) applied."),
                "type": "success",
                "sticky": False,
            },
        }
