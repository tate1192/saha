"""The service form shortcuts this module owns (they used to live in geolocation)."""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestServiceFormShortcuts(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Forms = cls.env["field.operation.forms"]
        cls.provider = cls.env["maps.website"].search([], limit=1)
        if not cls.provider:
            cls.provider = cls.env["maps.website"].create(
                {
                    "name": "Test Map",
                    "lat_lon_url": "https://example.com/?lat={LATITUDE}&lon={LONGITUDE}",
                }
            )
        cls.env.user.map_website_id = cls.provider
        cls.address = cls.env["res.partner"].create(
            {
                "name": "Form Shortcut Address",
                "partner_latitude": 41.0082,
                "partner_longitude": 28.9784,
            }
        )
        cls.form = cls.Forms.create(cls._form_vals(address_id=cls.address.id))

    @classmethod
    def _form_vals(cls, **overrides):
        """Vals for a form, plus the picking type when that suite adds it."""
        vals = dict(overrides)
        if "picking_type_id" in cls.Forms._fields:
            vals["picking_type_id"] = (
                cls.env["stock.picking.type"].search([], limit=1).id
            )
        return vals

    def _arch(self, xmlid, view_type):
        view = self.env.ref(xmlid)
        views = self.Forms.get_views([(view.id, view_type)])
        return views["views"][view_type]["arch"]

    def test_the_shortcuts_are_in_the_views(self):
        list_arch = self._arch(
            "field_operation_forms.field_operation_forms_list_view", "list"
        )
        form_arch = self._arch(
            "field_operation_forms.field_operation_forms_form_view", "form"
        )
        self.assertEqual(list_arch.count("action_open_map"), 1)
        self.assertEqual(form_arch.count("action_open_map"), 1)
        self.assertEqual(form_arch.count("action_geolocate_address"), 1)
        self.assertNotIn(
            "action_message_send",
            list_arch + form_arch,
            "the WhatsApp shortcut was removed with the dependency",
        )

    def test_the_map_url_carries_the_record_coordinates(self):
        result = self.form.action_open_map()
        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertEqual(result["target"], "new")
        self.assertIn("lat=41.0082", result["url"])
        self.assertIn("lon=28.9784", result["url"])
        for placeholder in ("{LATITUDE}", "{LONGITUDE}", "{API_KEY}"):
            self.assertNotIn(placeholder, result["url"])

    def test_a_pair_of_zeros_is_refused(self):
        self.address.write({"partner_latitude": 0.0, "partner_longitude": 0.0})
        with self.assertRaises(UserError):
            self.form.action_open_map()

    def test_geolocating_reports_a_missing_match_instead_of_success(self):
        address = self.env["res.partner"].create(
            {"name": "Nowhere", "street": "Unknown street", "city": "Nowhere"}
        )
        form = self.Forms.create(self._form_vals(address_id=address.id))
        result = form.action_geolocate_address()
        self.assertEqual(result["params"]["type"], "warning")

    def test_geolocating_reports_success_when_the_address_was_located(self):
        address = self.env["res.partner"].create(
            {"name": "Locatable", "street": "Some street", "city": "Somewhere"}
        )
        form = self.Forms.create(self._form_vals(address_id=address.id))
        with patch.object(
            type(self.env["res.partner"]), "_geo_localize", return_value=(41.0, 29.0)
        ):
            result = form.with_context(
                force_geo_localize=True
            ).action_geolocate_address()
        self.assertEqual(result["params"]["type"], "success")
        self.assertEqual(address.partner_latitude, 41.0)
        self.assertEqual(form.service_latitude, 41.0)
