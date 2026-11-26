# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import fields, models


class Company(models.Model):
    _inherit = "res.company"

    disinfection_certificate = fields.Char(string="Disinfection Certificate")
