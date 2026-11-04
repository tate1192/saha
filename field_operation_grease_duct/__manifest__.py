{
    "name": "Field Operation Grease Duct",
    "version": "19.0.1.0.0",
    "category": "Services/Field Service",
    "summary": "Grease duct cleaning measurements and certificate",
    "description": """
Field Operation Grease Duct
===========================

Grease duct (kitchen hood, horizontal and vertical duct) cleaning records for
field service operations, printed as a cleaning certificate.

Features:
---------
* Hood, duct and filter measurements on the operation form
* Access status and access note for blocked or unreachable duct sections
* Certificate number from its own sequence
* Certificate PDF printing the measured values, technicians and signatures
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 125,
    "depends": [
        "field_operation",
        "field_operation_forms",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/grease_duct_security.xml",
        "data/ir_sequence_data.xml",
        "views/field_operation_forms_view.xml",
        "report/grease_duct_templates.xml",
        "report/grease_duct_reports.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
