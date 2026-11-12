from datetime import datetime, time, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

TUZLA = (40.817, 29.3)
PENDIK = (40.877, 29.232)
HOME = (40.99, 29.13)


@tagged("post_install", "-at_install")
class TestDayBoard(TransactionCase):
    """The payload the dispatcher map board draws."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.tz = "Europe/Istanbul"
        cls.day = fields.Date.context_today(cls.env.user)
        cls.company_partner = cls.env.company.partner_id
        cls.company_partner.write(
            {"partner_latitude": TUZLA[0], "partner_longitude": TUZLA[1]}
        )
        cls.team = cls.env["field.operation.team"].create(
            {
                "name": "Board Team",
                "route_start_mode": "company",
                "color": 4,
                "base_location_id": False,
            }
        )
        cls.located_partner = cls.env["res.partner"].create(
            {
                "name": "Board Customer",
                "partner_latitude": PENDIK[0],
                "partner_longitude": PENDIK[1],
            }
        )
        cls.unlocated_partner = cls.env["res.partner"].create(
            {"name": "Board No Coordinates", "street": "Some Street", "city": "Istanbul"}
        )
        cls.early = cls._create_operation("Early Stop", cls.located_partner, 9)
        cls.late = cls._create_operation("Late Stop", cls.located_partner, 11)

    @classmethod
    def _create_operation(cls, subject, partner, hour):
        return cls.env["field.operation"].create(
            {
                "subject": subject,
                "partner_id": partner.id,
                "team_id": cls.team.id,
                "start_date": fields.Datetime.to_datetime(
                    datetime.combine(cls.day, time(hour))
                ),
                "status": "planned",
            }
        )

    def _board(self):
        return (
            self.env["field.operation.team"]
            .with_user(self.env.user)
            ._day_board_data(self.day, team_ids=[self.team.id])
        )

    def _team_payload(self, payload=None):
        payload = payload or self._board()
        return next(team for team in payload["teams"] if team["id"] == self.team.id)

    # ------------------------------------------------------------------
    # Order and geometry
    # ------------------------------------------------------------------
    def test_stops_follow_the_saved_route_sequence(self):
        self.late.route_sequence = 10
        self.early.route_sequence = 20
        team = self._team_payload()
        self.assertEqual(
            [stop["operation_id"] for stop in team["stops"]],
            [self.late.id, self.early.id],
            "the board must honour the dispatcher's saved order",
        )
        self.assertTrue(team["route_saved"])

    def test_stops_without_a_saved_order_follow_the_start_time(self):
        team = self._team_payload()
        self.assertEqual(
            [stop["operation_id"] for stop in team["stops"]],
            [self.early.id, self.late.id],
        )
        self.assertFalse(team["route_saved"], "no manual order was saved")

    def test_route_is_a_closed_loop_starting_at_the_company(self):
        team = self._team_payload()
        self.assertEqual(team["start"]["kind"], "company")
        self.assertEqual(
            list(team["geometry"][0]),
            [TUZLA[0], TUZLA[1]],
            "the loop must start at the team's start point",
        )
        self.assertEqual(
            list(team["geometry"][-1]),
            [TUZLA[0], TUZLA[1]],
            "the loop must come back to the start point",
        )
        self.assertGreater(team["total_km"], 0)

    def test_a_stop_without_coordinates_is_left_out_of_the_geometry(self):
        unlocated = self._create_operation("No Coordinates", self.unlocated_partner, 13)
        team = self._team_payload()
        self.assertEqual(team["stops_missing"], 1)
        self.assertEqual(
            len(team["geometry"]),
            4,
            "start + two located stops + return = 4 points",
        )
        self.assertNotIn(
            unlocated.id,
            [stop["operation_id"] for stop in team["stops"] if stop["located"]],
        )

    def test_a_team_without_a_located_home_starts_at_the_company(self):
        employee = self.env["hr.employee"].create({"name": "Board Head"})
        team = self.env["field.operation.team"].create(
            {"name": "Home Board Team", "team_head_id": employee.id}
        )
        self.env["field.operation"].create(
            {
                "subject": "Home Stop",
                "partner_id": self.located_partner.id,
                "team_id": team.id,
                "start_date": fields.Datetime.to_datetime(
                    datetime.combine(self.day, time(10))
                ),
            }
        )
        payload = self.env["field.operation.team"]._day_board_data(
            self.day, team_ids=[team.id]
        )
        team_payload = next(item for item in payload["teams"] if item["id"] == team.id)
        self.assertEqual(
            team_payload["start"]["kind"],
            "company",
            "a team without a located home must fall back to the company",
        )
        self.assertTrue(team_payload["geometry"])

    # ------------------------------------------------------------------
    # Colours, map config and payload shape
    # ------------------------------------------------------------------
    def test_the_board_uses_the_kanban_colour_of_the_team(self):
        team = self._team_payload()
        self.assertEqual(team["color_index"], 4)
        self.assertEqual(team["color"], "#5794dd")

    def test_a_team_without_colour_gets_an_automatic_one(self):
        self.team.color = 0
        team = self._team_payload()
        self.assertRegex(team["color"], r"^#[0-9a-f]{6}$")
        self.assertNotEqual(
            team["color"], "#a2a2a2", "the grey 'no colour' must not be a route colour"
        )

    def test_payload_carries_the_map_configuration_and_kpis(self):
        payload = self._board()
        self.assertIn("tile_url", payload["map"])
        self.assertTrue(payload["map"]["tile_url"])
        self.assertIn("unassigned", payload)
        self.assertIn("teams", payload)
        self.assertIn("generated_at", payload)

    def test_live_position_is_reported_when_present(self):
        self.team.write(
            {
                "latitude": HOME[0],
                "longitude": HOME[1],
                "last_update": fields.Datetime.now() - timedelta(minutes=2),
                "battery_level": 72,
            }
        )
        team = self._team_payload()
        self.assertTrue(team["live"])
        self.assertGreaterEqual(team["live"]["minutes_ago"], 2)
        self.assertEqual(team["live"]["battery"], 72)

        positions = self.env["field.operation.team"]._live_positions(
            team_ids=[self.team.id]
        )
        self.assertIn(self.team.id, positions["teams"])

    def test_live_positions_skip_a_team_never_seen(self):
        self.team.write({"latitude": 0.0, "longitude": 0.0, "last_update": False})
        positions = self.env["field.operation.team"]._live_positions(
            team_ids=[self.team.id]
        )
        self.assertNotIn(self.team.id, positions["teams"])

    # ------------------------------------------------------------------
    # The board and the plan wizard must agree
    # ------------------------------------------------------------------
    def test_the_board_shows_the_same_day_and_order_as_the_plan_wizard(self):
        self.late.route_sequence = 10
        self.early.route_sequence = 20
        plan = self.env["field.operation.route.plan"].create(
            {"team_id": self.team.id, "date": self.day}
        )
        board_ids = [stop["operation_id"] for stop in self._team_payload()["stops"]]
        self.assertEqual(
            plan._ordered_lines().mapped("operation_id").ids,
            board_ids,
            "the board and the plan wizard disagreed about the day/order",
        )

    # ------------------------------------------------------------------
    # Scoping, filtering and edge cases
    # ------------------------------------------------------------------
    def test_team_ids_restrict_the_payload(self):
        other_team = self.env["field.operation.team"].create({"name": "Other Board Team"})
        self.env["field.operation"].create(
            {
                "subject": "Other Team Stop",
                "partner_id": self.located_partner.id,
                "team_id": other_team.id,
                "start_date": fields.Datetime.to_datetime(
                    datetime.combine(self.day, time(10))
                ),
            }
        )
        payload = self.env["field.operation.team"]._day_board_data(
            self.day, team_ids=[self.team.id]
        )
        self.assertEqual(
            [team["id"] for team in payload["teams"]],
            [self.team.id],
            "team_ids must restrict the payload",
        )

    def test_an_empty_team_ids_list_returns_no_team(self):
        payload = self.env["field.operation.team"]._day_board_data(
            self.day, team_ids=[]
        )
        self.assertEqual(payload["teams"], [])

    def test_done_and_cancelled_jobs_are_not_stops(self):
        done = self._create_operation("Done Stop", self.located_partner, 13)
        done.status = "done"
        cancelled = self._create_operation("Cancelled Stop", self.located_partner, 14)
        cancelled.status = "cancel"
        stop_ids = [stop["operation_id"] for stop in self._team_payload()["stops"]]
        self.assertNotIn(done.id, stop_ids)
        self.assertNotIn(cancelled.id, stop_ids)

    def test_an_empty_day_returns_the_team_without_stops(self):
        future = self.day + timedelta(days=30)
        payload = self.env["field.operation.team"]._day_board_data(
            future, team_ids=[self.team.id]
        )
        team = next(item for item in payload["teams"] if item["id"] == self.team.id)
        self.assertEqual(team["stops_total"], 0)
        self.assertFalse(team["start_fallback"], "the start point is still located")

    def test_start_fallback_is_reported_when_no_start_point_is_located(self):
        self.company_partner.write(
            {"partner_latitude": 0.0, "partner_longitude": 0.0}
        )
        team = self._team_payload()
        self.assertTrue(
            team["start_fallback"],
            "a route without a start point must be flagged to the dispatcher",
        )
        self.assertEqual(
            list(team["geometry"][0]),
            [PENDIK[0], PENDIK[1]],
            "without a start point the route begins at the first located stop",
        )

    def test_auto_colours_stay_unique_for_many_teams(self):
        used_colors = set()
        colors = []
        for index in range(8):
            team = self.env["field.operation.team"].create(
                {"name": f"Board Colour {index}"}
            )
            _index, color = team._board_color(team, used_colors)
            colors.append(color)
        self.assertEqual(len(colors), len(set(colors)))

    def test_the_legacy_day_order_matches_the_shared_helper(self):
        """Older geolocation (19.0.1.6.x) has no shared helper; the fallback must agree."""
        if not hasattr(
            type(self.env["field.operation"]), "_day_operations_for_team"
        ):
            self.skipTest(
                "field_operation_geolocation < 19.0.1.8.0 has no shared helper"
            )
        self.late.route_sequence = 10
        self.early.route_sequence = 20
        shared = self.env["field.operation"]._day_operations_for_team(
            self.team, self.day
        )
        legacy = self.env["field.operation.team"]._board_legacy_day_operations(
            self.team, self.day
        )
        self.assertEqual(shared.ids, legacy.ids)

    def test_the_board_still_works_without_the_shared_helper(self):
        self.late.route_sequence = 10
        self.early.route_sequence = 20
        with patch.object(
            type(self.env["field.operation"]),
            "_day_operations_for_team",
            None,
            create=True,
        ):
            team = self._team_payload()
        self.assertEqual(
            [stop["operation_id"] for stop in team["stops"]],
            [self.late.id, self.early.id],
            "the board must keep the route order on the older geolocation",
        )

    def test_the_board_is_scoped_to_the_users_companies(self):
        other_company = self.env["res.company"].create({"name": "Board Other Company"})
        other_team = self.env["field.operation.team"].create(
            {"name": "Board Other Team", "company_id": other_company.id}
        )
        user = self.env["res.users"].create(
            {
                "name": "Board Scoped User",
                "login": "board_scoped_user",
                "email": "board_scoped_user@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, [self.env.company.id])],
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref(
                                "field_operation.service_group_all"
                            ).id,
                        ],
                    )
                ],
            }
        )
        payload = (
            self.env["field.operation.team"]
            .with_user(user)
            ._day_board_data(self.day)
        )
        self.assertNotIn(
            other_team.id,
            [team["id"] for team in payload["teams"]],
            "the board must not leak another company's teams",
        )

    # ------------------------------------------------------------------
    # Access and validation
    # ------------------------------------------------------------------
    def test_a_field_worker_without_the_board_group_is_refused(self):
        user = self.env["res.users"].create(
            {
                "name": "Board Outsider",
                "login": "board_outsider",
                "email": "board_outsider@example.com",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            self.env["field.operation.team"].with_user(user)._day_board_data(self.day)

    def test_an_invalid_day_is_rejected(self):
        with self.assertRaises(UserError):
            self.env["field.operation.team"]._day_board_data("not-a-date")
