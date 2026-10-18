{
    "name": "Field Operation Forms Extension",
    "version": "19.0.1.1.0",
    "category": "Services/Field Service",
    "summary": "Map and Route functionality for Field Operation Forms",
    "description": """
Field Operation Forms Extension
===============================

Extended functionality for field operation forms with geolocation.

Features:
---------
* Form geolocation integration
* Extended form capabilities

The WhatsApp shortcut was removed on purpose: field_operation_whatsapp is not
ready yet. Add the dependency and the button back once it is.
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "field_operation_forms",
        "field_operation_geolocation",
    ],
    "data": [
        "views/field_operation_forms_view.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
