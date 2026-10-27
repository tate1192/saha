{
    "name": "Field Operation Pest Form",
    "version": "19.0.1.1.2",
    "category": "Services/Field Service",
    "summary": "Field service operation pest control forms",
    "description": """
Field Operation Pest Form
=========================

Pest control forms for field service operations.

Features:
---------
* Pest control form management
* Product and stock integration
* Pest type management
* Company configuration
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "stock",
        "field_operation",
        "field_operation_forms",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "views/res_company_view.xml",
        "views/product_template_view.xml",
        "views/field_operation_view.xml",
        "views/field_operation_form_view.xml",
        "views/field_operation_pest_type_view.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
