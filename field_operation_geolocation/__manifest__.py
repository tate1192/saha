{
    "name": "Field Operation Geolocation",
    "version": "19.0.1.6.1",
    "category": "Services/Field Service",
    "summary": "Adds geolocation functionality to the field operation module",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "field_operation",
        # hr.employee is queried directly (controllers/gps_tracking.py and the
        # geolocation flow that maps a user to their team), so declare 'hr'
        # explicitly instead of relying on it transitively via field_operation.
        "hr",
        # Address -> coordinate conversion uses partner.geo_localize() and the
        # core geocoding flow, which are provided by 'base_geolocalize'.
        "base_geolocalize",
        # The route planner warns the dispatcher through user._bus_send(), which
        # bus adds to res.users (installed transitively through mail today, but
        # the dependency is real and therefore declared).
        "bus",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/maps_website_data.xml",
        "data/geo_company_cron.xml",
        "data/team_location_history_cron.xml",
        "data/actions_geolocation.xml",
        "views/field_operation_view.xml",
        "views/maps_website_view.xml",
        "views/res_users_view.xml",
        "views/team_location_history_view.xml",
        "views/hr_employee_view.xml",
        "views/field_operation_team_view.xml",
        "views/field_operation_route_plan_view.xml",
    ],
    "demo": [],
    "assets": {
        "web.assets_backend": [
            "field_operation_geolocation/static/src/js/gps_tracking.js",
        ],
    },
    "external_dependencies": {},
    "post_init_hook": "set_default_map_settings",
    "installable": True,
    "auto_install": False,
    "application": False,
}
