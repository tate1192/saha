# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    active_ingredient = fields.Char(string="Active Ingredient")
    package = fields.Char(string="Package")
    antidote = fields.Char(string="Antidote")
    vendor = fields.Char(string="Vendor")
