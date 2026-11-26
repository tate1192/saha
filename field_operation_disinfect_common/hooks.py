from odoo.tools import SQL

OLD_MODULE = "field_operation_disinfect"
COMMON_MODULE = "field_operation_disinfect_common"

MOVED_XMLIDS = {
    "ir.model": (
        "model_field_disinfect_product",
        "model_field_operation_type",
        "model_res_company",
    ),
    "ir.model.access": (
        "field_field_disinfect_product_worker",
        "field_field_disinfect_product_user",
        "field_field_disinfect_product_manager",
    ),
    "ir.model.fields.selection": (
        "selection__field_disinfect_product__priority__0",
        "selection__field_disinfect_product__priority__1",
        "selection__field_disinfect_product__type__dispenser",
        "selection__field_disinfect_product__type__tank",
        "selection__field_operation_type__type__disinfect",
    ),
    "ir.actions.act_window": ("action_field_disinfect_product",),
    "ir.ui.menu": ("menu_field_disinfect_product",),
    "ir.ui.view": (
        "field_disinfect_product_search_view",
        "field_disinfect_product_list_view",
        "field_disinfect_product_form_view",
        "field_disinfect_product_view_pivot",
        "view_company_field_operation_form",
    ),
}


def move_shared_xmlids(env):
    """Give the common module ownership of records that must survive."""
    for model, names in MOVED_XMLIDS.items():
        env.cr.execute(
            SQL(
                """
                UPDATE ir_model_data
                   SET module = %s
                 WHERE module = %s
                   AND model = %s
                   AND name = ANY(%s)
                """,
                COMMON_MODULE,
                OLD_MODULE,
                model,
                list(names),
            )
        )
    env.cr.execute(
        SQL(
            """
            UPDATE ir_model_data AS data
               SET module = %s
              FROM ir_model_fields AS field
             WHERE data.model = 'ir.model.fields'
               AND data.res_id = field.id
               AND data.module = %s
               AND field.model = ANY(%s)
            """,
            COMMON_MODULE,
            OLD_MODULE,
            [
                "field.disinfect.product",
                "field.operation.type",
                "res.company",
            ],
        )
    )


def pre_init_hook(env):
    move_shared_xmlids(env)
