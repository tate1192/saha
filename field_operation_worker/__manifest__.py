{
    "name": "Field Operation Worker",
    "version": "19.0.1.2.0",
    "category": "Services/Field Service",
    "summary": "Limited visibility for field operations personnel.",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "field_operation",
    ],
    "data": [
        "views/field_operation_worker_view.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
