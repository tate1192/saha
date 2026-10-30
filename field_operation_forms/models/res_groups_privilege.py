# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models

#: Privileges this module used to create, one per level. They are replaced by
#: the single "Forms" privilege the data file now declares.
LEGACY_PRIVILEGES = (
    "field_operation_forms.privilege_forms_user",
    "field_operation_forms.privilege_forms_all",
    "field_operation_forms.privilege_forms_manager",
)

#: The category those privileges used to live in, one per module.
LEGACY_CATEGORY = "field_operation_forms.field_operation_forms_module_category"


class ResGroupsPrivilege(models.Model):
    """Remove the per-level privileges and the module's own category.

    A data file cannot delete a record it no longer declares, so dropping the
    three privileges (and the category that held them) is done from here: it
    runs on install and on update alike, and on a fresh install there is
    nothing to remove.
    """

    _inherit = "res.groups.privilege"

    @api.model
    def _field_operation_forms_drop_legacy_privileges(self):
        for xmlid in LEGACY_PRIVILEGES:
            privilege = self.env.ref(xmlid, raise_if_not_found=False)
            if not privilege:
                continue
            # A privilege still holding groups is in use: leave it alone rather
            # than break the user form.
            if privilege.group_ids:
                continue
            privilege.unlink()
        category = self.env.ref(LEGACY_CATEGORY, raise_if_not_found=False)
        if category and not category.privilege_ids and not category.module_ids:
            category.unlink()
