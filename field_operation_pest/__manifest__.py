{
    "name": "Field Operation Pest Form",
    "version": "19.0.1.3.0",
    "category": "Services/Field Service",
    "summary": "Field service operation pest control forms",
    "description": """
Field Operation Pest Form
=========================

Pest control forms for field service operations.

The module is operation-centric: pesticide lines and the biocidal
application details live on ``field.operation`` and the operation service
report carries the pest section. Shared catalog and product metadata live in
``field_operation_pest_common``. The independent ``field_operation_forms_pest``
module provides the service-form flow without depending on this module.
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": ["field_operation_pest_common"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/ir_sequence_data.xml",
        "views/field_operation_view.xml",
        "pdf/field_pest_operation_pdf.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
