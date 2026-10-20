"""Keep existing teams on the company start after the home/company choice.

The field defaults to ``home`` for teams created after this version. An
existing installation must not switch every route to a home address nobody has
configured (and must not warn on every plan), so its teams keep the company
start until the office explicitly picks home.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Archived teams keep their history and may be restored: they get the same
    # backward-compatible start as the active ones.
    teams = (
        env["field.operation.team"]
        .with_context(active_test=False)
        .search([("route_start_mode", "=", "home")])
    )
    if teams:
        teams.write({"route_start_mode": "company"})
