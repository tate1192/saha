"""Post-migration: reset remaining_count on contract lines that are stuck
on the previous mixin default (10**9). Recompute via total_service -
generated_occurrences so the value matches the field definition.

Why only > 1_000_000: avoids clobbering legitimate user-edited values on
lines with a real (small) remaining_count. Lines hit by the bad mixin
default were exactly 1_000_000_000.
"""

from odoo.tools import SQL


def migrate(cr, version):
    cr.execute(
        SQL(
            """
            UPDATE field_operation_contract_line
            SET remaining_count = GREATEST(
                0,
                COALESCE(total_service, 0)::int
                - COALESCE(generated_occurrences, 0)::int
            )
            WHERE remaining_count > 1000000
            """
        )
    )
