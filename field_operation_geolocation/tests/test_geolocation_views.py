"""The views of this module must only use widgets Odoo 19 actually ships.

``boolean_button`` was removed from the web client before 19.0: an unknown widget
name is not an error, ``getFieldFromRegistry`` falls back to the type's default
widget and logs ``Missing widget: ...`` in the browser console
(``web/static/src/views/fields/field.js:140``), so a dead widget hides in plain
sight. Both places that used it are asserted here, and the same pattern was
already fixed in ``field_operation_whatsapp`` (its test keeps that module honest).
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGeolocationViewWidgets(TransactionCase):
    def _arch(self, xmlid):
        return str(self.env.ref(xmlid).arch)

    def test_the_team_form_shows_the_computed_online_flag_with_a_shipped_widget(self):
        """``is_online`` is a computed, read-only boolean: it needs a display widget."""
        arch = self._arch(
            "field_operation_geolocation.view_field_operation_geolocation_team_form"
        )
        self.assertNotIn("boolean_button", arch)
        self.assertIn('name="is_online"', arch)
        self.assertIn("boolean_toggle", arch)
        self.assertIn('readonly="1"', arch)

    def test_the_map_website_list_keeps_an_editable_archive_toggle(self):
        arch = self._arch("field_operation_geolocation.geolocation_map_website_list")
        self.assertNotIn("boolean_button", arch)
        self.assertIn('name="active"', arch)
        self.assertIn("boolean_toggle", arch)

    def test_the_operation_form_offers_the_geolocate_button(self):
        """The geolocate action must be reachable from the form (not RPC-only).

        It was defined on the model with no button anywhere: the only way to
        (re)trigger a geolocation was the address onchange, which does not fire
        when the address did not change. The forms model already had its button;
        this asserts the operation form now matches it.
        """
        arch = self._arch("field_operation_geolocation.view_field_operation_route_form")
        self.assertIn('name="action_geolocate_operation"', arch)
        self.assertIn('name="action_open_map"', arch)
