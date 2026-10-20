from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from . import geo_helpers


class MapsWebsite(models.Model):
    _name = "maps.website"
    _description = "Map Website"
    _order = "sequence, id"

    name = fields.Char(string="Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    sequence = fields.Integer(string="Sequence", default=10)
    website_url = fields.Char(string="Provider Website")
    requires_api_key = fields.Boolean(string="Requires API Key")
    api_key = fields.Char(
        string="API Key",
        help="Provider API Key; masked in the form (the 'password' attribute of "
        "the view field - Odoo 19 no longer takes it as a field parameter).",
    )
    lat_lon_url = fields.Char(string="Latitude/Longitude URL", required=True)
    route_lat_lon_url = fields.Char(string="Route Latitude/Longitude URL")
    provider_type = fields.Selection(
        [
            ("google", "Google Maps"),
            ("openstreetmap", "OpenStreetMap"),
            ("bing", "Bing Maps"),
            ("here", "Here Maps"),
            ("mapbox", "Mapbox"),
            ("other", "Other"),
        ],
        string="Provider Type",
        default="other",
    )

    @api.constrains("lat_lon_url", "route_lat_lon_url")
    def _check_url_placeholders(self):
        """Check that the configured URLs carry the expected placeholders."""
        for record in self:
            if record.lat_lon_url and (
                "{LATITUDE}" not in record.lat_lon_url
                or "{LONGITUDE}" not in record.lat_lon_url
            ):
                raise ValidationError(
                    _("Lat/Lon URL must contain {LATITUDE} and {LONGITUDE}")
                )

            if record.route_lat_lon_url:
                required = [
                    "{START_LATITUDE}",
                    "{START_LONGITUDE}",
                    "{DEST_LATITUDE}",
                    "{DEST_LONGITUDE}",
                ]
                if not all(
                    placeholder in record.route_lat_lon_url for placeholder in required
                ):
                    raise ValidationError(
                        _("Route Lat/Lon URL must contain required placeholders")
                    )

    @api.depends("name", "active")
    def _compute_display_name(self):
        for record in self:
            name = record.name
            if not record.active:
                name = f"{name} (Inactive)"
            record.display_name = name

    def _resolve_api_key(self, url):
        """Fill or strip the ``{API_KEY}`` slot of a provider URL template."""
        if self.requires_api_key and self.api_key:
            return url.replace("{API_KEY}", self.api_key)
        return url.replace("&key={API_KEY}", "").replace("?key={API_KEY}", "")

    def _get_osm_multi_url(self, coordinates: list[tuple[float, float, str]]) -> str:
        """Generate OpenStreetMap multi-marker URL using GraphHopper."""
        self.ensure_one()
        if not coordinates:
            return False

        params = [f"point={lat},{lon}" for lat, lon, name in coordinates]
        params.append("layer=Omniscale")
        return "https://graphhopper.com/maps/?" + "&".join(params)

    def _get_google_multi_url(self, coordinates: list[tuple[float, float, str]]) -> str:
        """Generate Google Maps multi-marker URL."""
        self.ensure_one()
        if not coordinates:
            return False

        # The directions format is used as a fallback for multiple points.
        parts = [f"{lat},{lon}" for lat, lon, name in coordinates]
        return "https://www.google.com/maps/dir/" + "/".join(parts)

    def _get_lat_lon_url(self, latitude: float, longitude: float) -> str:
        """Generate the single-point URL, with the API key slot resolved.

        Follows the convention of the other builders here: return ``False`` when
        this provider has no single-point URL, and let the caller report it.
        """
        self.ensure_one()
        if not self.lat_lon_url:
            return False
        url = self.lat_lon_url.replace("{LATITUDE}", str(latitude))
        url = url.replace("{LONGITUDE}", str(longitude))
        # The template carries a {API_KEY} slot only for the providers that need
        # one; strip it otherwise so it never reaches the browser.
        return self._resolve_api_key(url)

    def _get_multi_location_marker_url(
        self, coordinates: list[tuple[float, float, str]]
    ) -> str:
        """Generate multi-marker URL based on provider type."""
        self.ensure_one()
        if self.provider_type == "openstreetmap":
            return self._get_osm_multi_url(coordinates)
        if self.provider_type == "google":
            return self._get_google_multi_url(coordinates)
        if self.provider_type == "bing":
            # Bing format: pos.lat_lon~pos.lat_lon
            points = [f"pos.{lat}_{lon}" for lat, lon, name in coordinates]
            return (
                f"https://www.bing.com/maps?rtp={'~'.join(points)}" if points else False
            )
        if self.provider_type == "here":
            points = [f"{lat},{lon}" for lat, lon, name in coordinates]
            return (
                "https://www.here.com/search/" + "/".join(points) if points else False
            )
        return self._get_osm_multi_url(coordinates)

    def _parse_waypoints(self, waypoints):
        """Turn ``"lat,lon"`` strings into points, dropping unusable ones."""
        points = []
        for waypoint in waypoints or []:
            try:
                latitude, longitude = (float(part) for part in str(waypoint).split(","))
            except (TypeError, ValueError):
                continue
            if geo_helpers.has_point(latitude, longitude):
                points.append((latitude, longitude))
        return points

    def _get_route_url(
        self, start_coords: dict[str, float], waypoints: list[str]
    ) -> str:
        """Generate a route URL through the start point and the waypoints.

        ``waypoints`` are ``"lat,lon"`` strings and carry the destination as
        their last element (the caller appends it). Points without usable
        coordinates are skipped instead of failing the whole route: one
        unlocated stop must not hide the rest of the day.
        """
        self.ensure_one()
        if not start_coords or not waypoints:
            return False

        points = []
        start_lat = start_coords.get("latitude")
        start_lon = start_coords.get("longitude")
        # A latitude of 0.0 is the equator, not a missing value; the shared
        # rule lives in geo_helpers.has_point.
        if geo_helpers.has_point(start_lat, start_lon):
            points.append((start_lat, start_lon))
        points.extend(self._parse_waypoints(waypoints))
        if len(points) < 2:
            return False
        return self._get_route_url_for_points(points)

    def _get_route_url_for_points(self, points) -> str:
        """Route URL for an ordered list of ``(lat, lon)`` points."""
        self.ensure_one()
        if len(points) < 2:
            return False

        if self.provider_type == "openstreetmap":
            params = [f"point={lat},{lon}" for lat, lon in points]
            params.append("vehicle=car")
            return "https://graphhopper.com/maps/?" + "&".join(params)

        if self.provider_type == "google":
            parts = [f"{lat},{lon}" for lat, lon in points]
            return "https://www.google.com/maps/dir/" + "/".join(parts)

        if self.provider_type == "bing":
            rtp_parts = [f"pos.{lat}_{lon}" for lat, lon in points]
            return "https://www.bing.com/maps/directions?rtp=" + "~".join(rtp_parts)

        if self.provider_type == "mapbox":
            # The Mapbox web directions URL takes multiple points separated by
            # "~", so the whole day survives instead of only start and end.
            parts = [f"{lat},{lon}" for lat, lon in points]
            return "https://mapbox.com/maps/?rtext=" + "~".join(parts) + "&rtt=auto"

        # Any other provider is described by its own route template. The
        # template only knows start and destination, which is the limit of
        # those providers' web URLs; the URL no longer silently disappears
        # while the configured template is validated and shown in the form.
        first, last = points[0], points[-1]
        if len(points) > 2 and first == last:
            # A round trip (home -> stops -> home): the template cannot draw
            # the return leg, and the repeated point would turn the URL into
            # origin == destination. Keep the last customer as the destination
            # so the day is still visible.
            last = points[-2]
        return self._get_template_route_url(first, last)

    def _get_template_route_url(self, first, last) -> str:
        """Fill the provider's own route template with start and destination."""
        self.ensure_one()
        if not self.route_lat_lon_url:
            return False
        url = self.route_lat_lon_url.replace("{START_LATITUDE}", str(first[0]))
        url = url.replace("{START_LONGITUDE}", str(first[1]))
        url = url.replace("{DEST_LATITUDE}", str(last[0]))
        url = url.replace("{DEST_LONGITUDE}", str(last[1]))
        return self._resolve_api_key(url)
