# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def _operation_link(cr, line_table):
    """Column that reaches the operation from a legacy line table.

    19.0.1.1.x line tables carry no operation link; there the operation is
    reached through the form the line belongs to.
    """
    if sql.column_exists(cr, line_table, "operation_id"):
        return "line.operation_id"
    return "form.operation_id"


def _restore_operation_values(env):
    """Bring the operation-side pest headers back to the form.

    The core migration copies the old form header values to the operation.  On
    databases where they never lived on the operation the columns are absent
    and there is nothing to restore.
    """
    cr = env.cr
    if not (
        sql.column_exists(cr, "field_operation", "hygiene")
        and sql.column_exists(cr, "field_operation_forms", "hygiene")
    ):
        return
    cr.execute(
        """
        UPDATE field_operation_forms AS form
           SET hygiene = COALESCE(form.hygiene, FALSE)
                         OR COALESCE(operation.hygiene, FALSE),
               infestation = COALESCE(form.infestation, FALSE)
                             OR COALESCE(operation.infestation, FALSE),
               insulation = COALESCE(form.insulation, FALSE)
                            OR COALESCE(operation.insulation, FALSE),
               storage = COALESCE(form.storage, FALSE)
                         OR COALESCE(operation.storage, FALSE),
               efk_ift = COALESCE(form.efk_ift, FALSE)
                         OR COALESCE(operation.efk_ift, FALSE),
               monitors = COALESCE(form.monitors, FALSE)
                          OR COALESCE(operation.monitors, FALSE),
               others = COALESCE(form.others, FALSE)
                        OR COALESCE(operation.others, FALSE),
               residence = COALESCE(form.residence, operation.residence),
               place = COALESCE(form.place, operation.place),
               application_method = COALESCE(
                   form.application_method, operation.application_method
               ),
               security_precautions = COALESCE(
                   form.security_precautions, operation.security_precautions
               ),
               responsible_manager_id = COALESCE(
                   form.responsible_manager_id, operation.responsible_manager_id
               ),
               application_place = COALESCE(
                   form.application_place, operation.application_place
               )
          FROM field_operation AS operation
         WHERE form.operation_id = operation.id
           AND form.service_type = 'pest'
        """
    )


def copy_legacy_form_data(env):
    """Move the legacy service-form pest data to the independent form model.

    The core module keeps the operation-side lines and copies the old form
    header values to the operation during its own migration.  This helper runs
    both when the bridge is installed for the first time (post-init hook) and
    when an already installed bridge is upgraded (post-migration).
    """
    cr = env.cr
    if not sql.column_exists(cr, "field_operation_pesticide", "forms_id"):
        return

    Line = env["field.operation.forms.pest"]
    if not Line.search_count([]):
        operation_link = _operation_link(cr, "field_operation_pesticide")
        cr.execute(
            f"""
            INSERT INTO field_operation_forms_pest
                        (name, sequence, forms_id, product_id, product_uom,
                         product_qty, used_equipment, company_id, customer_id,
                         user_id, subject, status, start_date, end_date,
                         create_uid, create_date, write_uid, write_date)
            SELECT line.name, 10, line.forms_id, line.product_id,
                   line.product_uom, line.product_qty, line.used_equipment,
                   form.company_id, form.customer_id, form.user_id,
                   form.subject, COALESCE(line.status, form.status),
                   COALESCE(operation.start_date, form.start_date),
                   COALESCE(operation.end_date, form.end_date),
                   line.create_uid, line.create_date,
                   line.write_uid, line.write_date
              FROM field_operation_pesticide AS line
              JOIN field_operation_forms AS form ON form.id = line.forms_id
              LEFT JOIN field_operation AS operation
                ON operation.id = {operation_link}
             WHERE line.forms_id IS NOT NULL
            """
        )
        copied = cr.rowcount
        cr.execute(
            """
            SELECT id
              FROM field_operation_forms_pest
             WHERE name IS NULL OR name IN ('', '/', 'New', 'Yeni')
            """
        )
        for (line_id,) in cr.fetchall():
            name = env["ir.sequence"].next_by_code("field.forms.pest") or "/"
            cr.execute(
                "UPDATE field_operation_forms_pest SET name = %s WHERE id = %s",
                (name, line_id),
            )
        _logger.info("Copied %s pest form lines to the form model.", copied)

    _restore_operation_values(env)

    if sql.table_exists(
        cr, "field_operation_forms_field_operation_pest_type_rel"
    ) and sql.table_exists(cr, "field_operation_field_operation_pest_type_rel"):
        cr.execute(
            """
            INSERT INTO field_operation_forms_field_operation_pest_type_rel
                        (field_operation_forms_id, field_operation_pest_type_id)
            SELECT form.id, rel.field_operation_pest_type_id
              FROM field_operation_forms AS form
              JOIN field_operation_field_operation_pest_type_rel AS rel
                ON rel.field_operation_id = form.operation_id
             WHERE form.service_type = 'pest'
               AND form.operation_id IS NOT NULL
            ON CONFLICT DO NOTHING
            """
        )

    # If the old form stock columns were dropped by the core update, rebuild
    # them from the delivery order that points back at the form.
    if sql.column_exists(cr, "stock_picking", "field_operation_form_id"):
        cr.execute(
            """
            UPDATE field_operation_forms AS form
               SET stock_picking_id = COALESCE(
                       form.stock_picking_id, picking.id
                   ),
                   picking_type_id = COALESCE(
                       form.picking_type_id, picking.picking_type_id
                   ),
                   source_location_id = COALESCE(
                       form.source_location_id, picking.location_id
                   ),
                   destination_location_id = COALESCE(
                       form.destination_location_id, picking.location_dest_id
                   )
              FROM (
                  SELECT DISTINCT ON (field_operation_form_id)
                         field_operation_form_id,
                         id,
                         picking_type_id,
                         location_id,
                         location_dest_id
                    FROM stock_picking
                   WHERE field_operation_form_id IS NOT NULL
                   ORDER BY field_operation_form_id, id DESC
              ) AS picking
             WHERE picking.field_operation_form_id = form.id
            """
        )
