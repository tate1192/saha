"""The team members autocomplete must not quick-create employees from text."""

from ast import literal_eval

from lxml import etree

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTeamMembersQuickCreate(TransactionCase):
    """``team_members_ids`` disables quick create, keeps "Create and edit...".

    The avatar tags autocomplete carries two creation paths: the quick
    ``Create "<name>"`` item (``hr.employee.name_create``) and
    ``Create and edit...`` which opens the full employee form. The field
    operations team screen keeps the second and disables the first, so a
    bare employee record cannot be born from one typed name.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Team = cls.env["field.operation.team"]

    def _members_field_options(self, view_type):
        arch = self.Team.get_view(False, view_type)["arch"]
        root = etree.fromstring(arch)
        nodes = root.xpath("//field[@name='team_members_ids']")
        self.assertEqual(
            len(nodes),
            1,
            f"expected one team_members_ids field in the {view_type} view",
        )
        return literal_eval(nodes[0].get("options"))

    def test_form_disables_quick_create_and_keeps_create_and_edit(self):
        """The form keeps the full employee form path but not the typed one."""
        options = self._members_field_options("form")
        self.assertIs(options.get("no_quick_create"), True)
        self.assertNotIn("no_create", options)
        self.assertEqual(options.get("color_field"), "color")

    def test_list_disables_quick_create_and_keeps_create_and_edit(self):
        """The list embed carries the same options as the form."""
        options = self._members_field_options("list")
        self.assertIs(options.get("no_quick_create"), True)
        self.assertNotIn("no_create", options)
        self.assertEqual(options.get("color_field"), "color")
