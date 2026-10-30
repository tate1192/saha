# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models

#: The name the privilege carries in English. The Turkish UI gets its own value
#: from `i18n/tr.po` ("Servis").
PRIVILEGE_NAME = "Service"
PRIVILEGE_SEQUENCE = 10


class ResGroupsPrivilege(models.Model):
    """Re-file the module's privilege into the suite's shared category.

    `data/res_groups_privilege.xml` used to be loaded with `noupdate="1"`: the
    flag lives in `ir_model_data` and Odoo never downgrades it, so dropping the
    attribute from the file does nothing for a database that already holds the
    record -- it keeps the old name ("Field Operation") and stays without a
    category, i.e. the user form shows it outside any box. The file is the
    source of truth for fresh installs; this runs on install and on update and
    writes only what differs.
    """

    _inherit = "res.groups.privilege"

    @api.model
    def _field_operation_refile_privilege(self):
        privilege = self.env.ref(
            "field_operation.field_operation_privilege", raise_if_not_found=False
        )
        if not privilege:
            return
        category = self.env.ref("field_operation.module_category_saha_operation")
        if privilege.category_id != category or privilege.sequence != PRIVILEGE_SEQUENCE:
            privilege.write(
                {"category_id": category.id, "sequence": PRIVILEGE_SEQUENCE}
            )
        # Write the English value explicitly: a plain write would land in the
        # language of the environment, leaving the source term stale.
        if privilege.with_context(lang="en_US").name != PRIVILEGE_NAME:
            privilege.with_context(lang="en_US").name = PRIVILEGE_NAME
