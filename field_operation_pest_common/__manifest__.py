{
    "name": "Field Operation Pest Common",
    "version": "19.0.1.0.0",
    "category": "Services/Field Service",
    "summary": "Shared pest catalog and biocidal product metadata",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "license": "AGPL-3",
    "depends": [
        "field_operation",
        "product",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/field_operation_pest_type_view.xml",
        "views/product_template_view.xml",
        "views/res_company_view.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
    "pre_init_hook": "pre_init_hook",
}
