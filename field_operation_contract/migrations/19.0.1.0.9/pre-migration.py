"""The portal templates used to be declared with noupdate="1". Their content
has been rewritten (home card + signature form + status badges). Reset the
noupdate flag so the updated data files are applied on module update.
"""

from odoo.tools import SQL


def migrate(cr, version):
    cr.execute(
        SQL(
            """
            UPDATE ir_model_data
            SET noupdate = FALSE
            WHERE module = 'field_operation_contract'
              AND name IN ('portal_my_contracts', 'portal_contract_page')
            """
        )
    )
