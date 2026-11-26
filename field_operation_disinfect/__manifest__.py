{
    "name": "Field Operation Disinfect Form",
    "version": "19.0.1.3.0",
    "category": "Services/Field Service",
    "summary": "Field service operation disinfection forms",
    "description": """
Field Operation Disinfect Form
==============================

Disinfection forms for field service operations.

The module is operation-centric: the disinfection lines and the PH/CL
readings live on ``field.operation`` and the operation service report carries
that section. Shared catalog and company metadata live in
``field_operation_disinfect_common``. The independent
``field_operation_forms_disinfect`` module provides the service-form flow
without depending on this module.
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": ["field_operation_disinfect_common"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/ir_sequence_data.xml",
        "views/field_operation_view.xml",
        "pdf/field_disinfect_operation_pdf.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
