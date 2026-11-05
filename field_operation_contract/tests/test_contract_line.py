# tests/test_contract_line.py

# Copyright 2024 Softteknik Bilişim
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.tests.common import TransactionCase
from odoo.tools import SQL


class TestContractLine(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
            }
        )
        self.product = self.env["product.product"].create(
            {
                "name": "Test Service",
                "type": "service",
                "lst_price": 100.0,
            }
        )
        self.contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date(2024, 1, 1),
            }
        )

    def test_remaining_count_calculation(self):
        """Test kalan servis sayısı hesaplama"""
        line = self.env["field.operation.contract.line"].create(
            {
                "contract_id": self.contract.id,
                "product_id": self.product.id,
                "total_service": 5,
                "generated_occurrences": 2,
                "price_unit": 100,
            }
        )
        # 5 - 2 = 3 remaining
        self.assertEqual(line.remaining_count, 3)

    def test_remaining_count_not_negative(self):
        """Test remaining_count negatif olmamalı"""
        line = self.env["field.operation.contract.line"].create(
            {
                "contract_id": self.contract.id,
                "product_id": self.product.id,
                "total_service": 2,
                "generated_occurrences": 5,  # Fazla üretim
                "price_unit": 100,
            }
        )
        # max(0, 2-5) = 0
        self.assertEqual(line.remaining_count, 0)

    def test_subtotal_calculation(self):
        """Test ara toplam hesaplama"""
        line = self.env["field.operation.contract.line"].create(
            {
                "contract_id": self.contract.id,
                "product_id": self.product.id,
                "total_service": 2,
                "price_unit": 100.0,
                "discount": 10.0,  # %10 indirim
            }
        )
        # 2 * 100 * 0.9 = 180
        self.assertEqual(line.price_subtotal, 180.0)

    def test_location_default_from_partner(self):
        """Test location default değer partner'dan gelmeli"""
        # Partner'a delivery adresi ekle
        delivery = self.env["res.partner"].create(
            {
                "name": "Delivery Address",
                "parent_id": self.partner.id,
                "type": "delivery",
            }
        )

        line = self.env["field.operation.contract.line"].create(
            {
                "contract_id": self.contract.id,
                "product_id": self.product.id,
            }
        )

        # Delivery adresi otomatik seçilmeli
        self.assertEqual(line.location_id, delivery)

    def test_available_locations_domain(self):
        """Test available_locations domain hesaplama"""
        # Child addresses
        child1 = self.env["res.partner"].create(
            {
                "name": "Branch 1",
                "parent_id": self.partner.id,
                "type": "delivery",
            }
        )
        child2 = self.env["res.partner"].create(
            {
                "name": "Other Address",
                "parent_id": self.partner.id,
                "type": "other",
            }
        )
        # Invoice type dahil olmamalı
        child3 = self.env["res.partner"].create(
            {
                "name": "Invoice Address",
                "parent_id": self.partner.id,
                "type": "invoice",
            }
        )

        line = self.env["field.operation.contract.line"].create(
            {
                "contract_id": self.contract.id,
                "product_id": self.product.id,
            }
        )

        # Partner + delivery + other olmalı, invoice olmamalı
        self.assertIn(self.partner, line.available_location_ids)
        self.assertIn(child1, line.available_location_ids)
        self.assertIn(child2, line.available_location_ids)
        self.assertNotIn(child3, line.available_location_ids)

    def test_compute_subtotal_store(self):
        """Test subtotal stored computed field"""
        line = self.env["field.operation.contract.line"].create(
            {
                "contract_id": self.contract.id,
                "product_id": self.product.id,
                "total_service": 3,
                "price_unit": 100,
                "discount": 0,
            }
        )
        # Değerin store edildiğini kontrol et (DB'de var)
        line.flush_recordset()
        self.env.cr.execute(
            SQL(
                "SELECT price_subtotal FROM field_operation_contract_line "
                "WHERE id = %s",
                line.id,
            )
        )
        result = self.env.cr.fetchone()
        self.assertEqual(result[0], 300.0)
