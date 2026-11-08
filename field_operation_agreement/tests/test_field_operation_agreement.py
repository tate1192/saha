# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase

WORKER_GROUP = "field_operation.service_group_worker"


@tagged("post_install", "-at_install")
class TestFieldOperationAgreement(TransactionCase):
    """Contract tests for field.operation.agreement and its template."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Agreement = cls.env["field.operation.agreement"]
        cls.Template = cls.env["field.operation.agreement.template"]
        cls.Operation = cls.env["field.operation"]
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Agreement Test Customer",
                "is_company": True,
            }
        )

    def _create_agreement(self, **overrides):
        values = {
            "name": "Test Agreement",
            "partner_id": self.partner.id,
            "start_date": fields.Date.today(),
            "end_date": fields.Date.today() + timedelta(days=365),
        }
        values.update(overrides)
        return self.Agreement.create(values)

    def test_01_content_onchange_refreshes_variables(self):
        """The content onchange rebuilds variables and never links id 5."""
        template = self.Template.create(
            {
                "name": "Cleanup Template",
                "agreement_type": "service",
                "content": "<p>{{1}} {{2}}</p>",
            }
        )
        template.variable_ids = [
            (0, 0, {"name": "{{1}}"}),
            (0, 0, {"name": "{{2}}"}),
        ]
        self.assertEqual(len(template.variable_ids), 2)

        # Dropping every placeholder must clear the lines. The buggy code
        # instead bound the unrelated variable record whose id is 5.
        with Form(template) as form:
            form.content = "<p>No placeholders left</p>"
            self.assertEqual(len(form.variable_ids), 0)
            self.assertNotIn(5, [rec.get("id") for rec in form.variable_ids._records])

        # Replacing the placeholders regenerates the matching lines only.
        with Form(template) as form:
            form.content = "<p>{{3}}</p>"
            self.assertEqual(len(form.variable_ids), 1)
            self.assertEqual(form.variable_ids.edit(0).name, "{{3}}")
            self.assertNotIn(5, [rec.get("id") for rec in form.variable_ids._records])

    def test_02_status_transition_guards(self):
        """Each transition only runs from the states it is meant for."""
        future = fields.Date.today() + timedelta(days=30)

        agreement = self._create_agreement(status="draft", end_date=future)
        agreement.action_activate()
        self.assertEqual(agreement.status, "active")
        agreement.action_expire()
        self.assertEqual(agreement.status, "expired")
        # Activation is allowed again from an expired record.
        agreement.action_activate()
        self.assertEqual(agreement.status, "active")

        draft = self._create_agreement(status="draft", end_date=future)
        with self.assertRaises(ValidationError):
            draft.action_expire()
        with self.assertRaises(ValidationError):
            draft.action_draft()

        cancelled = self._create_agreement(status="draft", end_date=future)
        cancelled.action_activate()
        cancelled.action_cancel()
        self.assertEqual(cancelled.status, "cancelled")
        with self.assertRaises(ValidationError):
            cancelled.action_cancel()
        with self.assertRaises(ValidationError):
            cancelled.action_activate()

    def test_03_worker_cannot_activate(self):
        """A field worker is read-only and cannot activate an agreement."""
        worker_group = self.env.ref(WORKER_GROUP)
        worker = self.env["res.users"].create(
            {
                "name": "Agreement Read-only Worker",
                "login": "agreement_readonly_worker",
                "group_ids": [(6, 0, [worker_group.id])],
            }
        )
        agreement = self._create_agreement(
            status="draft", end_date=fields.Date.today() + timedelta(days=30)
        )
        with self.assertRaises(AccessError):
            agreement.with_user(worker).action_activate()

    def test_04_signature_integrity(self):
        """The signed flag needs a signature; writing one stamps the record."""
        with self.assertRaises(ValidationError):
            self._create_agreement(signed=True)

        agreement = self._create_agreement()
        with self.assertRaises(ValidationError):
            agreement.write({"signed": True})

        agreement.write(
            {
                "signature": base64.b64encode(b"signed-bytes").decode(),
            }
        )
        self.assertTrue(agreement.signed)
        self.assertTrue(agreement.signed_on)
        self.assertTrue(agreement.signed_by)

    def test_05_unlink_blocked_by_linked_operations(self):
        """An agreement with field operations already attached cannot go."""
        agreement = self._create_agreement()
        operation = self.Operation.create({"agreement_id": agreement.id})
        self.assertIn(operation, agreement.field_operation_ids)

        with self.assertRaises(UserError):
            agreement.unlink()

        operation.agreement_id = False
        agreement.unlink()
        self.assertFalse(agreement.exists())

    def test_06_expiry_handled_by_cron(self):
        """Expiry is a cron job, not something a constraint forces."""
        today = fields.Date.today()
        past = today - timedelta(days=5)
        future = today + timedelta(days=30)

        stale = self._create_agreement(
            status="active",
            start_date=past - timedelta(days=1),
            end_date=past,
        )
        self.assertEqual(stale.status, "active")

        self.Agreement._cron_expire_agreements()
        self.assertEqual(stale.status, "expired")

        valid = self._create_agreement(status="active", end_date=future)
        self.Agreement._cron_expire_agreements()
        self.assertEqual(valid.status, "active")

    def test_07_sample_template_is_not_production_data(self):
        """The sample template belongs to demo data, not a production set."""
        self.assertIsNone(
            self.env.ref(
                "field_operation_agreement.template_cnc_service",
                raise_if_not_found=False,
            )
        )

    def test_08_reference_is_unique(self):
        """Each agreement gets its own sequence reference."""
        first = self._create_agreement()
        second = self._create_agreement()
        self.assertNotEqual(first.reference, "/")
        self.assertNotEqual(second.reference, "/")
        self.assertNotEqual(first.reference, second.reference)

    def test_09_worker_cannot_read_the_amount(self):
        """The total amount is office data; the worker sees no money."""
        worker_group = self.env.ref(WORKER_GROUP)
        worker = self.env["res.users"].create(
            {
                "name": "Agreement Amount Worker",
                "login": "agreement_amount_worker",
                "group_ids": [(6, 0, [worker_group.id])],
            }
        )
        agreement = self._create_agreement(total_amount=750.0)
        self.assertEqual(agreement.total_amount, 750.0)
        self.assertNotIn("total_amount", self.Agreement.with_user(worker).fields_get())
        with self.assertRaises(AccessError):
            agreement.with_user(worker).read(["total_amount"])
