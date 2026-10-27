# field_operation/models/base_partner_merge.py

from odoo import models


class BasePartnerMergeAutomaticWizard(models.TransientModel):
    _inherit = "base.partner.merge.automatic.wizard"

    def _merge(self, partner_ids, dst_partner=None, extra_checks=True):
        """Recompute the service counter after a contact merge.

        The merge wizard rewrites every partner foreign key with plain SQL
        (``_update_foreign_keys``), so the ORM never sees the change: stored
        counters such as ``field_operation_count`` keep their pre-merge value
        and the contact form keeps showing the old number of services. The
        services themselves are moved correctly; only the counter is stale.
        """
        Partner = self.env["res.partner"].with_context(active_test=False)

        # res.partner has no parent_store in v19: walk parent_id by hand.
        ancestor_ids = set()
        for partner in Partner.browse(partner_ids).exists():
            node, seen = partner.parent_id, set()
            while node and node.id not in seen:
                seen.add(node.id)
                ancestor_ids.add(node.id)
                node = node.parent_id

        res = super()._merge(partner_ids, dst_partner, extra_checks=extra_checks)

        # Sources are deleted by now; the destination is what survives. Every
        # ancestor seen before the merge is recomputed: the destination parents
        # gained a service, the former parents of the sources lost one.
        to_compute = (
            Partner.browse(partner_ids).exists()
            | Partner.browse(sorted(ancestor_ids)).exists()
        )
        if to_compute:
            # Recompute in the default context: ``Partner`` above carries
            # active_test=False (needed to reach archived parents), and the
            # counter must count what the smart button counts — active
            # services only.
            to_compute = self.env["res.partner"].browse(to_compute.ids)
            to_compute.invalidate_recordset(["field_operation_count"])
            to_compute._compute_field_operation_count()
        return res
