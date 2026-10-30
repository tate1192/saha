{
    "name": "Field Operation Forms",
    "version": "19.0.1.2.0",
    "category": "Services/Field Service",
    "summary": "Field service operation forms",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "field_operation",
    ],
    "data": [
        "data/forms_data.xml",
        # Shared PDF header/footer: field_operation_disinfect calls it, and this
        # module's own service_form_pdf report uses it as its layout.
        "templates/pdf_header_footer.xml",
        "templates/service_form_pdf.xml",
        "data/form_service_email.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/field_operation_view.xml",
        "views/field_operation_forms_view.xml",
        "views/menu.xml",
        "templates/forms_portal.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
