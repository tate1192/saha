# Copyright(C) 2026 - Today Softteknik Bilişim
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import re

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFieldOperationStock(TransactionCase):
    """Behavioural tests for the stock consumption flow.

    The suite pins the invariants that were broken before the fix:

    * confirming a field operation must actually move the stock (P0): in 19.0 a
      move is validated only when it is picked, so writing the done quantity
      alone left the transfer assigned and the stock untouched while the
      consumption lines were already flagged done;
    * the stock move values must use the 19.0 field names (`product_uom`, no
      `name`), otherwise the picking creation raises before anything happens;
    * an insufficient stock error must leave nothing behind;
    * the reference, the subtotals and the per-type operation costs.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.partner = cls.env["res.partner"].create({"name": "Stock Test Customer"})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_product(self, quantity=10.0, price=12.5):
        product = self.env["product.product"].create(
            {
                "name": "Stock Test Product",
                "is_storable": True,
                "standard_price": price,
            }
        )
        if quantity:
            self.env["stock.quant"]._update_available_quantity(
                product, self.stock_location, quantity
            )
        return product

    def _make_operation(self):
        return self.env["field.operation"].create({"partner_id": self.partner.id})

    def _make_line(self, operation, product, quantity=1.0, **vals):
        base = {
            "operation_id": operation.id,
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "quantity": quantity,
        }
        base.update(vals)
        return self.env["field.operation.stock.line"].create(base)

    def _customer_quantity(self, product):
        return self.env["stock.quant"]._get_available_quantity(
            product, self.customer_location
        )

    # ------------------------------------------------------------------
    # P0: the confirmation flow
    # ------------------------------------------------------------------
    def test_confirm_consumes_stock(self):
        """Confirming a draft line must pick, validate and move the stock."""
        product = self._make_product(quantity=10.0)
        operation = self._make_operation()
        line = self._make_line(operation, product, quantity=3.0, unit_price=12.5)

        operation.action_confirm_stock()

        picking = line.stock_picking_id
        move = line.stock_move_id
        self.assertTrue(picking, "The confirmation must create a stock picking")
        self.assertTrue(move, "The line must be linked to its stock move")
        self.assertEqual(move.product_id, product)
        self.assertEqual(move.product_uom, line.product_uom_id)
        self.assertEqual(
            move.product_uom_qty,
            3.0,
            "The move must carry the consumed quantity",
        )
        self.assertTrue(move.picked, "The move must be picked to be validated in 19.0")
        self.assertEqual(move.state, "done", "The stock move must be validated")
        self.assertEqual(picking.state, "done", "The transfer must be validated")
        self.assertEqual(line.state, "done")
        self.assertEqual(
            product.qty_available,
            7.0,
            "The stock must actually leave the source location",
        )
        self.assertEqual(
            self._customer_quantity(product),
            3.0,
            "The consumed quantity must land on the customer location",
        )

    def test_confirm_uses_the_current_stock_move_field_names(self):
        """The picking must be created with the 19.0 `stock.move` field names.

        `name` and `product_uom_id` do not exist on `stock.move` in 19.0, so a
        wrong name raises a ValueError before the picking exists.
        """
        move_fields = self.env["stock.move"]._fields
        self.assertNotIn("name", move_fields)
        self.assertIn("product_uom", move_fields)

        product = self._make_product(quantity=5.0)
        operation = self._make_operation()
        line = self._make_line(operation, product, quantity=1.0)

        operation.action_confirm_stock()

        self.assertEqual(line.state, "done")
        self.assertEqual(line.stock_picking_id.move_ids.state, "done")

    def test_confirm_without_stock_leaves_nothing_behind(self):
        """An insufficient stock error must roll the whole request back."""
        product = self._make_product(quantity=2.0)
        operation = self._make_operation()
        line = self._make_line(operation, product, quantity=99.0)

        pickings_before = self.env["stock.picking"].search([])
        with self.assertRaises(UserError), self.env.cr.savepoint():
            operation.action_confirm_stock()

        self.assertEqual(line.state, "draft", "The line must stay draft")
        self.assertFalse(line.stock_picking_id)
        self.assertFalse(line.stock_move_id)
        self.assertEqual(
            self.env["stock.picking"].search([]),
            pickings_before,
            "No picking may survive the rollback",
        )
        self.assertEqual(product.qty_available, 2.0)

    def test_confirm_requires_a_draft_line(self):
        """Without a draft line there is nothing to send to the stock."""
        product = self._make_product(quantity=5.0)
        operation = self._make_operation()
        self._make_line(operation, product, quantity=1.0)

        operation.action_confirm_stock()
        line = operation.stock_line_ids
        self.assertEqual(line.state, "done")
        with self.assertRaises(UserError):
            operation.action_confirm_stock()

    def test_two_lines_of_the_same_product_move_the_total(self):
        """Two lines of one product share one merged move (core merges them)."""
        product = self._make_product(quantity=10.0)
        operation = self._make_operation()
        first = self._make_line(operation, product, quantity=1.0)
        second = self._make_line(operation, product, quantity=2.0)

        operation.action_confirm_stock()

        picking = first.stock_picking_id
        self.assertEqual(picking, second.stock_picking_id)
        self.assertEqual(len(picking.move_ids), 1)
        self.assertEqual(picking.move_ids.product_uom_qty, 3.0)
        self.assertEqual(first.stock_move_id, second.stock_move_id)
        self.assertEqual(first.state, "done")
        self.assertEqual(second.state, "done")
        self.assertEqual(product.qty_available, 7.0)

    # ------------------------------------------------------------------
    # Fields and guards
    # ------------------------------------------------------------------
    def test_reference_is_taken_from_the_sequence(self):
        product = self._make_product()
        operation = self._make_operation()

        line = self._make_line(operation, product, quantity=1.0)

        self.assertRegex(line.name, re.compile(r"^SL\d{5}$"))
        second = self._make_line(operation, product, quantity=1.0)
        self.assertNotEqual(line.name, second.name)

    def test_quantity_must_be_positive(self):
        product = self._make_product()
        operation = self._make_operation()

        with self.assertRaises(UserError):
            self._make_line(operation, product, quantity=0.0)

    def test_subtotal_and_operation_costs_are_split_by_consumption_type(self):
        """Draft lines stay out of the cost totals; confirmed ones are counted."""
        product = self._make_product(quantity=10.0)
        operation = self._make_operation()
        serviced = self._make_line(
            operation,
            product,
            quantity=2.0,
            unit_price=10.0,
            consumption_type="serviced",
        )
        warranty = self._make_line(
            operation,
            product,
            quantity=3.0,
            unit_price=10.0,
            consumption_type="warranty",
        )

        self.assertEqual(serviced.subtotal, 20.0)
        self.assertEqual(warranty.subtotal, 30.0)
        self.assertEqual(operation.stock_line_count, 2)
        self.assertEqual(
            operation.total_stock_all,
            0.0,
            "Draft lines are deliberately excluded from the cost totals",
        )

        operation.action_confirm_stock()

        self.assertEqual(operation.total_stock_cost, 20.0)
        self.assertEqual(operation.total_warranty_cost, 30.0)
        self.assertEqual(operation.total_stock_all, 50.0)

    def test_a_completed_line_cannot_be_cancelled(self):
        """Cancelling a line whose move is done is refused, so the cost stays."""
        product = self._make_product(quantity=10.0)
        operation = self._make_operation()
        line = self._make_line(operation, product, quantity=2.0, unit_price=10.0)
        operation.action_confirm_stock()
        self.assertEqual(operation.total_stock_cost, 20.0)

        with self.assertRaises(UserError):
            line.action_cancel()

        self.assertEqual(line.state, "done")
        self.assertEqual(operation.total_stock_cost, 20.0)

    def test_a_completed_line_cannot_be_deleted(self):
        """A done line is the only trace of its move, so it cannot be unlinked."""
        product = self._make_product(quantity=10.0)
        operation = self._make_operation()
        line = self._make_line(operation, product, quantity=2.0, unit_price=10.0)
        operation.action_confirm_stock()
        move = line.stock_move_id

        with self.assertRaises(UserError):
            line.unlink()

        self.assertTrue(line.exists())
        self.assertEqual(line.state, "done")
        self.assertEqual(move.state, "done")
        self.assertEqual(operation.total_stock_cost, 20.0)

    def test_a_draft_line_can_be_deleted(self):
        product = self._make_product()
        operation = self._make_operation()
        line = self._make_line(operation, product, quantity=1.0)

        line.unlink()

        self.assertFalse(line.exists())

    def test_the_line_form_has_no_manual_confirm_button(self):
        """The only confirmation path is the operation's 'Confirm stock' button.

        The per-line `action_confirm` used to set `confirmed` without creating
        any stock move, and such a line was then ignored by the operation flow
        (it only picks up draft lines) while still entering the cost totals.
        """
        view = self.env.ref(
            "field_operation_stock.view_field_operation_stock_line_form"
        )
        self.assertNotIn("action_confirm", view.arch)

    def test_multi_company_isolation(self):
        """A user of company A must not see company B's consumption lines."""
        company_a = self.env["res.company"].create({"name": "Stock Company A"})
        company_b = self.env["res.company"].create({"name": "Stock Company B"})
        service_user_group = self.env.ref("field_operation.service_group_user")
        user_a = self.env["res.users"].create(
            {
                "name": "Stock Company A User",
                "login": "company_a_user_field_operation_stock_test",
                "company_id": company_a.id,
                "company_ids": [(6, 0, [company_a.id])],
                "group_ids": [(6, 0, [service_user_group.id])],
            }
        )
        product = self._make_product()
        operation_a = self.env["field.operation"].create(
            {"partner_id": self.partner.id, "company_id": company_a.id}
        )
        operation_b = self.env["field.operation"].create(
            {"partner_id": self.partner.id, "company_id": company_b.id}
        )
        line_a = self._make_line(
            operation_a, product, quantity=1.0, company_id=company_a.id
        )
        line_b = self._make_line(
            operation_b, product, quantity=1.0, company_id=company_b.id
        )

        visible = (
            self.env["field.operation.stock.line"]
            .with_user(user_a)
            .search([("id", "in", [line_a.id, line_b.id])])
        )

        self.assertIn(line_a, visible)
        self.assertNotIn(line_b, visible)

    # ------------------------------------------------------------------
    # T8 - the money fields are office-only
    # ------------------------------------------------------------------
    def test_worker_cannot_read_the_costs(self):
        """A worker reads the operation and the line without the money fields."""
        worker_group = self.env.ref("field_operation.service_group_worker")
        worker = self.env["res.users"].create(
            {
                "name": "Stock Read-only Worker",
                "login": "stock_readonly_worker",
                "group_ids": [(6, 0, [worker_group.id])],
            }
        )
        employee = self.env["hr.employee"].create(
            {"name": "Stock Worker Employee", "user_id": worker.id}
        )
        operation = self._make_operation()
        operation.write({"person_ids": [(6, 0, employee.ids)], "status": "planned"})
        product = self._make_product(quantity=4.0)
        line = self._make_line(operation, product, quantity=1.0, unit_price=12.5)
        self.assertEqual(line.subtotal, 12.5)

        self.assertNotIn(
            "total_stock_cost",
            self.env["field.operation"].with_user(worker).fields_get(),
        )
        self.assertNotIn(
            "unit_price",
            self.env["field.operation.stock.line"].with_user(worker).fields_get(),
        )
        with self.assertRaises(AccessError):
            operation.with_user(worker).read(["total_stock_cost"])
        with self.assertRaises(AccessError):
            line.with_user(worker).read(["unit_price"])
