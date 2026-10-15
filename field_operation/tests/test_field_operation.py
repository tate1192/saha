"""Regression tests for the field_operation core module.

Each test targets a concrete bug that was found during the v19 review:
* team kanban crashed because ``_read_group`` does not return an implicit
  ``__count`` aggregate anymore (v18/v19) and ``draft`` was missing from the
  status counters;
* the leave/absence conflict check raised a ``TypeError`` instead of a
  ``ValidationError`` (message/arguments mismatch);
* the stored partner service counter was never invalidated when an operation
  was added to a child contact;
* the portal PDF download used a non existing report xml:id;
* the "This Week" / "Last Week" search filters were off by one week;
* ``date_localization`` was overwritten by a compute method;
* the team dashboard issued one query per team per period (N+1);
* the team kanban graph data used the pre-17 ``{'label', 'value'}`` shape,
  which the current ``dashboard_graph`` widget cannot read: it reads
  ``data[0].values`` and threw ``Cannot read properties of undefined`` on every
  team having a service today;
* the recurring service wizard stored naive local dates as UTC, shifting
  planned services by the user UTC offset.
"""

import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from dateutil.relativedelta import relativedelta
from lxml import etree

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged("field_operation", "post_install", "-at_install")
class TestFieldOperation(TransactionCase):
    def test_01_team_kanban_counts_all_statuses(self):
        """Team dashboard must not raise and must count every status, draft too."""
        team = self.env["field.operation.team"].create({"name": "Test Team"})
        self.env["field.operation"].create(
            {
                "subject": "Today Service",
                "start_date": fields.Datetime.now(),
                "team_id": team.id,
                "status": "draft",
            }
        )

        data = team._get_kanban_data()

        self.assertEqual(data["today"]["counts"]["draft"], 1)
        self.assertEqual(data["today"]["total"], 1)
        self.assertTrue(data["has_entries"])

    def test_02_leave_conflict_raises_validation_error(self):
        """A leave conflict raises ValidationError, with one batched leave lookup.

        ``hr.leave.search`` is stubbed on purpose: hr_holidays refuses to create a
        bare leave inside a test transaction (its own date constraints), and the
        contract pinned down here is ours — a *single* lookup whose result is
        intersected with the record dates, whatever the number of services
        written at once (the previous implementation queried once per record).
        """
        employee = self.env["hr.employee"].create({"name": "Leave Test Employee"})
        leave = MagicMock()
        leave.employee_id.name = "Leave Test Employee"
        leave.holiday_status_id.display_name = "Paid Time Off"
        leave.request_date_from = date(2026, 3, 10)
        leave.request_date_to = date(2026, 3, 10)
        # emulate the recordset API the batched code goes through
        leave.filtered.return_value = leave
        leave.__getitem__.return_value = leave

        vals = {
            "person_ids": [(6, 0, employee.ids)],
            "start_date": "2026-03-10 08:00:00",
            "end_date": "2026-03-10 10:00:00",
            "status": "planned",
        }
        with patch.object(
            type(self.env["hr.leave"]), "search", return_value=leave
        ) as leave_search:
            with self.assertRaises(ValidationError) as error:
                self.env["field.operation"].create(
                    [
                        dict(vals, subject="Conflict Service 1"),
                        dict(vals, subject="Conflict Service 2"),
                    ]
                )

        self.assertEqual(
            leave_search.call_count,
            1,
            "the leaves must be looked up once for the whole batch",
        )
        message = str(error.exception)
        self.assertIn("Leave Test Employee", message)
        self.assertIn("Paid Time Off", message)

    def test_03_partner_count_follows_child_contacts(self):
        """The parent company's stored counter must follow child contacts."""
        company = self.env["res.partner"].create(
            {
                "name": "Counter Test Company",
                "is_company": True,
            }
        )
        contact = self.env["res.partner"].create(
            {
                "name": "Counter Test Contact",
                "parent_id": company.id,
            }
        )

        operation = self.env["field.operation"].create(
            {
                "subject": "Child Service",
                "partner_id": contact.id,
            }
        )

        self.assertEqual(contact.field_operation_count, 1)
        self.assertEqual(company.field_operation_count, 1)

        operation.unlink()
        self.assertEqual(company.field_operation_count, 0)

    def test_04_partner_action_domain_matches_counter(self):
        """The smart button list and the counter must use the same domain."""
        company = self.env["res.partner"].create(
            {
                "name": "Domain Test Company",
                "is_company": True,
            }
        )
        action = company.action_view_field_operation()
        self.assertEqual(action["domain"], [("partner_id", "child_of", company.id)])

    def test_05_portal_pdf_report_exists(self):
        """The report xml:id used by the portal download route must exist."""
        report = self.env.ref("field_operation.field_operation_action_pdf")
        self.assertEqual(report.model, "field.operation")
        self.assertFalse(
            self.env.ref(
                "field_operation.action_report_field_operation",
                raise_if_not_found=False,
            )
        )

    def test_06_week_filters_cover_the_current_week(self):
        """'This Week'/'Last Week' filters must use the real Monday of the week."""
        arch = etree.fromstring(
            self.env.ref("field_operation.view_field_operation_filter").arch
        )
        domains = {
            node.get("name"): node.get("domain")
            for node in arch.iter("filter")
            if node.get("name") in ("this_week", "last_week")
        }
        self.assertIn("this_week", domains)
        self.assertIn("last_week", domains)

        cases = [
            (date(2026, 9, 21), date(2026, 9, 21)),  # Monday
            (date(2026, 9, 23), date(2026, 9, 21)),  # Wednesday
            (date(2026, 9, 20), date(2026, 9, 14)),  # Sunday
        ]
        for today, expected_start in cases:
            context = {
                "context_today": lambda today=today: today,
                "relativedelta": relativedelta,
            }
            this_week = safe_eval(domains["this_week"], context)
            last_week = safe_eval(domains["last_week"], context)
            self.assertEqual(
                this_week[0][2], expected_start, f"this_week start for {today}"
            )
            self.assertEqual(
                this_week[1][2],
                expected_start + timedelta(days=7),
                f"this_week end for {today}",
            )
            self.assertEqual(
                last_week[0][2],
                expected_start - timedelta(days=7),
                f"last_week start for {today}",
            )
            self.assertEqual(
                last_week[1][2], expected_start, f"last_week end for {today}"
            )

    def test_07_date_localization_is_not_computed(self):
        """``date_localization`` must only be set by the geolocation flows."""
        company = self.env["res.partner"].create(
            {
                "name": "Geo Test Company",
                "is_company": True,
                "partner_latitude": 41.0,
                "partner_longitude": 29.0,
            }
        )
        operation = self.env["field.operation"].create(
            {
                "subject": "Geo Service",
                "partner_id": company.id,
            }
        )
        fixed_date = fields.Datetime.now() - timedelta(days=1)
        operation.write({"date_localization": fixed_date})

        company.write({"partner_latitude": 42.0})

        self.assertEqual(operation.date_localization, fixed_date)

    def test_08_team_service_count(self):
        """The service counter of a team must follow its operations."""
        team = self.env["field.operation.team"].create({"name": "Counter Team"})
        self.assertEqual(team.service_count, 0)
        self.env["field.operation"].create(
            {
                "subject": "Team Service",
                "team_id": team.id,
            }
        )
        self.assertEqual(team.service_count, 1)

    def test_09_team_kanban_data_is_batched(self):
        """Batch kanban data must serve several teams with correct counters."""
        team_a = self.env["field.operation.team"].create({"name": "Batch A"})
        team_b = self.env["field.operation.team"].create({"name": "Batch B"})
        self.env["field.operation"].create(
            {
                "subject": "Planned Today",
                "team_id": team_a.id,
                "start_date": fields.Datetime.now(),
                "status": "planned",
            }
        )

        data = (team_a + team_b)._get_kanban_data_batch()

        self.assertEqual(data[team_a.id]["today"]["counts"]["planned"], 1)
        self.assertEqual(data[team_a.id]["today"]["total"], 1)
        self.assertTrue(data[team_a.id]["has_entries"])
        self.assertEqual(data[team_b.id]["today"]["total"], 0)
        self.assertFalse(data[team_b.id]["has_entries"])
        # Per-team public API and computes stay consistent with the batch
        self.assertEqual(team_a._get_kanban_data()["today"]["total"], 1)
        self.assertEqual(team_a.service_count, 1)
        self.assertEqual(team_b.service_count, 0)

        # The graph must be the shape the dashboard_graph widget reads
        # (`data[0].values`). The old `[{'label': 'Week 1', 'value': 3}]` list
        # made the kanban throw "Cannot read properties of undefined (reading
        # 'map')" on every team having a service today.
        graph = (team_a + team_b)._get_graph_data_batch()
        series = graph[team_a.id]
        self.assertEqual(len(series), 1, "one series, not a bare list of points")
        self.assertEqual(set(series[0]), {"key", "values", "is_sample_data"})
        self.assertEqual(len(series[0]["values"]), 4)
        for point in series[0]["values"]:
            self.assertTrue(set(point) >= {"x", "y"}, point)
            self.assertIsInstance(point["y"], int)
        # The service created above is today's, so it lands in the last bucket.
        self.assertEqual(series[0]["values"][-1]["y"], 1)
        self.assertFalse(series[0]["is_sample_data"])
        # A team with nothing to show still gets four zeroed points: the widget
        # reads values[0] whatever the data is.
        self.assertEqual(
            [point["y"] for point in graph[team_b.id][0]["values"]], [0, 0, 0, 0]
        )
        # And the value the kanban really receives parses back into that series.
        self.assertEqual(
            json.loads(team_a.kanban_graph)[0]["values"], series[0]["values"]
        )

    def test_10_recurring_wizard_stores_utc(self):
        """Generated start dates must be stored in UTC for the user timezone."""
        partner = self.env["res.partner"].create({"name": "Repeat Customer"})
        wizard = (
            self.env["service.repeat.wizard"]
            .with_context(tz="Europe/Istanbul")
            .create(
                {
                    "partner_id": partner.id,
                    "subject": "Recurring UTC",
                    "dtstart": date(2026, 3, 10),
                    "rrule_freq": "daily",
                    "rrule_interval": 1,
                    "rrule_end_type": "count",
                    "rrule_count": 2,
                }
            )
        )

        action = wizard.action_generate_operations()
        created = (
            self.env["field.operation"]
            .browse(action["domain"][0][2])
            .sorted("start_date")
        )

        self.assertEqual(len(created), 2)
        # 10.03 / 11.03 00:00 Istanbul (+03:00) == previous day 21:00 UTC
        self.assertEqual(
            fields.Datetime.to_string(created[0].start_date), "2026-03-09 21:00:00"
        )
        self.assertEqual(
            fields.Datetime.to_string(created[1].start_date), "2026-03-10 21:00:00"
        )

    def test_11_partner_statistics_expose_service_counter(self):
        """The "Stats" cell of a contact must expose the service counter badge."""
        company = self.env["res.partner"].create(
            {"name": "Stats Company", "is_company": True}
        )
        contact = self.env["res.partner"].create(
            {
                "name": "Stats Contact",
                "parent_id": company.id,
            }
        )
        # No service yet -> hook must not add any entry to the JSON cell.
        # An empty fields.Json value reads back as False, not []:
        # Json.convert_to_cache turns a falsy value into None and
        # convert_to_record maps None to False (odoo/orm/fields_misc.py:67-74).
        self.assertFalse(company.application_statistics)

        self.env["field.operation"].create(
            {
                "subject": "Stats Service",
                "partner_id": contact.id,
            }
        )
        company.invalidate_recordset()

        stats = company.application_statistics
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["iconClass"], "fa-tasks")
        self.assertEqual(stats[0]["label"], self.env._("Services"))
        # Counter is recursive (child contacts included), badge must match it
        self.assertEqual(stats[0]["value"], company.field_operation_count)

    def test_12_contact_mobile_reads_through_without_writing_back(self):
        """The contact phone stays the master record: the job copy only follows it.

        ``contact_mobile`` was a writable related field: editing the phone on a
        job silently rewrote ``res.partner.phone`` for every document of that
        contact (measured: 222 -> 999), including through list ``multi_edit``.
        It is readonly now — a revert to ``readonly=False`` must fail this test.
        """
        partner = self.env["res.partner"].create(
            {"name": "Phone Owner", "phone": "111222333"}
        )
        contact = self.env["res.partner"].create(
            {"name": "Phone Contact", "parent_id": partner.id, "phone": "999888777"}
        )
        operation = self.env["field.operation"].create(
            {"subject": "Phone Job", "partner_id": partner.id, "contact_id": contact.id}
        )
        self.assertEqual(operation.contact_mobile, "999888777")
        self.assertTrue(
            self.env["field.operation"]._fields["contact_mobile"].readonly,
            "a writable related field would overwrite res.partner.phone",
        )

        operation.write({"contact_mobile": "000000000"})
        self.assertEqual(
            contact.phone,
            "999888777",
            "the write must not travel back to the contact's phone",
        )

        contact.phone = "444555666"
        operation.invalidate_recordset(["contact_mobile"])
        self.assertEqual(operation.contact_mobile, "444555666")
