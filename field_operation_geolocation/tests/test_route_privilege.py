"""The module contributes one privilege ("Route") to the suite's category."""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.field_operation_geolocation.models.res_groups_privilege import (
    LEGACY_CATEGORY,
    LEGACY_PRIVILEGES,
)


@tagged("post_install", "-at_install")
class TestRoutePrivilege(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.privilege = cls.env.ref("field_operation_geolocation.privilege_route")
        cls.category = cls.env.ref("field_operation.module_category_saha_operation")

    def test_the_module_has_one_privilege_in_the_shared_category(self):
        self.assertEqual(self.privilege.name, "Route")
        self.assertEqual(self.privilege.category_id, self.category)

    def test_its_two_levels_hang_off_that_privilege(self):
        groups = self.privilege.group_ids
        self.assertEqual(set(groups.mapped("name")), {"User", "Manager"})

    def test_the_per_level_privileges_are_gone(self):
        for xmlid in LEGACY_PRIVILEGES:
            self.assertFalse(
                self.env.ref(xmlid, raise_if_not_found=False),
                "%s must be replaced by privilege_route" % xmlid,
            )
        self.assertFalse(self.env.ref(LEGACY_CATEGORY, raise_if_not_found=False))
