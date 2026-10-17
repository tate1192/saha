"""The team-side map actions follow the module's coordinate rule.

``action_show_on_map`` and ``action_show_team_locations`` used to repeat the
"a pair of zeros means no coordinate" test inline, and neither was covered:
the forms model pinned the same rule with a test
(``test_a_lone_zero_latitude_is_still_a_coordinate``) while the team side had
none. Both actions now go through ``geo_helpers.has_point`` and are covered
here, so a revert to a truthiness test (which would reject ``lat=0.0``, the
equator) breaks a test instead of passing silently.
"""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTeamMapActions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["maps.website"].search([], limit=1)
        cls.env.user.map_website_id = cls.provider
        cls.env.user.multi_locations_map_website_id = cls.provider
        Teams = cls.env["field.operation.team"]
        cls.equator = Teams.create(
            {"name": "Equator Team", "latitude": 0.0, "longitude": 29.03}
        )
        cls.unlocated = Teams.create({"name": "Unlocated Team"})

    def test_a_lone_zero_latitude_is_still_a_coordinate(self):
        """``lat=0.0`` is the equator: the action builds the URL, not an error."""
        result = self.equator.action_show_on_map()
        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertEqual(result["target"], "new")
        self.assertIn("0.0", result["url"])
        self.assertIn("29.03", result["url"])
        for placeholder in ("{LATITUDE}", "{LONGITUDE}", "{API_KEY}"):
            self.assertNotIn(placeholder, result["url"])

    def test_a_pair_of_zeros_counts_as_missing_coordinates(self):
        """Both zeros mean "no coordinates": the ORM cannot tell them from NULL."""
        with self.assertRaises(UserError):
            self.unlocated.action_show_on_map()

    def test_the_multi_location_action_keeps_the_equator_team(self):
        """A team at ``lat=0.0`` belongs in the markers; only (0, 0) is filtered."""
        with patch.object(
            type(self.provider),
            "_get_multi_location_marker_url",
            return_value="https://example.test/map",
        ) as marker_url:
            result = (self.equator | self.unlocated).action_show_team_locations()

        self.assertEqual(result["type"], "ir.actions.act_url")
        coordinates = marker_url.call_args[0][0]
        self.assertEqual([point[:2] for point in coordinates], [(0.0, 29.03)])

    def test_the_multi_location_action_needs_one_located_team(self):
        """With no located team there is nothing to draw."""
        with self.assertRaises(UserError):
            self.unlocated.action_show_team_locations()
