{
    "name": "Field Operation Stock",
    "version": "19.0.1.1.0",
    "category": "Services/Field Service",
    "summary": "Stock consumption tracking for field operations",
    "description": """
Field Operation Stock
=====================

Stock consumption tracking for field service operations.

Features:
---------
* Track materials consumed during field operations
* Two consumption types: service included / warranty
* Automatic stock picking creation on confirmation
* Cost calculation per operation
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "field_operation",
        "stock",
        "product",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/sequence_data.xml",
        "views/field_operation_stock_line_view.xml",
        "views/field_operation_view.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
