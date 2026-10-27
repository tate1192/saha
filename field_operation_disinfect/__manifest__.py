{
    "name": "Field Operation Disinfect Form",
    "version": "19.0.1.1.1",
    "category": "Services/Field Service",
    "summary": "Field service operation disinfection forms",
    "description": """
Field Operation Disinfect Form
==============================

Disinfection forms for field service operations.

Features:
---------
* Disinfection form management
* Product management
* Company configuration
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "field_operation",
        "field_operation_forms",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/ir_sequence_data.xml",
        "views/res_company_view.xml",
        "views/field_operation_forms_view.xml",
        "views/field_disinfect_product_view.xml",
        # PDF must load before the mail template (report_template_ids ref).
        "pdf/field_disinfect_pdf.xml",
        "data/email_template.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
