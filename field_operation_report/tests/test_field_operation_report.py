"""Regression tests for the reporting layer.

Each test pins a decision the first draft got wrong:
* duration comes from the core ``total_work`` field, not from a second private
  definition that fills ``close_date`` and clamps negatives (two answers to the
  same question);
* the calendar day of ``report_date`` is cut in the company timezone, not in
  UTC, so a 01:00 Istanbul service is not reported on the previous day;
* the analysis screens are the core pivot/graph extended, not a second pair of
  views with the same title;
* the team report renders with real data.
"""

from datetime import date

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("field_operation_report", "post_install", "-at_install")
class TestFieldOperationReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.team = cls.env["field.operation.team"].create({"name": "Report Team"})
        cls.service_type = cls.env["field.operation.type"].create({"name": "Report Type"})
        cls.employee_a = cls.env["hr.employee"].create({"name": "Report Employee A"})
        cls.employee_b = cls.env["hr.employee"].create({"name": "Report Employee B"})

    def _operation(self, **vals):
        values = {"subject": "Report Service", "team_id": self.team.id}
        values.update(vals)
        return self.env["field.operation"].create(values)

    def _wizard(self, date_from, date_to):
        return self.env["field.operation.report.wizard"].create(
            {
                "date_from": date_from,
                "date_to": date_to,
                "team_ids": [(6, 0, [self.team.id])],
            }
        )

    # ------------------------------------------------------------------ fields
    def test_01_duration_uses_the_core_total_work(self):
        """One duration definition: the core ``total_work`` field."""
        self.assertNotIn(
            "duration_hours",
            self.env["field.operation"]._fields,
            "a second hours field reintroduces two answers for the same question",
        )
        operation = self._operation(
            start_date="2026-10-10 08:00:00",
            end_date="2026-10-10 10:30:00",
            person_ids=[(6, 0, (self.employee_a | self.employee_b).ids)],
        )
        self.assertAlmostEqual(operation.total_work, 2.5, places=2)
        self.assertEqual(operation.person_count, 2)
        self.assertAlmostEqual(operation.duration_per_person, 1.25, places=2)

    def test_02_service_without_end_is_unmeasured(self):
        """No end date: duration 0 and no per-person figure, not a guess."""
        operation = self._operation(start_date="2026-10-10 08:00:00")
        self.assertEqual(operation.total_work, 0.0)
        self.assertEqual(operation.duration_per_person, 0.0)

    def test_03_report_date_is_cut_in_the_company_timezone(self):
        """22:00 UTC is the next day in Istanbul: the stored day must follow."""
        self.company.partner_id.tz = "Europe/Istanbul"
        operation = self._operation(start_date="2026-10-24 22:00:00")
        self.assertEqual(
            operation.report_date,
            date(2026, 10, 25),
            "the day must be cut in the company timezone, not in UTC",
        )

        self.company.partner_id.tz = "UTC"
        operation_utc = self._operation(start_date="2026-10-24 22:00:00")
        self.assertEqual(operation_utc.report_date, date(2026, 10, 24))

    # ------------------------------------------------------------------ wizard
    def test_04_wizard_aggregates_the_period_and_skips_cancelled(self):
        """Counts, staff, signature and amount per period; cancelled excluded."""
        self._operation(
            start_date="2026-10-10 08:00:00",
            end_date="2026-10-10 09:00:00",
            status="done",
            signed=True,
            service_price=100.0,
            service_type_id=self.service_type.id,
        )
        self._operation(
            start_date="2026-10-10 11:00:00",
            status="draft",
            service_price=200.0,
            service_type_id=self.service_type.id,
        )
        self._operation(
            start_date="2026-10-10 12:00:00",
            status="cancel",
            service_price=999.0,
            service_type_id=self.service_type.id,
        )

        wizard = self._wizard(date(2026, 10, 10), date(2026, 10, 10))
        self.assertEqual(wizard.operation_count, 2)
        self.assertFalse(wizard.multi_currency)

        totals = wizard._get_report_data()["totals"]
        self.assertEqual(totals["services"], 2)
        self.assertEqual(totals["done"], 1)
        self.assertEqual(totals["open"], 1)
        self.assertEqual(totals["signed"], 1)
        self.assertEqual(totals["measured"], 1)
        self.assertAlmostEqual(totals["amount"], 300.0, places=2)

    def test_05_period_outside_the_range_is_empty(self):
        """A service outside the period must not leak into the report."""
        self._operation(
            start_date="2026-10-10 08:00:00", end_date="2026-10-10 09:00:00"
        )
        wizard = self._wizard(date(2026, 11, 1), date(2026, 11, 30))
        self.assertEqual(wizard.operation_count, 0)
        self.assertEqual(wizard._get_report_data()["totals"]["services"], 0)

    # -------------------------------------------------------------------- views
    def test_06_analysis_is_the_core_pivot_extended(self):
        """One pivot in the database: the core one, with the reporting fields."""
        arch = etree.fromstring(
            self.env["field.operation"].get_view(view_type="pivot")["arch"]
        )
        names = [node.get("name") for node in arch.iter("field")]
        self.assertIn("report_date", names)
        self.assertIn("duration_per_person", names)
        self.assertIn("total_work", names)
        self.assertFalse(
            self.env.ref(
                "field_operation_report.view_field_operation_report_pivot",
                raise_if_not_found=False,
            ),
            "a second pivot copy would show the same analysis twice",
        )

    def test_07_team_report_renders(self):
        """The QWeb team report must render with real data, not only install."""
        self._operation(
            start_date="2026-10-10 08:00:00",
            end_date="2026-10-10 09:30:00",
            status="done",
            service_price=50.0,
            service_type_id=self.service_type.id,
        )
        wizard = self._wizard(date(2026, 10, 10), date(2026, 10, 10))
        html, report_type = self.env["ir.actions.report"]._render_qweb_html(
            "field_operation_report.field_operation_team_report", wizard.ids
        )
        self.assertEqual(report_type, "html")
        self.assertIn(b"Field Service Team Report", html)
        self.assertIn(self.team.name.encode(), html)
