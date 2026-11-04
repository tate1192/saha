{
    "name": "Field Operation Time Off",
    "version": "19.0.1.0.0",
    "category": "Services/Field Service",
    "summary": "Create a field operation for every day an employee is on leave",
    "description": """
Field Operation Time Off
========================

Keeps the field service planning aware of approved time off: for every day an
employee is on leave, a field operation is created that marks the employee as
unavailable.

Features:
---------
* Approved leaves create one operation per leave day
* The operation carries the employee, the time off type and the leave reference
* Refused, cancelled or deleted leaves remove their operations
* Changing the dates of an approved leave rebuilds its operations
* The existing leave/overlap checks of the field operation module keep working
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 126,
    "depends": [
        "field_operation",
        "hr_holidays",
    ],
    "data": [
        "data/field_operation_type_data.xml",
        "views/field_operation_views.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
