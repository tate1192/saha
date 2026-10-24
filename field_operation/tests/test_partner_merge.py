"""Regression test: merging contacts must refresh the service counter.

The merge wizard rewrites every partner foreign key with plain SQL, so the ORM
never sees the services move and the stored ``field_operation_count`` keeps its
pre-merge value. The counter is recursive (``child_of``), so the company at the
top of the hierarchy is stale as well, not just the direct parent.
"""

from odoo.tests import TransactionCase, tagged


@tagged("field_operation", "post_install", "-at_install")
class TestPartnerMergeCounter(TransactionCase):
    def _service(self, partner):
        return self.env["field.operation"].create(
            {"subject": "Merged contact service", "partner_id": partner.id}
        )

    def test_merge_refreshes_every_ancestor(self):
        """company > branch > contact, with source and target in two branches."""
        company = self.env["res.partner"].create(
            {"name": "Merge Root Company", "is_company": True}
        )
        branch_source = self.env["res.partner"].create(
            {"name": "Merge Branch Source", "is_company": True, "parent_id": company.id}
        )
        branch_target = self.env["res.partner"].create(
            {"name": "Merge Branch Target", "is_company": True, "parent_id": company.id}
        )
        source = self.env["res.partner"].create(
            {"name": "Merge Source Contact", "parent_id": branch_source.id}
        )
        target = self.env["res.partner"].create(
            {"name": "Merge Target Contact", "parent_id": branch_target.id}
        )

        operation = self._service(source)
        self.assertEqual(source.field_operation_count, 1)
        self.assertEqual(branch_source.field_operation_count, 1)
        self.assertEqual(branch_target.field_operation_count, 0)
        self.assertEqual(company.field_operation_count, 1)

        wizard = self.env["base.partner.merge.automatic.wizard"].create({})
        wizard._merge([source.id, target.id], target)

        self.assertFalse(source.exists(), "the source contact is deleted by the merge")
        self.assertEqual(operation.partner_id, target, "the service moved to the target")
        self.assertEqual(
            target.field_operation_count,
            1,
            "the surviving contact must count the merged services",
        )
        self.assertEqual(
            branch_target.field_operation_count,
            1,
            "the destination parent counter is stale after the SQL merge",
        )
        self.assertEqual(
            branch_source.field_operation_count,
            0,
            "the former parent of the source lost the service and must be recomputed",
        )
        self.assertEqual(
            company.field_operation_count,
            1,
            "the grandparent counter is stale: recomputing only parent_id misses it",
        )

        # Every counter must match the domain the smart button uses.
        for partner in (target, branch_source, branch_target, company):
            self.assertEqual(
                partner.field_operation_count,
                self.env["field.operation"].search_count(
                    [("partner_id", "child_of", partner.id)]
                ),
                "counter and search disagree on %s" % partner.name,
            )
