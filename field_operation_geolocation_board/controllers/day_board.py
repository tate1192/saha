"""JSON endpoints for the dispatcher map board.

The heavy lifting lives on ``field.operation.team`` so the payload can be tested
with a TransactionCase; the controller only parses the request and keeps the
server side thin.
"""

from odoo import http
from odoo.http import request


class FieldOperationBoardController(http.Controller):
    @http.route(
        "/field_operation_geolocation_board/day_board",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def day_board(self, date=None, team_ids=None):
        """The whole day: teams, ordered stops, geometry and live positions."""
        return request.env["field.operation.team"]._day_board_data(
            date, team_ids=team_ids
        )

    @http.route(
        "/field_operation_geolocation_board/live",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def live(self, team_ids=None):
        """Only the live positions, for the periodic refresh of the board."""
        return request.env["field.operation.team"]._live_positions(team_ids=team_ids)
