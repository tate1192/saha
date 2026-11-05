# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tools import SQL


def migrate(cr, version):
    """Drop contract_template_id column and contract template table.

    The field.operation.contract.template model has been removed from the
    module. The contract_terms HTML field on field.operation.contract is
    preserved so previously-copied template content is not lost.
    """
    cr.execute(
        SQL(
            "ALTER TABLE field_operation_contract "
            "DROP COLUMN IF EXISTS contract_template_id"
        )
    )
    cr.execute(SQL("DROP TABLE IF EXISTS field_operation_contract_template CASCADE"))
