"""The suite's privileges share one category, one row per module."""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSahaPrivilegeCategory(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env.ref("field_operation.module_category_saha_operation")
        cls.privilege = cls.env.ref("field_operation.field_operation_privilege")

    def test_the_category_exists_once(self):
        """One box for the suite, not one per module."""
        self.assertEqual(self.category.name, "Field Operations")
        self.assertEqual(self.category.sequence, 23)

    def test_the_module_contributes_one_privilege(self):
        """This module's row is "Service" and it sits in the shared box."""
        self.assertEqual(self.privilege.name, "Service")
        self.assertEqual(self.privilege.category_id, self.category)
        self.assertEqual(self.privilege.sequence, 10)

    def test_the_category_holds_one_row_per_installed_module(self):
        """Service / Forms / Route: the rows core shows for its own areas.

        The siblings are optional (a database may run `field_operation` alone),
        so the expectation follows what is actually installed.
        """
        modules = self.env["ir.module.module"].search(
            [("name", "=", "field_operation_forms"), ("state", "=", "installed")]
        )
        expected = {"Service"}
        if modules:
            expected.add("Forms")
        modules = self.env["ir.module.module"].search(
            [("name", "=", "field_operation_geolocation"), ("state", "=", "installed")]
        )
        if modules:
            expected.add("Route")
        self.assertEqual(set(self.category.privilege_ids.mapped("name")), expected)

    def test_no_per_module_category_is_left(self):
        """The two categories the suite used to create are gone."""
        for xmlid in (
            "field_operation_forms.field_operation_forms_module_category",
            "field_operation_geolocation.module_category_field_operation_route",
        ):
            self.assertFalse(
                self.env.ref(xmlid, raise_if_not_found=False),
                "%s must not survive: it would be an empty box in the user form" % xmlid,
            )
