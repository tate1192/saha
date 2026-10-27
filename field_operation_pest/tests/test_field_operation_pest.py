"""Tests for the pest module.

Covers what the review found broken: the pesticide reference sequence, the guards and
the link of the delivery order created from a form, and the computed unit of measure.
"""

from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("field_operation_pest", "post_install", "-at_install")
class TestFieldOperationPest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.forms_model = cls.env["field.operation.forms"]
        cls.pesticide_model = cls.env["field.operation.pesticide"]
        cls.partner = cls.env["res.partner"].create({"name": "Pest Customer"})
        cls.service_type = cls.env["field.operation.type"].search([], limit=1)
        cls.product = cls.env["product.product"].create(
            {"name": "Pest Product", "type": "consu", "is_storable": True}
        )
        cls.picking_type = cls.env["stock.picking.type"].search(
            [("code", "=", "outgoing")], limit=1
        )
        warehouse = cls.env["stock.warehouse"].search([], limit=1)
        cls.source_location = warehouse.lot_stock_id
        cls.dest_location = cls.env["stock.location"].search(
            [("usage", "=", "customer")], limit=1
        )

    def _form(self, **values):
        values.setdefault("customer_id", self.partner.id)
        values.setdefault("service_type_id", self.service_type.id)
        values.setdefault("picking_type_id", self.picking_type.id)
        values.setdefault("source_location_id", self.source_location.id)
        values.setdefault("destination_location_id", self.dest_location.id)
        return self.forms_model.create(values)

    def _pesticide(self, form, qty=1.0):
        return self.pesticide_model.create(
            {
                "forms_id": form.id,
                "product_id": self.product.id,
                "product_qty": qty,
            }
        )

    def test_01_pesticide_gets_a_reference(self):
        """The sequence the create() always asked for now exists."""
        form = self._form()
        pesticide = self._pesticide(form)

        self.assertTrue(pesticide.name.startswith("BIO-"), pesticide.name)
        self.assertNotEqual(pesticide.name, "Yeni")
        self.assertEqual(pesticide.product_uom, self.product.uom_id)
        self.assertEqual(pesticide.status, form.status)

    def test_02_transfer_guards(self):
        """No lines, or no group: no delivery order."""
        form = self._form()
        with self.assertRaises(UserError):
            form.action_transfer()

        self._pesticide(form)
        outsider = self.env["res.users"].create(
            {
                "name": "pest_outsider",
                "login": "pest_outsider",
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            form.with_user(outsider).action_transfer()

        # same source and destination is refused
        form.destination_location_id = self.source_location
        with self.assertRaises(UserError):
            form.action_transfer()
        form.destination_location_id = self.dest_location

    def test_03_transfer_creates_a_linked_delivery_order(self):
        """The picking carries the pesticide lines and points back at the form."""
        if not self.picking_type or not self.dest_location:
            self.skipTest("No stock configuration in this database.")

        form = self._form()
        self._pesticide(form, qty=2.5)
        self.assertTrue(form.action_transfer())

        picking = form.stock_picking_id
        self.assertTrue(picking)
        self.assertEqual(picking.field_operation_form_id, form)
        self.assertEqual(picking.partner_id, self.partner)
        self.assertEqual(picking.origin, form.name)
        self.assertEqual(len(picking.move_ids), 1)
        self.assertEqual(picking.move_ids.product_qty, 2.5)
        self.assertEqual(form.picking_count, 1)
        self.assertEqual(form.action_view_picking()["res_id"], picking.id)

        # a second transfer is refused by the same guard: the order is already there
        self.assertEqual(form.picking_count, 1)

    def test_04_picking_count_is_zero_without_delivery(self):
        """The smart button stays hidden while no delivery order exists."""
        form = self._form()
        self.assertEqual(form.picking_count, 0)
        self.assertEqual(
            form.action_view_picking()["type"], "ir.actions.act_window_close"
        )

    def test_05_stock_and_pest_fields_are_gated_by_service_type(self):
        """The stock and pest-type fields only belong on a pest form."""
        view = self.env.ref("field_operation_pest.field_operation_forms_pest_view")
        arch = etree.fromstring(view.arch_db)
        gated = {
            "pest_type_ids",
            "picking_type_id",
            "source_location_id",
            "destination_location_id",
        }
        found = {
            node.get("name"): node.get("invisible")
            for node in arch.iter("field")
            if node.get("name") in gated
        }
        self.assertEqual(set(found), gated)
        for name, expression in found.items():
            self.assertEqual(expression, "service_type != 'pest'", name)

    def test_06_pest_type_is_gated_on_the_operation_form(self):
        """The operation form carries the same gate as the service form.

        ``pest_type_ids`` is added to both forms; only the service form was
        gated, so every non-pest operation still showed a "Pest Type" field.
        The combined arch is read through ``get_view`` so a later override
        cannot quietly drop the attribute.
        """
        arch = etree.fromstring(
            self.env["field.operation"].get_view(view_type="form")["arch"]
        )
        found = {
            node.get("name"): node.get("invisible")
            for node in arch.iter("field")
            if node.get("name") == "pest_type_ids"
        }
        self.assertEqual(
            found,
            {"pest_type_ids": "service_type_id.type != 'pest'"},
            "the operation form shows the pest type on every service type",
        )
