"""Home address on the public employee profile.

``hr.employee.fetch()`` refuses to read a field that is not declared on
``hr.employee.public``: the moment a user without HR rights reads an employee
field (opening the employee card from the team form, a list export, a saved
filter), Odoo switches to the public profile and raises

    The fields "home_location_id", which you are trying to read, are not
    available for employee public profiles.

The field is therefore mirrored on the public model as a non-stored related
field: the read succeeds, the value stays the employee's own record and no
column is duplicated.
"""

from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    home_location_id = fields.Many2one(
        "res.partner",
        string="Home Address",
        related="employee_id.home_location_id",
        readonly=True,
        help="Mirror of the employee's home address, so a user without HR "
        "rights can read the team's start address without an access error.",
    )
