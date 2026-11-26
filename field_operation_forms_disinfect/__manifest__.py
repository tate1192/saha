{
    "name": "Field Operation Forms Disinfect",
    "version": "19.0.1.4.0",
    "category": "Services/Field Service",
    "summary": "Disinfection tab, PDF and e-mail on field operation forms",
    "description": """
Field Operation Forms Disinfect
===============================

Disinfection forms for customers using ``field_operation_forms``. The
disinfection tab, signed service-form PDF and e-mail template work without
``field_operation_disinfect``. The shared product catalog comes from
``field_operation_disinfect_common``. Form-side lines live in their own model
(``field.operation.forms.disinfect``) and do not create or modify an operation.
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 121,
    "depends": [
        "field_operation_disinfect_common",
        "field_operation_forms",
    ],
    "data": [
        "forms_security/ir.model.access.csv",
        "forms_security/security.xml",
        "data_forms/ir_sequence_data.xml",
        "views/field_operation_forms_view.xml",
        "pdf/field_disinfect_pdf.xml",
        "ph_cl_report.xml",
        "data/email_template.xml",
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
