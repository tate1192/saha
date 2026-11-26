from odoo import fields, models


class Company(models.Model):
    _inherit = "res.company"

    biocidal_certificate = fields.Char(string="Biocidal Certificate")
    responsible_manager = fields.Char(string="Responsible Manager")
