"""Tests for the field_operation_sale bridge.

Both directions are covered — service → sale (wizard) and sale → service
(``create_sale_service``) — plus the guards around them and the counters, which used to
be computed without a dependency and would not move when the link changed.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("field_operation_sale", "post_install", "-at_install")
class TestFieldOperationSale(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sale_group = cls.env.ref(
            "field_operation_sale.group_field_operation_sale_enabled"
        )
        cls.env.user.group_ids = [(4, cls.sale_group.id)]
        cls.partner = cls.env["res.partner"].create({"name": "Bridge Customer"})
        cls.service_product = cls.env["product.product"].create(
            {
                "name": "Bridge Service",
                "type": "service",
                "sale_ok": True,
                "list_price": 250.0,
            }
        )
        cls.wizard_model = cls.env["field.operation.create.sale.wizard"]

    def _operation(self, **values):
        defaults = {
            "subject": "Bridge Job",
            "partner_id": self.partner.id,
            "status": "done",
            "service_price": 250.0,
        }
        defaults.update(values)
        return self.env["field.operation"].create(defaults)

    def _sale(self, **values):
        defaults = {"partner_id": self.partner.id, "order_types": "service"}
        defaults.update(values)
        return self.env["sale.order"].create(defaults)

    def _wizard(self, operations, model=None):
        # `model or self.wizard_model` would be a trap: an empty recordset is falsy,
        # so the caller env (with_user) would silently be replaced by this one
        model = self.wizard_model if model is None else model
        return model.with_context(active_ids=operations.ids).create(
            {
                "operation_ids": [(6, 0, operations.ids)],
                "product_id": self.service_product.id,
            }
        )

    def _user_without_sale_group(self, extra_group=None):
        groups = [self.env.ref("field_operation.service_group_user").id]
        if extra_group:
            groups.append(self.env.ref(extra_group).id)
        return self.env["res.users"].create(
            {
                "name": "Office Without Sale Group",
                "login": "office_without_sale_group",
                "group_ids": [(6, 0, groups)],
            }
        )

    def _foreign_pricelist(self):
        """A pricelist in a currency other than the company's."""
        company_currency = self.env.company.currency_id
        currency = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search(
                [("id", "!=", company_currency.id), ("name", "in", ("USD", "EUR"))],
                limit=1,
            )
        )
        currency.active = True
        return self.env["product.pricelist"].create(
            {"name": "Foreign Probe", "currency_id": currency.id}
        )

    def test_01_wizard_creates_a_draft_sale_and_links_both_ways(self):
        """The wizard turns a service into a draft order with its price and customer."""
        operation = self._operation()
        wizard = self._wizard(operation)
        self.assertEqual(wizard.operation_ids, operation)

        action = wizard.action_create_sale()
        sale = self.env["sale.order"].browse(action["domain"][0][2])

        self.assertEqual(len(sale), 1)
        self.assertEqual(sale.state, "draft")
        self.assertEqual(sale.partner_id, self.partner)
        self.assertEqual(sale.order_types, "service")
        self.assertEqual(sale.field_operation_ids, operation)
        self.assertEqual(operation.sale_id, sale)
        self.assertEqual(len(sale.order_line), 1)
        self.assertEqual(sale.order_line.price_unit, 250.0)
        self.assertEqual(sale.order_line.name, operation.subject)
        self.assertEqual(operation.sale_count, 1)
        self.assertEqual(sale.field_operation_count, 1)

    def test_02_wizard_refuses_a_service_without_customer(self):
        """A sale order needs a customer: the wizard says so instead of the ORM."""
        operation = self._operation(partner_id=False)
        wizard = self._wizard(operation)
        with self.assertRaises(UserError):
            wizard.action_create_sale()
        self.assertFalse(operation.sale_id)

    def test_03_wizard_needs_the_module_group(self):
        """The button is hidden by a group; the model must enforce the same group."""
        user = self._user_without_sale_group()
        self.assertFalse(
            user.has_group("field_operation_sale.group_field_operation_sale_enabled")
        )
        # the office record rule only shows the user their own services
        operation = self._operation(user_id=user.id)
        wizard = self._wizard(operation, model=self.wizard_model.with_user(user))
        self.assertEqual(wizard.env.user, user)
        with self.assertRaises(AccessError):
            wizard.action_create_sale()
        self.assertFalse(operation.sale_id)

    def test_04_invoice_preparation_carries_the_service(self):
        """The service pointing at the order reaches the invoice reference."""
        operation = self._operation()
        sale = self._sale()
        operation.sale_id = sale
        self.assertEqual(sale._prepare_invoice()["field_operation_id"], operation.id)

        # several services: the first one is carried over
        second = self._operation(subject="Second Job")
        second.sale_id = sale
        self.assertEqual(sale._prepare_invoice()["field_operation_id"], operation.id)

    def test_05_create_sale_service_makes_one_service_per_line(self):
        """One operation per product line, priced from the line, and no duplicates."""
        sale = self._sale(
            order_line=[
                (
                    0,
                    0,
                    {
                        "product_id": self.service_product.id,
                        "product_uom_qty": 2,
                        "price_unit": 100.0,
                    },
                ),
                (
                    0,
                    0,
                    {
                        "product_id": self.service_product.id,
                        "product_uom_qty": 1,
                        "price_unit": 50.0,
                    },
                ),
            ]
        )
        self.assertEqual(sale.field_operation_count, 0)

        sale.create_sale_service()

        # the counter follows the new services (it used to stay at 0)
        self.assertEqual(sale.field_operation_count, 2)
        self.assertEqual(sale.field_operation_ids.partner_id, self.partner)
        self.assertEqual(
            sorted(sale.field_operation_ids.mapped("service_price")), [50.0, 200.0]
        )
        # start_date is a real timestamp, not midnight UTC coming from a date
        limit = fields.Datetime.now() - timedelta(minutes=5)
        for operation in sale.field_operation_ids:
            self.assertGreater(operation.start_date, limit)
            self.assertEqual(operation.sale_id, sale)

        with self.assertRaises(UserError):
            sale.create_sale_service()
        self.assertEqual(sale.field_operation_count, 2)

    def test_06_create_sale_service_needs_the_module_group(self):
        """A sale manager without the module group cannot create services this way."""
        user = self._user_without_sale_group("sales_team.group_sale_salesman")
        sale = self._sale(
            order_line=[
                (
                    0,
                    0,
                    {
                        "product_id": self.service_product.id,
                        "product_uom_qty": 1,
                        "price_unit": 10.0,
                    },
                ),
            ]
        ).with_user(user)
        with self.assertRaises(AccessError):
            sale.create_sale_service()
        # read back as the test user: the guard must have stopped it before any write
        created = self.env["field.operation"].search([("sale_id", "=", sale.id)])
        self.assertFalse(created)

    def test_07_wizard_refuses_a_service_that_already_has_a_sale(self):
        """A sold service is not sold twice, no orphan draft order is left behind."""
        sale = self._sale()
        operation = self._operation(sale_id=sale.id)
        wizard = self._wizard(operation)
        order_count = self.env["sale.order"].search_count([])

        with self.assertRaises(UserError):
            wizard.action_create_sale()

        # the existing link is untouched and no second order was created
        self.assertEqual(operation.sale_id, sale)
        self.assertEqual(self.env["sale.order"].search_count([]), order_count)

    def test_08_create_sale_button_hides_itself_once_the_service_is_sold(self):
        """The header button carries the ``sale_id`` condition, not the status alone."""
        arch = self.env.ref(
            "field_operation_sale.sale_order_field_operation_form_view"
        ).arch
        self.assertIn("status not in ('done',)", arch)
        self.assertIn("or sale_id", arch)

    def test_09_create_sale_service_stores_the_line_and_the_order_currency(self):
        """Each service keeps its line; the order currency is copied too."""
        pricelist = self._foreign_pricelist()
        sale = self._sale(
            pricelist_id=pricelist.id,
            order_line=[
                (
                    0,
                    0,
                    {
                        "product_id": self.service_product.id,
                        "product_uom_qty": 1,
                        "price_unit": 100.0,
                    },
                ),
                (
                    0,
                    0,
                    {
                        "product_id": self.service_product.id,
                        "product_uom_qty": 1,
                        "price_unit": 50.0,
                    },
                ),
            ],
        )
        self.assertEqual(sale.currency_id, pricelist.currency_id)

        sale.create_sale_service()

        self.assertEqual(
            sorted(sale.field_operation_ids.mapped("sale_line_id").ids),
            sorted(sale.order_line.ids),
        )
        self.assertEqual(
            sale.field_operation_ids.mapped("currency_id"), pricelist.currency_id
        )

    def test_10_cancelled_order_creates_no_service_and_keeps_the_link(self):
        """Cancelling blocks new services; the services created earlier stay linked."""
        sale = self._sale(
            order_line=[
                (
                    0,
                    0,
                    {
                        "product_id": self.service_product.id,
                        "product_uom_qty": 1,
                        "price_unit": 10.0,
                    },
                ),
            ]
        )
        sale.create_sale_service()
        operation = sale.field_operation_ids

        sale.action_cancel()
        self.assertEqual(sale.state, "cancel")
        self.assertEqual(operation.sale_id, sale)
        self.assertEqual(operation.sale_line_id, sale.order_line)

        with self.assertRaises(UserError):
            sale.create_sale_service()
        self.assertEqual(sale.field_operation_ids, operation)

    def test_11_wizard_refuses_a_foreign_currency_without_a_pricelist(self):
        """A foreign-currency service with no pricelist in that currency is refused.

        Picking the customer's pricelist would not convert the amount, it would only
        relabel it, so the wizard stops instead of booking a wrong price.
        """
        pricelist = self._foreign_pricelist()
        currency = pricelist.currency_id
        # no pricelist in that currency may be picked, archived ones included
        self.env["product.pricelist"].with_context(active_test=False).search(
            [("currency_id", "=", currency.id)]
        ).write({"active": False})
        operation = self._operation(currency_id=currency.id)
        self.assertNotEqual(operation.currency_id, self.env.company.currency_id)
        order_count = self.env["sale.order"].search_count([])

        wizard = self._wizard(operation)
        with self.assertRaises(UserError):
            wizard.action_create_sale()

        self.assertFalse(operation.sale_id)
        self.assertFalse(operation.sale_line_id)
        # the refusal happens before any order exists: no orphan draft is left
        self.assertEqual(self.env["sale.order"].search_count([]), order_count)

    def test_12_wizard_pricelist_and_currency_follow_the_service(self):
        """The order is created in the service's currency.

        A service already in the company currency needs no pricelist at all: an order
        without one lands in the same currency, so the copied price needs no
        conversion. When the customer has a pricelist it is the natural pick.
        """
        operation = self._operation()
        wizard = self._wizard(operation)
        action = wizard.action_create_sale()
        sale = self.env["sale.order"].browse(action["domain"][0][2])
        self.assertEqual(
            sale.pricelist_id,
            self.partner.property_product_pricelist,
        )
        self.assertEqual(sale.currency_id, operation.currency_id)

    def test_13_wizard_falls_back_to_a_pricelist_in_the_service_currency(self):
        """A foreign-currency service still gets an order, without conversion.

        With no usable pricelist the wizard used to create the order first and only
        then complain; now an equivalent pricelist in the service's currency is picked
        and the order inventory exactly matches the service price.
        """
        pricelist = self._foreign_pricelist()
        currency = pricelist.currency_id
        operation = self._operation(service_price=120.0, currency_id=currency.id)

        wizard = self._wizard(operation)
        action = wizard.action_create_sale()
        sale = self.env["sale.order"].browse(action["domain"][0][2])

        self.assertEqual(sale.pricelist_id.currency_id, currency)
        self.assertEqual(sale.currency_id, currency)
        self.assertEqual(sale.order_line.price_unit, 120.0)
        self.assertFalse(sale.order_line.discount)

    def test_14_wizard_refuses_an_unknown_currency(self):
        """A service with no currency at all is refused, not silently ordered."""
        operation = self._operation(currency_id=False)
        wizard = self._wizard(operation)
        order_count = self.env["sale.order"].search_count([])
        with self.assertRaises(UserError):
            wizard.action_create_sale()
        self.assertFalse(operation.sale_id)
        self.assertEqual(self.env["sale.order"].search_count([]), order_count)

    def test_15_default_get_ignores_foreign_active_ids(self):
        """``active_ids`` from another model must not end up as service links."""
        wizard = self.wizard_model.with_context(active_model="res.partner").create(
            {"product_id": self.service_product.id}
        )
        self.assertFalse(wizard.operation_ids)

    def test_16_stat_button_opens_the_single_service_or_the_list(self):
        """One service opens its form, several open the filtered list."""
        sale = self._sale()
        operation = self._operation()
        operation.sale_id = sale.id

        action = sale.show_field_operation()
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["res_id"], operation.id)

        second = self._operation(subject="Second Job")
        second.sale_id = sale.id

        action = sale.show_field_operation()
        self.assertEqual(action["view_mode"], "list,form")
        self.assertEqual(action["domain"], [("sale_id", "=", sale.id)])
