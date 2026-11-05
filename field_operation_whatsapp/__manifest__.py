{
    "name": "Field Operation WhatsApp",
    "version": "19.0.1.1.0",
    "category": "Services/Field Service",
    "summary": "WhatsApp messages for field operations through the wa.me link",
    "description": """
Field Operation WhatsApp
========================

Send WhatsApp messages to the customer from a field operation, with reusable
templates and a message log.

Features:
---------
* WhatsApp message templates with {placeholder} fields
* Send wizard on the field operation form
* Optional service report link in the message
* Message log per operation, per company
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 127,
    "depends": [
        "field_operation",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "views/field_operation_view.xml",
        "views/field_whatsapp_template_view.xml",
        "wizard/field_whatsapp_message.xml",
        "data/field_whatsapp_template_data.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
