from odoo.tools import SQL

OLD_MODULE = "field_operation_pest"
COMMON_MODULE = "field_operation_pest_common"

MOVED_XMLIDS = {
    "ir.model": (
        "model_field_operation_pest_type",
        "model_field_operation_type",
        "model_product_template",
        "model_res_company",
    ),
    "ir.model.access": (
        "field_operation_pest_type_all",
        "field_operation_pest_type_user",
        "field_operation_pest_type_manager",
    ),
    "ir.model.fields.selection": ("selection__field_operation_type__type__pest",),
    "ir.actions.act_window": ("action_field_operation_pest_type",),
    "ir.ui.menu": ("menu_field_operation_pest_type",),
    "ir.ui.view": (
        "field_operation_pest_type_search_view",
        "field_operation_pest_type_form_view",
        "field_operation_pest_type_list_view",
        "field_product_template_view_form",
        "field_product_template_tree_view",
        "view_company_field_operation_form",
    ),
    "uom.uom": ("uom_ml", "uom_mg", "ug", "mmol"),
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
                "field.operation.pest.type",
                "field.operation.type",
                "product.template",
                "product.product",
                "res.company",
            ],
        )
    )


def pre_init_hook(env):
    move_shared_xmlids(env)
