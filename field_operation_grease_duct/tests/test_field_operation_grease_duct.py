"""Tests for the grease duct module.

Covers the certificate numbering, the measurement totals and the certificate
rendering the values typed on the operation form.
"""

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("field_operation_grease_duct", "post_install", "-at_install")
class TestFieldOperationGreaseDuct(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The certificate prints in the customer language: the Turkish labels live
        # in i18n/tr.po. Activation alone does not import them, so this asks for the
        # translations too (a fresh database only ships en_US active).
        cls.env["res.lang"]._activate_and_install_lang("tr_TR")
        cls.forms_model = cls.env["field.operation.forms"]
        cls.line_model = cls.env["field.operation.grease.duct.line"]
        cls.partner = cls.env["res.partner"].create({"name": "Metroway Kebab"})
        cls.grease_type = cls.env["field.operation.type"].create(
            {"name": "Grease Duct (test)", "type": "grease_duct"}
        )
        cls.other_type = cls.env["field.operation.type"].create(
            {"name": "General (test)", "type": "general"}
        )

    def _form(self, service_type):
        return self.forms_model.create(
            {
                "customer_id": self.partner.id,
                "service_type_id": service_type.id,
            }
        )

    def _lines(self, form):
        return self.line_model.create(
            [
                {"forms_id": form.id, "duct_type": "hood", "quantity": 2},
                {"forms_id": form.id, "duct_type": "horizontal", "length": 8.0},
                {"forms_id": form.id, "duct_type": "vertical", "length": 4.5},
            ]
        )

    def test_01_grease_duct_form_gets_a_certificate_number(self):
        form = self._form(self.grease_type)
        self.assertTrue(form.grease_duct_no.startswith("GRD-"), form.grease_duct_no)

    def test_02_other_service_types_stay_unnumbered(self):
        self.assertFalse(self._form(self.other_type).grease_duct_no)

    def test_03_switching_the_service_type_assigns_the_number(self):
        form = self._form(self.other_type)
        form.service_type_id = self.grease_type
        self.assertTrue(form.grease_duct_no.startswith("GRD-"), form.grease_duct_no)

    def test_04_total_length_sums_the_measurement_lines(self):
        form = self._form(self.grease_type)
        self._lines(form)
        self.assertEqual(form.grease_total_length, 12.5)

    def test_05_certificate_prints_the_measured_values(self):
        # The customer language drives the report (t-lang in the template).
        self.partner.lang = "en_US"
        form = self._form(self.grease_type)
        form.write(
            {
                "start_date": "2026-11-04 09:00:00",
                "grease_access_status": "partial",
                "grease_access_note": "Catwalk needed above the ceiling.",
                "grease_next_cleaning_date": "2027-05-04",
            }
        )
        self._lines(form)

        report = self.env.ref(
            "field_operation_grease_duct.action_grease_duct_certificate"
        )
        self.assertEqual(report.model, "field.operation.forms")

        html, _report_type = (
            self.env["ir.actions.report"]
            .with_context(lang="en_US")
            ._render_qweb_html(report, form.ids)
        )
        html = html.decode() if isinstance(html, bytes) else html
        for expected in (
            "Grease Duct Cleaning Certificate",
            "Metroway Kebab",
            form.grease_duct_no,
            "Catwalk needed above the ceiling.",
        ):
            self.assertIn(expected, html)

    @patch(
        "odoo.addons.base.models.ir_actions_report.IrActionsReport._run_wkhtmltopdf",
        return_value=b"%PDF-1.4\n% mocked by the test\n",
    )
    def test_07_certificate_renders_a_pdf(self, run_wkhtmltopdf):
        """The certificate reaches the PDF pipeline (the binary itself is mocked).

        A real wkhtmltopdf run fetches the report assets over HTTP from inside the
        open test transaction and can hang the whole suite on a headless machine;
        test_06 already checks the rendered HTML.
        """
        form = self._form(self.grease_type)
        self._lines(form)
        report = self.env.ref(
            "field_operation_grease_duct.action_grease_duct_certificate"
        )
        self.assertEqual(report.report_type, "qweb-pdf")
        pdf, report_type = (
            self.env["ir.actions.report"]
            .with_context(force_report_rendering=True)
            ._render_qweb_pdf(report, form.ids)
        )
        self.assertEqual(report_type, "pdf")
        self.assertTrue(
            pdf.startswith(b"%PDF"), "the certificate did not reach the PDF pipeline"
        )
        run_wkhtmltopdf.assert_called_once()

    def test_06_certificate_follows_the_customer_language(self):
        """A Turkish customer gets the Turkish labels shipped in i18n/tr.po."""
        self.partner.lang = "tr_TR"
        form = self._form(self.grease_type)
        self._lines(form)

        report = self.env.ref(
            "field_operation_grease_duct.action_grease_duct_certificate"
        )
        html, _report_type = self.env["ir.actions.report"]._render_qweb_html(
            report, form.ids
        )
        html = html.decode() if isinstance(html, bytes) else html
        for expected in ("Sertifika No", "Toplam Kanal Uzunluğu", "Müşteri"):
            self.assertIn(expected, html)
