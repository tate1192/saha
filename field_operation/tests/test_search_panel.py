"""The search panel's team category must not list archived teams."""

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSearchPanelTeams(TransactionCase):
    def test_archived_teams_are_not_listed(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Panel Customer",
                "partner_latitude": 41.0,
                "partner_longitude": 29.0,
            }
        )
        active_team = self.env["field.operation.team"].create(
            {"name": "Active Panel Team"}
        )
        archived_team = self.env["field.operation.team"].create(
            {"name": "Archived Panel Team"}
        )
        for team in active_team | archived_team:
            self.env["field.operation"].create(
                {
                    "subject": f"Job {team.name}",
                    "partner_id": partner.id,
                    "team_id": team.id,
                    "start_date": fields.Datetime.now(),
                }
            )
        archived_team.active = False

        result = self.env["field.operation"].search_panel_select_range(
            "team_id", search_domain=[], enable_counters=True
        )
        ids = [value["id"] for value in result["values"]]
        self.assertIn(active_team.id, ids)
        self.assertNotIn(
            archived_team.id, ids, "an archived team is still in the search panel"
        )
