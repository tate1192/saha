{
    "name": "Field Operation Machine",
    "version": "19.0.1.2.0",
    "category": "Services/Field Service",
    "summary": "Field service operation machine management",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "field_operation",
        "stock",
        "product",
        # hr is used directly: machine.maintenance.technician_id targets
        # hr.employee, which was previously only available transitively.
        "hr",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/sequence_data.xml",
        "views/machine_master_view.xml",
        "views/machine_maintenance_view.xml",
        "views/machine_spare_part_view.xml",
        "views/field_operation_view.xml",
    ],
    "external_dependencies": {
        "python": [
            "qrcode",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
