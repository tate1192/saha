# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests import TransactionCase, tagged

from odoo.addons.field_operation_gantt.hooks import uninstall_hook


@tagged("post_install", "-at_install")
class TestFieldOperationGantt(TransactionCase):
    """What this module adds to ``field.operation``.

    The view type itself is tested by ``soft_gantt``: what is checked here is
    the wiring between the two, and the two figures the chart reads.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.action = cls.env.ref("field_operation.action_field_operation")
        cls.Operation = cls.env["field.operation"]

    def _operation(self, status):
        return self.Operation.create({"subject": "Gantt test", "status": status})

    def test_the_view_is_resolved_by_the_model(self):
        view = self.env.ref("field_operation_gantt.view_field_operation_gantt_soft")
        arch = self.env["field.operation"].get_view(view.id, "gantt_soft")["arch"]
        self.assertIn("gantt_soft", arch)

    def test_the_view_names_the_expected_fields(self):
        """The arch is refused at install on a typo; this pins the contract."""
        view = self.env.ref("field_operation_gantt.view_field_operation_gantt_soft")
        arch = self.env["field.operation"].get_view(view.id, "gantt_soft")["arch"]
        for expected in (
            'date_start="start_date"',
            'date_stop="end_date"',
            # The team is both the name of a row and the row's group: the bars
            # along the timeline are the team's services. The group produces
            # the row label, so no `label` attribute is needed.
            'group_by="team_id"',
            'progress="gantt_progress"',
            'color="gantt_color"',
            'default_range="month"',
        ):
            self.assertIn(expected, arch)

    def test_the_view_has_no_translatable_field_name(self):
        """A field name must not sit in the translatable ``label`` attribute.

        Odoo extracts ``label`` as a translation term. Writing a field name
        there puts it in the ``.pot``; translating it would turn the field
        name into a label and make the arch invalid in that language.
        """
        view = self.env.ref("field_operation_gantt.view_field_operation_gantt_soft")
        arch = self.env["field.operation"].get_view(view.id, "gantt_soft")["arch"]
        self.assertNotIn('label="team_id"', arch)

    def test_the_action_offers_the_gantt_mode(self):
        self.assertIn("gantt_soft", self.action.view_mode.split(","))

    def test_the_mode_is_added_without_dropping_the_others(self):
        """The mode is inserted, never written as a whole string.

        A data record listing ``view_mode`` would replace it, and this action is
        written by three modules: the last one to update would silently drop
        the others' modes (measured with ``field_operation_map``).
        """
        self.action.view_mode = "list,kanban,form,calendar,graph,pivot,activity"
        self.env["ir.actions.act_window"]._add_field_operation_gantt_view_mode()
        modes = self.action.view_mode.split(",")
        self.assertEqual(
            modes,
            [
                "list",
                "kanban",
                "form",
                "calendar",
                "gantt_soft",
                "graph",
                "pivot",
                "activity",
            ],
            "the core and sibling modes must survive, the Gantt after calendar",
        )

    def test_the_mode_is_restored_after_a_sibling_rewrote_the_string(self):
        """Whatever a sibling module left behind, the Gantt comes back."""
        self.action.view_mode = "kanban,list,form,activity,leaflet_map"
        self.env["ir.actions.act_window"]._add_field_operation_gantt_view_mode()
        modes = self.action.view_mode.split(",")
        self.assertIn("gantt_soft", modes)
        self.assertIn("leaflet_map", modes, "the sibling's mode must not be dropped")

    def test_the_mode_is_added_once(self):
        """The function runs on every update of this module: it must be idempotent."""
        self.env["ir.actions.act_window"]._add_field_operation_gantt_view_mode()
        once = self.action.view_mode
        self.env["ir.actions.act_window"]._add_field_operation_gantt_view_mode()
        self.assertEqual(self.action.view_mode, once)
        self.assertEqual(self.action.view_mode.count("gantt_soft"), 1)

    def test_the_landing_view_is_untouched(self):
        """Adding a mode must not change the view users land on."""
        self.assertEqual(self.action.views[0][1], "list")

    def test_the_progress_follows_the_status(self):
        expected = {
            "draft": 0.0,
            "planned": 25.0,
            "progress": 50.0,
            "done": 100.0,
            "cancel": 0.0,
        }
        for status, value in expected.items():
            self.assertEqual(self._operation(status).gantt_progress, value, status)

    def test_the_colour_follows_the_status(self):
        expected = {
            "draft": 2,
            "planned": 9,
            "progress": 10,
            "done": 8,
            "cancel": 11,
        }
        for status, index in expected.items():
            self.assertEqual(self._operation(status).gantt_color, index, status)

    def test_the_uninstall_hook_drops_the_mode(self):
        uninstall_hook(self.env)
        self.assertNotIn("gantt_soft", self.action.view_mode.split(","))
