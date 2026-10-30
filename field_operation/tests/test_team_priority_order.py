"""The team list reads the flagged teams first, like Odoo's product lists."""

from lxml import etree

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTeamListOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Team = cls.env["field.operation.team"]
        arch = cls.Team.get_view(False, "list")["arch"]
        cls.list_root = etree.fromstring(arch)

    def test_the_team_list_puts_priority_first(self):
        """A team flagged High/Emergency is listed above the others.

        The list carries a ``sequence`` handle, so the order has to say what
        happens to it: priority first, then the manual sequence, then the id.
        Without a ``default_order`` the list followed the model's own order
        (``id``), which is why the flagged teams of the live database sat
        wherever they had been created.
        """
        self.assertEqual(
            self.list_root.get("default_order"), "priority desc, sequence, id"
        )

    def test_that_order_reads_the_flagged_team_first(self):
        """The declared order is not just a string: it is what the read does."""
        low = self.Team.create({"name": "Low team", "priority": "0", "sequence": 10})
        high = self.Team.create(
            {"name": "Emergency team", "priority": "2", "sequence": 10}
        )
        teams = self.Team.search(
            [("id", "in", (low | high).ids)],
            order=self.list_root.get("default_order"),
        )
        self.assertEqual(teams[0], high)
