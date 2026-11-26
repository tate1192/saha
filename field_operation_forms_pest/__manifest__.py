{
    "name": "Field Operation Forms Pest",
    "version": "19.0.1.4.0",
    "category": "Services/Field Service",
    "summary": "Pest tab, stock delivery and form rules on field operation forms",
    "description": """
Field Operation Forms Pest
==========================

Pest control forms for customers using ``field_operation_forms``. The
biocidal/pesticide tab, stock delivery flow and form record rules work
without ``field_operation_pest``. Shared catalog and product metadata come
from ``field_operation_pest_common``. Form-side lines live in their own model
(``field.operation.forms.pest``) and do not create or modify an operation.
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 121,
    "depends": [
        "field_operation_pest_common",
        "field_operation_forms",
        "stock",
    ],
    "data": [
        "forms_security/ir.model.access.csv",
        "forms_security/security.xml",
        "data/ir_sequence_data.xml",
        "views/field_operation_forms_view.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
}
