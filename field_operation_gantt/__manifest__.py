# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Field Operation Gantt",
    "version": "19.0.1.2.0",
    "category": "Services/Field Service",
    "summary": "Gantt view of the field operations (soft_gantt view type)",
    "description": """
Field Operation Gantt
=====================

Offers a Gantt view of ``field.operation`` records on top of the ``soft_gantt``
view type, in the Field Operations action.

* the view type, the rendering and the date arithmetic belong to ``soft_gantt``
* this module only declares the view and the two read-only figures it draws:
  a completion percentage and a bar colour, both derived from ``status``
* a user without write access on field operations sees the chart without being
  able to move the bars: the rights travel in the arch, from the server
* the planning gestures of ``soft_gantt`` are enabled on the view: a team row
  sums its planned work (``group_total``), a double click on an empty cell or
  the "+" of a team row creates an operation with the dates or the team
  defaulted (``cell_create``), and the cancelled/draft states are flagged with
  decoration rings on top of the status colour (``decoration-*``)
""",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "license": "AGPL-3",
    "depends": [
        "field_operation",
        "soft_gantt",
    ],
    "data": [
        "views/field_operation_gantt_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "uninstall_hook": "uninstall_hook",
}
