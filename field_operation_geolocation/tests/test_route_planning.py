"""Dispatcher-side route planning: day filter, driving order and map links.

The need behind these tests: the office that creates the services must see the
day's stops on the customer locations, in a sensible order, and must be told
when the planned start times drive the crew across the city and back.
"""

from datetime import datetime, time, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.field_operation_geolocation.models import geo_helpers

# District centres used throughout: Tuzla (east), Beykoz (north), Pendik
# (south-east). In start-time order they zig-zag, which is the case the
# dispatcher has to see and fix.
TUZLA = (40.817, 29.300)
BEYKOZ = (41.130, 29.090)
PENDIK = (40.877, 29.232)
DEPOT = (41.000, 29.000)
HOME = (40.990, 29.020)


def route_points(url):
    """The ``point=lat,lon`` pairs of a GraphHopper URL, in order."""
    points = []
    for chunk in url.split("point=")[1:]:
        coordinates = chunk.split("&")[0]
        points.append(tuple(float(value) for value in coordinates.split(",")))
    return points


@tagged("post_install", "-at_install")
class TestGeoHelpers(TransactionCase):
    def test_haversine_matches_known_distances(self):
        self.assertAlmostEqual(geo_helpers.haversine_km(TUZLA, PENDIK), 8.8, delta=0.5)
        self.assertAlmostEqual(geo_helpers.haversine_km(TUZLA, BEYKOZ), 39.0, delta=1.0)
        self.assertEqual(geo_helpers.haversine_km(None, TUZLA), 0.0)

    def test_suggestion_removes_the_zigzag(self):
        points = [TUZLA, BEYKOZ, PENDIK]
        current = geo_helpers.path_length_km(points, start=DEPOT)
        order = geo_helpers.suggest_route_order(points, start=DEPOT)
        suggested = geo_helpers.path_length_km(points, order, start=DEPOT)
        self.assertLess(suggested, current - 20.0)
        self.assertGreater(suggested, 0.0)
        self.assertTrue(geo_helpers.distance_gain_is_significant(current, suggested))

    def test_suggestion_keeps_the_first_stop_without_a_depot(self):
        points = [TUZLA, BEYKOZ, PENDIK]
        order = geo_helpers.suggest_route_order(points)
        self.assertEqual(order[0], 0, "the first appointment must stay first")
        self.assertEqual(sorted(order), [0, 1, 2])

    def test_suggestion_puts_unlocated_stops_last(self):
        points = [TUZLA, None, PENDIK]
        order = geo_helpers.suggest_route_order(points, start=DEPOT)
        self.assertEqual(order[-1], 1)
        self.assertEqual(
            geo_helpers.path_length_km(points, order, start=DEPOT),
            geo_helpers.path_length_km([TUZLA, PENDIK], start=DEPOT),
        )

    def test_a_closed_route_adds_the_return_leg(self):
        points = [TUZLA, PENDIK]
        expected = (
            geo_helpers.haversine_km(DEPOT, TUZLA)
            + geo_helpers.haversine_km(TUZLA, PENDIK)
            + geo_helpers.haversine_km(PENDIK, DEPOT)
        )
        self.assertAlmostEqual(
            geo_helpers.path_length_km(points, start=DEPOT, end=DEPOT),
            expected,
            delta=0.1,
        )

    def test_the_suggestion_accounts_for_the_return_leg(self):
        home = (0.0, 0.0)
        points = [(1.0, 0.0), (1.0, 1.0), (10.0, 0.0)]
        one_way = geo_helpers.path_length_km(points, [0, 1, 2], start=home)
        order = geo_helpers.suggest_route_order(points, start=home, end=home)
        self.assertEqual(order, [0, 2, 1])
        self.assertLess(
            geo_helpers.path_length_km(points, order, start=home, end=home),
            one_way + geo_helpers.haversine_km(points[2], home) - 0.5,
            "the suggestion left the stop next to home as the last one",
        )


@tagged("post_install", "-at_install")
class TestDayPlan(TransactionCase):
    """The day a job belongs to, and the coordinates the route is built from."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Day Plan Customer",
                "partner_latitude": TUZLA[0],
                "partner_longitude": TUZLA[1],
            }
        )
        cls.operation = cls.env["field.operation"].create(
            {
                "subject": "Day Plan Job",
                "partner_id": cls.partner.id,
                "start_date": fields.Datetime.to_datetime(
                    datetime.combine(fields.Date.context_today(cls.env.user), time(9))
                ),
            }
        )

    def _plan_domain(self, day):
        return self.env["field.operation"]._plan_day_domain(day)

    def test_is_located_is_stored_and_follows_the_address(self):
        self.assertTrue(self.operation.is_located)
        self.assertTrue(
            self.env["field.operation"]._fields["is_located"].store,
            "is_located must be stored so the dispatcher can filter on it",
        )
        self.partner.write({"partner_latitude": 0.0, "partner_longitude": 0.0})
        self.assertFalse(self.operation.is_located)

    def test_a_job_running_today_belongs_to_today(self):
        today = fields.Date.context_today(self.env.user)
        started_yesterday = self.operation.copy(
            {
                "start_date": fields.Datetime.to_datetime(
                    datetime.combine(today - timedelta(days=1), time(9))
                ),
                "end_date": fields.Datetime.to_datetime(
                    datetime.combine(today, time(17))
                ),
            }
        )
        open_ended_yesterday = self.operation.copy(
            {
                "start_date": fields.Datetime.to_datetime(
                    datetime.combine(today - timedelta(days=1), time(9))
                ),
                "end_date": False,
            }
        )
        open_ended_long_ago = self.operation.copy(
            {
                "start_date": fields.Datetime.to_datetime(
                    datetime.combine(today - timedelta(days=30), time(9))
                ),
                "end_date": False,
            }
        )
        tomorrow = self.operation.copy(
            {
                "start_date": fields.Datetime.to_datetime(
                    datetime.combine(today + timedelta(days=1), time(9))
                ),
                "end_date": False,
            }
        )
        today_operations = self.env["field.operation"].search(self._plan_domain(today))
        self.assertIn(self.operation, today_operations)
        self.assertIn(started_yesterday, today_operations)
        self.assertIn(
            open_ended_yesterday,
            today_operations,
            "a job started yesterday and never closed is still running today",
        )
        self.assertNotIn(
            open_ended_long_ago,
            today_operations,
            "months-old open jobs must not flood every day's plan",
        )
        self.assertNotIn(tomorrow, today_operations)

    def test_the_day_boundary_uses_the_user_timezone(self):
        """A job at 01:30 local is today for an Istanbul user, not yesterday."""
        self.env.user.tz = "Europe/Istanbul"
        today = fields.Date.context_today(self.env.user)
        early = self.operation.copy(
            {
                "start_date": fields.Datetime.to_datetime(
                    datetime.combine(today, time(1, 30))
                )
                - timedelta(hours=3),
                "end_date": False,
            }
        )
        self.assertIn(
            early,
            self.env["field.operation"].search(self._plan_domain(today)),
            "a job just after local midnight fell out of its own day",
        )


@tagged("post_install", "-at_install")
class TestRoutePlanGeolocation(TransactionCase):
    """The plan must offer a way out when the day's stops have no coordinates."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.lang = "en_US"
        cls.provider = cls.env["maps.website"].search([], limit=1)
        if not cls.provider:
            cls.provider = cls.env["maps.website"].create(
                {
                    "name": "Test Map",
                    "lat_lon_url": "https://example.com/?lat={LATITUDE}&lon={LONGITUDE}",
                    "route_lat_lon_url": "https://example.com/route?from={START_LATITUDE},"
                    "{START_LONGITUDE}&to={DEST_LATITUDE},{DEST_LONGITUDE}",
                }
            )
        cls.env.user.route_map_website_id = cls.provider
        cls.team = cls.env["field.operation.team"].create({"name": "Geo Plan Team"})
        # Keep the company address out of the leg expectations below.
        cls.env.company.partner_id.write(
            {"partner_latitude": 0.0, "partner_longitude": 0.0}
        )
        cls.day = fields.Date.context_today(cls.env.user)
        located_partner = cls.env["res.partner"].create(
            {
                "name": "Located Customer",
                "partner_latitude": TUZLA[0],
                "partner_longitude": TUZLA[1],
            }
        )
        unlocated_partner = cls.env["res.partner"].create(
            {"name": "Unlocated Customer", "street": "Some Street", "city": "Istanbul"}
        )
        cls.located = cls.env["field.operation"].create(
            {
                "subject": "Located Job",
                "partner_id": located_partner.id,
                "team_id": cls.team.id,
                "start_date": fields.Datetime.to_datetime(
                    datetime.combine(cls.day, time(10))
                ),
            }
        )
        cls.unlocated = cls.env["field.operation"].create(
            {
                "subject": "Unlocated Job",
                "partner_id": unlocated_partner.id,
                "team_id": cls.team.id,
                "start_date": fields.Datetime.to_datetime(
                    datetime.combine(cls.day, time(12))
                ),
            }
        )

    def _plan(self):
        return self.env["field.operation.route.plan"].create(
            {"team_id": self.team.id, "date": self.day}
        )

    def test_open_map_names_the_stops_without_coordinates(self):
        with self.assertRaisesRegex(UserError, "Without coordinates"):
            self._plan().action_open_map()

    def test_geolocating_the_day_fills_the_missing_coordinates(self):
        plan = self._plan()
        with patch.object(
            type(self.env["res.partner"]), "_geo_localize", return_value=(41.0, 29.0)
        ):
            plan.with_context(force_geo_localize=True).action_geolocate_stops()
        self.assertTrue(
            self.unlocated.is_located,
            "the stop without coordinates was not geocoded",
        )
        # With two located stops the dialog can build the route now.
        action = plan.action_open_map()
        self.assertEqual(action["type"], "ir.actions.act_url")

    def test_a_leg_is_measured_from_the_previous_stop(self):
        """The leg belongs to the line and is computed from the stop before it."""
        team = self.env["field.operation.team"].create({"name": "Leg Team"})
        tuzla_partner = self.env["res.partner"].create(
            {
                "name": "Tuzla Leg",
                "partner_latitude": TUZLA[0],
                "partner_longitude": TUZLA[1],
            }
        )
        pendik_partner = self.env["res.partner"].create(
            {
                "name": "Pendik Leg",
                "partner_latitude": PENDIK[0],
                "partner_longitude": PENDIK[1],
            }
        )
        for hour, partner in ((10, tuzla_partner), (12, pendik_partner)):
            self.env["field.operation"].create(
                {
                    "subject": f"Leg {hour}",
                    "partner_id": partner.id,
                    "team_id": team.id,
                    "start_date": fields.Datetime.to_datetime(
                        datetime.combine(self.day, time(hour))
                    ),
                }
            )
        plan = self.env["field.operation.route.plan"].create(
            {"team_id": team.id, "date": self.day}
        )
        lines = plan._ordered_lines()
        self.assertEqual(lines[0].leg_km, 0.0, "the first stop has no leg yet")
        self.assertAlmostEqual(
            lines[1].leg_km,
            geo_helpers.haversine_km(TUZLA, PENDIK),
            delta=0.2,
            msg="the leg is not measured from the previous stop",
        )

    def test_shifting_times_leaves_a_job_from_another_day_alone(self):
        """A job running over from yesterday keeps its start when times shift."""
        day = self.day
        team = self.env["field.operation.team"].create(
            {
                "name": "Shift Team",
                "base_location_id": self.env["res.partner"]
                .create(
                    {
                        "name": "Shift Depot",
                        "is_company": True,
                        "partner_latitude": DEPOT[0],
                        "partner_longitude": DEPOT[1],
                    }
                )
                .id,
            }
        )
        yesterday_job = self.env["field.operation"].create(
            {
                "subject": "Running Since Yesterday",
                "partner_id": self.env["res.partner"]
                .create(
                    {
                        "name": "Far Stop",
                        "partner_latitude": PENDIK[0],
                        "partner_longitude": PENDIK[1],
                    }
                )
                .id,
                "team_id": team.id,
                "start_date": fields.Datetime.to_datetime(
                    datetime.combine(day - timedelta(days=1), time(9))
                ),
                "end_date": False,
            }
        )
        near_partner = self.env["res.partner"].create(
            {
                "name": "Near Stop",
                "partner_latitude": DEPOT[0],
                "partner_longitude": DEPOT[1],
            }
        )
        today_jobs = self.env["field.operation"]
        for hour in (10, 12):
            today_jobs |= self.env["field.operation"].create(
                {
                    "subject": f"Today {hour}",
                    "partner_id": near_partner.id,
                    "team_id": team.id,
                    "start_date": fields.Datetime.to_datetime(
                        datetime.combine(day, time(hour))
                    ),
                }
            )
        plan = self.env["field.operation.route.plan"].create(
            {"team_id": team.id, "date": day}
        )
        plan.action_suggest_order()
        plan.shift_times = True
        plan.action_save_order()

        self.assertEqual(
            yesterday_job.start_date,
            fields.Datetime.to_datetime(
                datetime.combine(day - timedelta(days=1), time(9))
            ),
            "the shift moved a job across days",
        )
        self.assertEqual(
            sorted(today_jobs.mapped("start_date")),
            sorted(
                fields.Datetime.to_datetime(datetime.combine(day, time(hour)))
                for hour in (10, 12)
            ),
        )

    def test_nothing_to_do_when_every_stop_is_located(self):
        plan = self.env["field.operation.route.plan"].new(
            {"team_id": self.team.id, "date": self.day}
        )
        plan._load_stops()
        plan.line_ids.filtered(lambda line: not line.is_located).unlink()
        result = plan.action_geolocate_stops()
        self.assertEqual(result["res_model"], "field.operation.route.plan")


@tagged("post_install", "-at_install")
class TestSelectedRouteAction(TransactionCase):
    """The list action: start-time order, depot start and skipped stops."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["maps.website"].create(
            {
                "name": "OSM Test",
                "provider_type": "openstreetmap",
                "lat_lon_url": "https://www.openstreetmap.org/?mlat={LATITUDE}&mlon={LONGITUDE}",
                "route_lat_lon_url": "https://example.com/route?from={START_LATITUDE},"
                "{START_LONGITUDE}&to={DEST_LATITUDE},{DEST_LONGITUDE}",
            }
        )
        cls.env.user.route_map_website_id = cls.provider
        cls.env.user.map_website_id = cls.provider
        # These expectations start at the depot below; keep the company
        # fallback out of them.
        cls.env.company.partner_id.write(
            {"partner_latitude": 0.0, "partner_longitude": 0.0}
        )
        cls.day = fields.Date.context_today(cls.env.user)
        cls.depot = cls.env["res.partner"].create(
            {
                "name": "Depot",
                "is_company": True,
                "partner_latitude": DEPOT[0],
                "partner_longitude": DEPOT[1],
            }
        )
        cls.team = cls.env["field.operation.team"].create(
            {"name": "Selected Team", "base_location_id": cls.depot.id}
        )

    def _operation(self, name, point, hour):
        vals = {
            "subject": name,
            "team_id": self.team.id,
            "start_date": fields.Datetime.to_datetime(
                datetime.combine(self.day, time(hour))
            ),
        }
        if point:
            vals["partner_id"] = (
                self.env["res.partner"]
                .create(
                    {
                        "name": name,
                        "partner_latitude": point[0],
                        "partner_longitude": point[1],
                    }
                )
                .id
            )
        else:
            vals["partner_id"] = (
                self.env["res.partner"].create({"name": name, "city": "Nowhere"}).id
            )
        return self.env["field.operation"].create(vals)

    def _points(self, url):
        return route_points(url)

    def test_the_route_follows_the_planned_start_time(self):
        tuzla = self._operation("Tuzla", TUZLA, 12)
        beykoz = self._operation("Beykoz", BEYKOZ, 14)
        pendik = self._operation("Pendik", PENDIK, 16)
        # The list hands the records over in the wrong order on purpose.
        action = (pendik | tuzla | beykoz).action_show_selected_routes()
        points = self._points(action["url"])
        self.assertEqual(points[0], DEPOT, "the route must start at the depot")
        self.assertEqual(points[1:-1], [TUZLA, BEYKOZ, PENDIK])
        self.assertEqual(points[-1], DEPOT, "the route must return to the depot")

    def test_a_manual_route_order_wins_over_the_start_time(self):
        tuzla = self._operation("Tuzla", TUZLA, 12)
        beykoz = self._operation("Beykoz", BEYKOZ, 14)
        self.team.base_location_id = False
        beykoz.route_sequence = 10
        tuzla.route_sequence = 20
        action = (tuzla | beykoz).action_show_selected_routes()
        self.assertEqual(self._points(action["url"]), [BEYKOZ, TUZLA])

    def test_an_unlocated_stop_is_left_out_with_a_warning(self):
        tuzla = self._operation("Tuzla", TUZLA, 12)
        beykoz = self._operation("Beykoz", BEYKOZ, 14)
        nowhere = self._operation("Nowhere", None, 16)
        selection = tuzla | beykoz | nowhere
        with patch.object(
            type(self.env["field.operation"]), "_notify_missing_stops", autospec=True
        ) as notify:
            action = selection.action_show_selected_routes()
        self.assertTrue(notify.called, "the skipped stop was not reported")
        self.assertEqual(notify.call_args[0][0], nowhere)
        self.assertEqual(self._points(action["url"]), [DEPOT, TUZLA, BEYKOZ, DEPOT])

    def test_an_unsequenced_job_lands_after_the_saved_order(self):
        tuzla = self._operation("Tuzla", TUZLA, 12)
        beykoz = self._operation("Beykoz", BEYKOZ, 14)
        beykoz.route_sequence = 10
        tuzla.route_sequence = 20
        urgent = self._operation("Urgent", (41.0, 29.05), 8)
        self.assertEqual(
            (tuzla | beykoz | urgent)._sorted_for_route().ids,
            [beykoz.id, tuzla.id, urgent.id],
            "the saved order was reset by an unsequenced stop",
        )

    def test_one_located_stop_is_not_a_route(self):
        tuzla = self._operation("Tuzla", TUZLA, 12)
        nowhere = self._operation("Nowhere", None, 16)
        with self.assertRaises(UserError):
            (tuzla | nowhere).action_show_selected_routes()


@tagged("post_install", "-at_install")
class TestRouteStart(TransactionCase):
    """The route starts and ends at home or at the company, as a loop."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.lang = "en_US"
        cls.provider = cls.env["maps.website"].create(
            {
                "name": "Start Route OSM",
                "provider_type": "openstreetmap",
                "lat_lon_url": "https://example.com/?lat={LATITUDE}&lon={LONGITUDE}",
            }
        )
        cls.env.user.route_map_website_id = cls.provider
        cls.day = fields.Date.context_today(cls.env.user)
        cls.company_partner = cls.env.company.partner_id
        cls.company_partner.write(
            {"partner_latitude": DEPOT[0], "partner_longitude": DEPOT[1]}
        )
        cls.home_partner = cls.env["res.partner"].create(
            {
                "name": "Employee Home",
                "partner_latitude": HOME[0],
                "partner_longitude": HOME[1],
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {"name": "Route Owner", "home_location_id": cls.home_partner.id}
        )
        cls.team = cls.env["field.operation.team"].create(
            {"name": "Home Team", "team_head_id": cls.employee.id}
        )

    def _operation(self, name, point, hour):
        vals = {
            "subject": name,
            "team_id": self.team.id,
            "start_date": fields.Datetime.to_datetime(
                datetime.combine(self.day, time(hour))
            ),
        }
        if point:
            vals["partner_id"] = (
                self.env["res.partner"]
                .create(
                    {
                        "name": name,
                        "partner_latitude": point[0],
                        "partner_longitude": point[1],
                    }
                )
                .id
            )
        else:
            vals["partner_id"] = (
                self.env["res.partner"].create({"name": name, "city": "Nowhere"}).id
            )
        return self.env["field.operation"].create(vals)

    def _plan(self):
        return self.env["field.operation.route.plan"].create(
            {"team_id": self.team.id, "date": self.day}
        )

    def test_the_route_starts_and_ends_at_home(self):
        self._operation("Tuzla", TUZLA, 10)
        self._operation("Beykoz", BEYKOZ, 12)
        plan = self._plan()
        self.assertEqual(plan.start_location_id, self.home_partner)
        expected = (
            geo_helpers.haversine_km(HOME, TUZLA)
            + geo_helpers.haversine_km(TUZLA, BEYKOZ)
            + geo_helpers.haversine_km(BEYKOZ, HOME)
        )
        self.assertAlmostEqual(plan.total_km, expected, delta=0.2)
        self.assertAlmostEqual(
            plan.return_km, geo_helpers.haversine_km(BEYKOZ, HOME), delta=0.2
        )
        action = plan.action_open_map()
        points = route_points(action["url"])
        self.assertEqual(points[0], HOME)
        self.assertEqual(points[-1], HOME)

    def test_a_home_without_coordinates_falls_back_to_the_company(self):
        self.home_partner.write({"partner_latitude": 0.0, "partner_longitude": 0.0})
        self._operation("Tuzla", TUZLA, 10)
        self._operation("Beykoz", BEYKOZ, 12)
        plan = self._plan()
        self.assertEqual(plan.start_location_id, self.company_partner)
        self.assertIn("Home address", plan.info)
        self.assertGreater(plan.return_km, 0.0)

    def test_a_team_without_a_home_starts_at_the_company_silently(self):
        """No home is a normal state, not a configuration error to warn about."""
        self.employee.home_location_id = False
        self._operation("Tuzla", TUZLA, 10)
        self._operation("Beykoz", BEYKOZ, 12)
        plan = self._plan()
        self.assertEqual(plan.start_location_id, self.company_partner)
        self.assertNotIn("Home address", plan.info)

    def test_company_mode_starts_at_the_company(self):
        self.team.route_start_mode = "company"
        self._operation("Tuzla", TUZLA, 10)
        self._operation("Beykoz", BEYKOZ, 12)
        plan = self._plan()
        self.assertEqual(plan.start_location_id, self.company_partner)
        self.assertNotIn("Home address", plan.info)


@tagged("post_install", "-at_install")
class TestRouteProviders(TransactionCase):
    """The provider side of the route URLs."""

    def _provider(self, provider_type, **vals):
        values = {
            "name": provider_type,
            "provider_type": provider_type,
            "lat_lon_url": "https://example.com/?lat={LATITUDE}&lon={LONGITUDE}",
        }
        values.update(vals)
        return self.env["maps.website"].create(values)

    def test_a_configured_route_template_is_used(self):
        provider = self._provider(
            "other",
            route_lat_lon_url="https://example.com/route?from={START_LATITUDE},"
            "{START_LONGITUDE}&to={DEST_LATITUDE},{DEST_LONGITUDE}",
        )
        url = provider._get_route_url(
            {"latitude": 41.0, "longitude": 29.0}, ["40.0,28.0"]
        )
        self.assertIn("from=41.0,29.0", url)
        self.assertIn("to=40.0,28.0", url)

    def test_a_round_trip_keeps_the_last_stop_as_destination(self):
        """A template knows only two points: do not turn the loop into X -> X."""
        provider = self._provider(
            "other",
            route_lat_lon_url="https://example.com/route?from={START_LATITUDE},"
            "{START_LONGITUDE}&to={DEST_LATITUDE},{DEST_LONGITUDE}",
        )
        url = provider._get_route_url_for_points([TUZLA, BEYKOZ, PENDIK, TUZLA])
        self.assertIn("from=40.817,29.3", url)
        self.assertIn("to=40.877,29.232", url)

    def test_mapbox_keeps_every_stop(self):
        provider = self._provider("mapbox")
        url = provider._get_route_url_for_points([TUZLA, BEYKOZ, PENDIK])
        self.assertIn("rtext=40.817,29.3~41.13,29.09~40.877,29.232", url)

    def test_here_falls_back_to_its_template(self):
        provider = self._provider(
            "here",
            route_lat_lon_url="https://www.here.com/directions-app/?destination="
            "{DEST_LATITUDE},{DEST_LONGITUDE}&origin={START_LATITUDE},{START_LONGITUDE}",
        )
        url = provider._get_route_url(
            {"latitude": 41.0, "longitude": 29.0}, ["40.0,28.0"]
        )
        self.assertTrue(url)
        self.assertIn("origin=41.0,29.0", url)

    def test_a_start_on_the_equator_is_a_real_point(self):
        provider = self._provider("openstreetmap")
        url = provider._get_route_url(
            {"latitude": 0.0, "longitude": 29.0}, ["40.0,28.0"]
        )
        self.assertIn("point=0.0,29.0", url)
        self.assertEqual(url.count("point="), 2)
