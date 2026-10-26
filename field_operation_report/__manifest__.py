{
    "name": "Field Operation Report",
    "version": "19.0.1.1.0",
    "category": "Services/Field Service",
    "summary": "Team, district and service type reporting for field operations",
    "description": """
Field Operation Report
======================

Reporting layer on top of ``field_operation``.

Features:
---------
* Reporting fields on the service: report date, duration, team size,
  duration per person.
* Field service analysis pivot and graph (period x team x service type).
* Data quality filters: services without end date, staff, price or signature.
* Printable team report for a chosen period (PDF).
* Printable service detail report for the selected services (PDF).
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "license": "AGPL-3",
    "sequence": 121,
    "depends": [
        "field_operation",
    ],
    "data": [
        "security/ir.model.access.csv",
        "report/field_operation_templates.xml",
        "report/field_operation_reports.xml",
        "wizard/field_operation_report_wizard_views.xml",
        "views/field_operation_report_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
