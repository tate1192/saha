"""GPS position samples recorded for a field operation team.

Rows are appended by the GPS tracking controller and would grow without bound
(roughly a few hundred rows per active team per day), so a daily cron deletes
the rows older than the configured retention window. The window is a system
parameter, which lets a deployment keep one or two months without a code
change.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

#: System parameter with the number of days of history to keep.
RETENTION_PARAM = "field_operation_geolocation.location_history_retention_days"
DEFAULT_RETENTION_DAYS = 60


class TeamLocationHistory(models.Model):
    """One GPS position sample recorded for a field operation team."""

    _name = "team.location.history"
    _description = "GPS Location History"
    _order = "timestamp desc"

    team_id = fields.Many2one(
        "field.operation.team", required=True, ondelete="cascade", index=True
    )
    latitude = fields.Float(digits=(10, 7), required=True)
    longitude = fields.Float(digits=(10, 7), required=True)
    accuracy = fields.Float()
    timestamp = fields.Datetime(default=fields.Datetime.now, index=True)
    battery_level = fields.Integer()

    @api.model
    def _cron_cleanup(self, days=None):
        """Delete history rows older than the retention window.

        ``days`` is exposed for tests and for a manual run from the shell; the
        cron calls the method without arguments and reads the system parameter
        (``field_operation_geolocation.location_history_retention_days``,
        default 60 days).

        The cutoff uses ``timestamp`` - the sample's own time and the indexed
        column - so a device with a badly set clock is cleaned up instead of
        keeping a row forever.
        """
        if days is None:
            raw_days = (
                self.env["ir.config_parameter"]
                .sudo()
                .get_param(RETENTION_PARAM, DEFAULT_RETENTION_DAYS)
            )
            try:
                days = int(raw_days)
            except (TypeError, ValueError):
                _logger.warning(
                    "Invalid %s value %r, using %s days",
                    RETENTION_PARAM,
                    raw_days,
                    DEFAULT_RETENTION_DAYS,
                )
                days = DEFAULT_RETENTION_DAYS
        days = max(1, days)
        cutoff = fields.Datetime.now() - timedelta(days=days)
        records = self.search([("timestamp", "<", cutoff)])
        count = len(records)
        if records:
            records.unlink()
        _logger.info(
            "GPS history cleanup: removed %s row(s) older than %s day(s)",
            count,
            days,
        )
        return count
