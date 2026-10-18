from odoo import api, fields, models

from odoo.addons.field_operation_geolocation.models import geo_helpers


class FieldOperationForms(models.Model):
    """Map and geolocation shortcuts for the service form.

    The heavy lifting (provider lookup, coordinate rule, URL placeholders, the
    honest geolocation notification) lives in the geolocation module's
    ``geo_helpers``; this module only exposes it on ``field.operation.forms``.
    """

    _inherit = "field.operation.forms"

    service_latitude = fields.Float(
        related="address_id.partner_latitude", store=True, string="Latitude"
    )
    service_longitude = fields.Float(
        related="address_id.partner_longitude", store=True, string="Longitude"
    )
    display_address = fields.Char(compute="_compute_display_address")

    @api.depends("address_id")
    def _compute_display_address(self):
        for operation in self:
            if operation.address_id:
                operation.display_address = operation.address_id._display_address(
                    without_company=True
                )
            else:
                operation.display_address = False

    def action_open_map(self):
        """Open the service address in the user's map provider."""
        self.ensure_one()
        return geo_helpers.open_map_action(self)

    def action_geolocate_address(self):
        """Geolocate the service address and report what actually happened."""
        self.ensure_one()
        geo_helpers.geolocate_service_address(self)
        return geo_helpers.geolocation_notification(self)
