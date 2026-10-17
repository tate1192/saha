# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.
"""One-off backfill: point existing services at the sale order line they came from.

``field.operation.sale_line_id`` is only written when a service is born from a sale
order line. Services created before that field existed have no line, so this script
matches them back by line name or line subtotal — and only accepts the match when it
is unambiguous (exactly one candidate line in the order).

Dry run by default: it reports what it would do. Set ``APPLY = True`` below to write.

Usage (Odoo 19, free HTTP port, own log file):

    odoo-bin shell -c <conf> -d <db> --http-port <free> --logfile <log> \
        < field_operation_sale/scripts/backfill_sale_line_id.py
"""

import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)

APPLY = False


def backfill_sale_line_id(env, apply=False):
    """Match services without ``sale_line_id`` back to their order line, if unique."""
    services = env["field.operation"].search(
        [("sale_id", "!=", False), ("sale_line_id", "=", False)]
    )
    by_order = defaultdict(lambda: env["field.operation"])
    for service in services:
        by_order[service.sale_id.id] |= service

    matched = ambiguous = unmatched = 0
    for order in env["sale.order"].browse(list(by_order)):
        lines = order.order_line.filtered("product_id")
        for service in by_order[order.id]:
            candidates = lines.filtered(
                lambda line, service=service: (
                    (line.name or "") == (service.subject or "")
                    or abs(
                        (line.price_subtotal or 0.0) - (service.service_price or 0.0)
                    )
                    < 0.01
                )
            )
            if len(candidates) == 1:
                matched += 1
                if apply:
                    service.sale_line_id = candidates.id
            elif len(candidates) > 1:
                ambiguous += 1
            else:
                unmatched += 1

    report = (
        f"BACKFILL REPORT: scanned={len(services)} matched={matched} "
        f"ambiguous={ambiguous} unmatched={unmatched} apply={apply}"
    )
    _logger.info(report)
    print(report)
    if apply:
        env.cr.commit()
        print("BACKFILL: committed")


backfill_sale_line_id(env, APPLY)  # noqa: F821 — `env` is injected by odoo-bin shell
