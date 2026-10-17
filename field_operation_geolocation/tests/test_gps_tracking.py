"""Behavioural tests for the ``field_operation_geolocation`` GPS feature.

They exercise the contract shared by the browser GPS service, the
``/field_team/*`` JSON-RPC controllers and the geolocation ORM models:

* per-team isolation of the position endpoints,
* rejection of writes addressed to another team,
* coordinate input validation,
* read/write access rights on ``maps.website`` (including a masked API key),
* the ``team.location.history`` record rule,
* the daily geolocation cron and the route-history action.
"""

import logging
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tests.common import JsonRpcException

_logger = logging.getLogger(__name__)

ROUTE_USER_GROUP = "field_operation_geolocation.group_user_field_operation_route"
ROUTE_MANAGER_GROUP = "field_operation_geolocation.group_manager_field_operation_route"


@tagged("post_install", "-at_install")
class TestGpsTrackingEndpoints(HttpCase):
    """HTTP contract of the ``/field_team/*`` JSON-RPC endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        Employees = cls.env["hr.employee"]
        Teams = cls.env["field.operation.team"]
        user_group = cls.env.ref(ROUTE_USER_GROUP).id
        base_user_group = cls.env.ref("base.group_user").id

        def _make_user(login, name):
            return Users.create(
                {
                    "name": name,
                    "login": login,
                    "password": login,
                    "group_ids": [(6, 0, [base_user_group, user_group])],
                }
            )

        cls.user_a = _make_user("gps_user_a", "GPS User A")
        cls.user_b = _make_user("gps_user_b", "GPS User B")

        cls.employee_a = Employees.create(
            {
                "name": "GPS Employee A",
                "user_id": cls.user_a.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.employee_b = Employees.create(
            {
                "name": "GPS Employee B",
                "user_id": cls.user_b.id,
                "company_id": cls.env.company.id,
            }
        )

        cls.team_a = Teams.create(
            {
                "name": "GPS Team A",
                "team_members_ids": [(4, cls.employee_a.id)],
                "latitude": 41.0,
                "longitude": 29.0,
            }
        )
        cls.team_b = Teams.create(
            {
                "name": "GPS Team B",
                "team_members_ids": [(4, cls.employee_b.id)],
                "latitude": 39.0,
                "longitude": 32.0,
            }
        )

    def _call(self, route, params):
        """Return ``(result, exception)`` for a jsonrpc call.

        The result is the method payload (which may be ``{"error": ...}``) and
        the exception is a :class:`JsonRpcException` when the server answered
        with a JSON-RPC error (for instance an uncaught ``UserError``).
        """
        try:
            return self.make_jsonrpc_request(route, params), None
        except JsonRpcException as exc:
            return None, exc

    @staticmethod
    def _rejected(result, exc):
        return exc is not None or (isinstance(result, dict) and result.get("error"))

    def test_get_my_team_returns_the_logged_in_users_team(self):
        self.authenticate(self.user_a.login, self.user_a.login)
        result, exc = self._call("/field_team/get_my_team", {})
        self.assertIsNone(exc)
        self.assertEqual(result.get("team_id"), self.team_a.id)

    def test_update_gps_on_another_team_is_rejected(self):
        self.authenticate(self.user_a.login, self.user_a.login)
        params = {
            "team_id": self.team_b.id,
            "latitude": 40.0,
            "longitude": 30.0,
            "accuracy": 5.0,
            "device_id": "test-device",
            "status": "working",
            "signal_strength": "3",
        }
        result, exc = self._call("/field_team/update_gps", params)
        self.assertTrue(
            self._rejected(result, exc),
            "writing to another team's record was accepted",
        )
        self.team_b.invalidate_recordset()
        self.assertFalse(
            self.team_b.latitude == 40.0 and self.team_b.longitude == 30.0,
            "another team's coordinates were overwritten",
        )

    def test_update_gps_own_team_accepted(self):
        self.authenticate(self.user_a.login, self.user_a.login)
        params = {
            "team_id": self.team_a.id,
            "latitude": 41.5,
            "longitude": 29.5,
            "accuracy": 5.0,
            "device_id": "test-device",
            "status": "working",
            "signal_strength": "3",
        }
        result, exc = self._call("/field_team/update_gps", params)
        self.assertIsNone(exc)
        self.assertFalse(result.get("error"))
        self.team_a.invalidate_recordset()
        self.assertEqual(self.team_a.latitude, 41.5)
        self.assertEqual(self.team_a.longitude, 29.5)

    def test_update_gps_invalid_status_is_handled(self):
        """A bogus ``status`` must not take the whole request down.

        The endpoint has to answer with a structured payload; it may either
        reject the request or store the coordinates while ignoring the invalid
        status. Whichever design the implementation chose is logged.
        """
        self.authenticate(self.user_a.login, self.user_a.login)
        params = {
            "team_id": self.team_a.id,
            "latitude": 42.5,
            "longitude": 28.5,
            "accuracy": 5.0,
            "device_id": "test-device",
            "status": "started",  # not part of idle/moving/working/break
            "signal_strength": "3",
        }
        result, exc = self._call("/field_team/update_gps", params)
        self.assertIsNone(
            exc,
            "update_gps raised on an invalid status instead of returning a structured "
            "response",
        )
        self.team_a.invalidate_recordset()
        if result and result.get("error"):
            _logger.info("GPS_INVALID_STATUS_BRANCH=rejected_as_whole")
            self.assertNotEqual(
                self.team_a.latitude,
                42.5,
                "request was rejected but the coordinates were still written",
            )
        else:
            _logger.info("GPS_INVALID_STATUS_BRANCH=sanitized_and_stored")
            self.assertEqual(self.team_a.latitude, 42.5)
            self.assertIn(
                self.team_a.status,
                ("idle", "moving", "working", "break"),
                "an out-of-selection status ended up stored on the team",
            )

    def test_update_gps_rejects_out_of_range_latitude(self):
        self.authenticate(self.user_a.login, self.user_a.login)
        params = {
            "team_id": self.team_a.id,
            "latitude": 91.0,
            "longitude": 29.0,
            "accuracy": 5.0,
            "status": "working",
            "signal_strength": "3",
        }
        result, exc = self._call("/field_team/update_gps", params)
        self.assertTrue(
            self._rejected(result, exc),
            "latitude 91.0 was accepted instead of being rejected",
        )

    def test_update_gps_rejects_out_of_range_longitude(self):
        self.authenticate(self.user_a.login, self.user_a.login)
        params = {
            "team_id": self.team_a.id,
            "latitude": 41.0,
            "longitude": 181.0,
            "accuracy": 5.0,
            "status": "working",
            "signal_strength": "3",
        }
        result, exc = self._call("/field_team/update_gps", params)
        self.assertTrue(
            self._rejected(result, exc),
            "longitude 181.0 was accepted instead of being rejected",
        )

    def test_update_gps_accepts_null_island_coordinates(self):
        """``0.0`` is a legitimate coordinate and must not be rejected."""
        self.authenticate(self.user_a.login, self.user_a.login)
        params = {
            "team_id": self.team_a.id,
            "latitude": 0.0,
            "longitude": 0.0,
            "accuracy": 5.0,
            "status": "working",
            "signal_strength": "3",
        }
        result, exc = self._call("/field_team/update_gps", params)
        self.assertIsNone(exc)
        self.assertFalse(
            self._rejected(result, exc),
            "the legitimate (0.0, 0.0) coordinate was rejected",
        )


@tagged("post_install", "-at_install")
class TestGpsTrackingModels(TransactionCase):
    """Model-level contract: access rights, record rules, cron and routes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.maps_website = cls.env["maps.website"].search([], limit=1)
        if not cls.maps_website:
            cls.maps_website = cls.env["maps.website"].create(
                {
                    "name": "Test Map",
                    "lat_lon_url": "https://example.com/?lat={LATITUDE}&lon={LONGITUDE}",
                }
            )

    def _make_user(self, login, group_xmlid):
        base_user = self.env.ref("base.group_user").id
        route_group = self.env.ref(group_xmlid).id
        return (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": login,
                    "login": login,
                    "password": login,
                    "group_ids": [(6, 0, [base_user, route_group])],
                }
            )
        )

    def test_maps_website_api_key_is_masked(self):
        """``api_key`` must be stored as a password field (masked in the UI)."""
        self.assertTrue(
            self.env["maps.website"]._fields["api_key"].password,
            "maps.website.api_key is not declared with password=True",
        )

    def test_maps_website_office_user_is_read_only(self):
        office_user = self._make_user("gps_office_user", ROUTE_USER_GROUP)
        website = self.maps_website.with_user(office_user)
        # Reading is allowed.
        self.assertTrue(website.search([]))
        with self.assertRaises(AccessError):
            website.write({"name": "Edited By Office User"})

    def test_maps_website_manager_can_write(self):
        manager = self._make_user("gps_manager", ROUTE_MANAGER_GROUP)
        self.maps_website.with_user(manager).write({"name": "Edited By Manager"})
        self.assertEqual(self.maps_website.name, "Edited By Manager")

    def test_location_history_record_rule_scopes_to_own_team(self):
        office_user = self._make_user("gps_history_user", ROUTE_USER_GROUP)
        employee = self.env["hr.employee"].create(
            {
                "name": "History Employee",
                "user_id": office_user.id,
                "company_id": self.env.company.id,
            }
        )
        team_a = self.env["field.operation.team"].create(
            {
                "name": "History Team A",
                "team_members_ids": [(4, employee.id)],
            }
        )
        team_b = self.env["field.operation.team"].create({"name": "History Team B"})
        history_a = self.env["team.location.history"].create(
            {
                "team_id": team_a.id,
                "latitude": 41.0,
                "longitude": 29.0,
            }
        )
        self.env["team.location.history"].create(
            {
                "team_id": team_b.id,
                "latitude": 39.0,
                "longitude": 32.0,
            }
        )

        visible = self.env["team.location.history"].with_user(office_user).search([])
        self.assertIn(history_a, visible)
        self.assertTrue(
            all(rec.team_id == team_a for rec in visible),
            "the user can see another team's location history",
        )

    def test_cron_is_created_inactive_and_targets_res_partner(self):
        cron = self.env.ref("field_operation_geolocation.ir_cron_company_geolocalize")
        self.assertFalse(
            cron.active,
            "the daily geolocation cron is active at install time",
        )
        self.assertEqual(cron.model_id.model, "res.partner")
        self.assertIn("action_cron_update_company_geolocations", cron.code)

    def test_cron_method_runs(self):
        """The cron method exists and returns cleanly when there is no work."""
        Partner = self.env["res.partner"]
        self.assertTrue(hasattr(Partner, "action_cron_update_company_geolocations"))
        with patch.object(type(Partner), "search", return_value=Partner):
            result = Partner.action_cron_update_company_geolocations(limit=50)
        self.assertTrue(result)

    def test_route_history_keeps_the_newest_points(self):
        """With more than 50 points in 24h, the ``order`` must keep the newest."""
        team = self.env["field.operation.team"].create({"name": "Route Team"})
        now = fields.Datetime.now()
        history = self.env["team.location.history"]
        for index in range(60):
            history |= self.env["team.location.history"].create(
                {
                    "team_id": team.id,
                    "latitude": 10.0 + index,  # 10.0 is the newest point
                    "longitude": 20.0,
                    "timestamp": now - timedelta(minutes=index),
                }
            )

        action = team.action_show_route_history()
        url = action["url"]
        self.assertIn(
            "10.0",
            url,
            "the newest point is missing from the route (wrong search order/limit)",
        )
        self.assertNotIn(
            "69.0",
            url,
            "the oldest point was returned instead of the newest 50",
        )

    def test_online_flag_is_computed_fresh_and_starts_false(self):
        """``is_online`` must not be stored, and a fresh team must not be Online.

        Two measured defects pinned here: the field was ``store=True`` (once the
        pings stop, the stored True never refreshes — a silent team kept showing
        as online forever; probed: last_update moved 2h back at the DB level,
        ORM still read True) and ``last_update`` carried
        ``default=fields.Datetime.now`` (a team that never sent a single ping
        showed Online for its first five minutes).
        """
        self.assertFalse(
            self.env["field.operation.team"]._fields["is_online"].store,
            "a stored is_online never refreshes after the pings stop",
        )
        team = self.env["field.operation.team"].create({"name": "Fresh Team"})
        self.assertFalse(team.is_online, "a brand-new team is Online before any ping")
        self.assertFalse(team.last_update, "last_update must start empty")

    def test_online_flag_follows_the_last_ping_window(self):
        team = self.env["field.operation.team"].create({"name": "Ping Team"})
        team.last_update = fields.Datetime.now() - timedelta(minutes=10)
        self.assertFalse(
            team.is_online, "a ping ten minutes old must not read as online"
        )
        team.last_update = fields.Datetime.now() - timedelta(minutes=1)
        self.assertTrue(team.is_online, "a ping one minute old is online")
