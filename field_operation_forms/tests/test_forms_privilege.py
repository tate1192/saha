"""The module contributes one privilege ("Forms") to the suite's category."""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.field_operation_forms.models.res_groups_privilege import (
    LEGACY_CATEGORY,
    LEGACY_PRIVILEGES,
)


@tagged("post_install", "-at_install")
class TestFormsPrivilege(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.privilege = cls.env.ref("field_operation_forms.privilege_forms")
        cls.category = cls.env.ref("field_operation.module_category_saha_operation")

    def test_the_module_has_one_privilege_in_the_shared_category(self):
        self.assertEqual(self.privilege.name, "Forms")
        self.assertEqual(self.privilege.category_id, self.category)

    def test_its_three_levels_hang_off_that_privilege(self):
        """Field User / All Data / Field Manager are the dropdown, not rows."""
        groups = self.privilege.group_ids
        self.assertEqual(
            set(groups.mapped("name")), {"Field User", "All Data", "Field Manager"}
        )
        self.assertTrue(all(group.privilege_id == self.privilege for group in groups))

    def test_the_per_level_privileges_are_gone(self):
        for xmlid in LEGACY_PRIVILEGES:
            self.assertFalse(
                self.env.ref(xmlid, raise_if_not_found=False),
                "%s must be replaced by privilege_forms" % xmlid,
            )
        self.assertFalse(self.env.ref(LEGACY_CATEGORY, raise_if_not_found=False))
