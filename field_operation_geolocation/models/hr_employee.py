"""Home address of a field employee.

The daily route can start and end at the employee's home instead of the
company: a crew that takes the van home leaves from there in the morning and
returns there in the evening. The address is a regular ``res.partner`` so the
coordinates (and the core geolocation button) work exactly as they do for a
customer address.
"""

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    home_location_id = fields.Many2one(
        "res.partner",
        string="Home Address",
        domain=[("is_company", "=", False)],
        help="Address where this employee's working day starts and ends when "
        "the route starts from home. The route planner uses its coordinates "
        "as the first and the last point of the day.",
    )
