{
    "name": "Field Operation Route Board",
    "version": "19.0.1.0.0",
    "category": "Services/Field Service",
    "summary": "Dispatcher map board with the whole day's routes, one colour per team",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "license": "AGPL-3",
    "sequence": 121,
    "depends": [
        "field_operation_geolocation",
        "soft_web_map",
    ],
    "data": [
        "views/day_board_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "field_operation_geolocation_board/static/src/xml/day_board.xml",
            "field_operation_geolocation_board/static/src/js/day_board_helpers.js",
            "field_operation_geolocation_board/static/src/js/day_board_map.js",
            "field_operation_geolocation_board/static/src/js/day_board_action.js",
            "field_operation_geolocation_board/static/src/scss/day_board.scss",
        ],
        # Loaded by Odoo only when the user's color scheme is dark
        # (web/views/webclient_templates.xml: color_scheme == 'dark').
        "web.assets_web_dark": [
            "field_operation_geolocation_board/static/src/scss/day_board.dark.scss",
        ],
    },
    "auto_install": False,
    "installable": True,
    "application": False,
}
