"""Regression tests for the field_operation_worker view-only module.

The module ships no model: it layers worker-specific views, an action and a
menu on top of ``field.operation``. The tests below pin the behaviour that was
either broken or unverified:

* installation used to abort with a ``ParseError`` because the form view kept
  commented-out ``<button>`` nodes (``action_planned`` / ``action_cancel`` /
  ``action_draft``) inside its ``<header>``: the view validator walks commented
  nodes in v19, so dead XML now fails the module install. Every worker view is
  checked to be free of ``<!--`` nodes.
* the four views reused the exact base names (``field.operation.form`` ...),
  which makes them indistinguishable from the core module views; they must now
  carry the ``.worker`` suffix.
* the action, its ``ir.actions.act_window.view`` links, the menu groups and the
  ``my_jobs`` filter were never asserted.
* the ``my_jobs`` default filter is a search filter, not a security boundary:
  the actual visibility comes from the base record rules. Reading covers the
  worker's own jobs in every non-draft status (``rule_service_worker``), while
  writing stops at the open part of the flow (``rule_service_worker_write``).
"""

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFieldOperationWorker(TransactionCase):
    """Checks the worker view set, its action/menu wiring and the record rule."""

    WORKER_VIEW_XMLIDS = {
        "filter": "field_operation_worker.view_field_operation_worker_filter",
        "list": "field_operation_worker.view_field_operation_worker_list",
        "form": "field_operation_worker.view_field_operation_worker_form",
        "kanban": "field_operation_worker.view_field_operation_worker_kanban",
    }
    # Names owned by the core module: the worker views must not reuse them.
    BASE_VIEW_NAMES = {
        "field.operation.select",
        "field.operation.list",
        "field.operation.form",
        "field.operation.kanban",
    }
    WORKER_VIEW_NAMES = {
        "field.operation.select.worker",
        "field.operation.list.worker",
        "field.operation.form.worker",
        "field.operation.kanban.worker",
    }

    def test_01_worker_views_ship_no_commented_nodes(self):
        """P0 regression: no worker view may contain a commented XML node.

        The form view used to carry ``<!-- <button .../> -->`` blocks. In Odoo
        19 the view validator still reads commented nodes, so the module could
        not be installed at all (``ParseError`` while parsing the view). Each
        xml:id must resolve and its stored arch must be comment-free.

        The same view used to call ``action_send_mail`` on its ``Email``
        button, a method that does not exist on ``field.operation`` (the real
        one is ``action_send_report_mail``): a second install-blocking
        ``ParseError``. Every object button of the form is therefore checked to
        target an existing method.
        """
        for label, xmlid in self.WORKER_VIEW_XMLIDS.items():
            view = self.env.ref(xmlid)
            self.assertTrue(view, f"{label} view {xmlid} does not resolve")
            for raw in (view.arch_db, view.arch):
                self.assertNotIn(
                    "<!--",
                    raw or "",
                    f"{label} view {xmlid} still ships a commented XML node",
                )

        form_arch = etree.fromstring(self.env.ref(self.WORKER_VIEW_XMLIDS["form"]).arch)
        model = self.env["field.operation"]
        for button in form_arch.iter("button"):
            if button.get("type") == "object":
                method = button.get("name")
                self.assertTrue(
                    callable(getattr(model, method, None)),
                    f"form button calls unknown method {method!r} on field.operation",
                )

    def test_02_view_names_are_worker_specific(self):
        """The four views must be named ``field.operation.*.worker``."""
        for label, xmlid in self.WORKER_VIEW_XMLIDS.items():
            view = self.env.ref(xmlid)
            self.assertIn(
                view.name,
                self.WORKER_VIEW_NAMES,
                f"{label} view name {view.name!r} is not worker specific",
            )
            self.assertNotIn(
                view.name,
                self.BASE_VIEW_NAMES,
                f"{label} view reused the base view name {view.name!r}",
            )

        # The core module may still own the bare names, but none of our records.
        our_ids = {self.env.ref(xmlid).id for xmlid in self.WORKER_VIEW_XMLIDS.values()}
        for base_name in self.BASE_VIEW_NAMES:
            found = self.env["ir.ui.view"].search(
                [("model", "=", "field.operation"), ("name", "=", base_name)]
            )
            self.assertFalse(
                our_ids & set(found.ids),
                f"a worker view still answers to the base name {base_name!r}",
            )

    def test_03_action_is_wired_to_worker_views(self):
        """The action exposes the three modes and the worker search view."""
        action = self.env.ref("field_operation_worker.action_field_operation_worker")
        self.assertEqual(action.res_model, "field.operation")
        modes = action.view_mode.split(",")
        for mode in ("list", "kanban", "form"):
            self.assertIn(mode, modes, f"{mode} missing from action view_mode")
        self.assertEqual(
            action.search_view_id,
            self.env.ref("field_operation_worker.view_field_operation_worker_filter"),
        )
        self.assertIn("search_default_my_jobs", action.context or "")

        links = self.env["ir.actions.act_window.view"].search(
            [("act_window_id", "=", action.id)]
        )
        self.assertEqual(len(links), 3)
        by_mode = {link.view_mode: link for link in links}
        self.assertEqual(
            by_mode["list"].view_id,
            self.env.ref("field_operation_worker.view_field_operation_worker_list"),
        )
        self.assertEqual(
            by_mode["kanban"].view_id,
            self.env.ref("field_operation_worker.view_field_operation_worker_kanban"),
        )
        self.assertEqual(
            by_mode["form"].view_id,
            self.env.ref("field_operation_worker.view_field_operation_worker_form"),
        )

    def test_04_menu_is_restricted_to_workers(self):
        """The menu lives under the base root and only workers may see it."""
        menu = self.env.ref("field_operation_worker.menu_field_operation_worker")
        self.assertEqual(
            menu.parent_id, self.env.ref("field_operation.menu_field_operation_root")
        )
        self.assertIn(
            self.env.ref("field_operation.service_group_worker"),
            menu.group_ids,
        )

    def test_05_worker_only_sees_assigned_jobs(self):
        """A worker reads their own jobs in every non-draft status.

        Visibility is enforced by the base record rule ``rule_service_worker``
        (``person_ids.user_id = user.id`` and the job is not a draft). Closed
        jobs stay readable (mobile history); drafts and foreign jobs stay hidden.
        """
        worker_group = self.env.ref("field_operation.service_group_worker")
        worker_user = self.env["res.users"].create(
            {
                "name": "Worker Visibility",
                "login": "worker_visibility@example.com",
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, [self.env.company.id])],
            }
        )
        worker_user.group_ids = [(4, worker_group.id)]
        employee = self.env["hr.employee"].create(
            {"name": "Worker Employee", "user_id": worker_user.id}
        )

        assigned = self.env["field.operation"].create(
            {
                "subject": "Assigned to worker",
                "status": "progress",
                "person_ids": [(6, 0, employee.ids)],
            }
        )
        unassigned = self.env["field.operation"].create(
            {"subject": "Not assigned to worker", "status": "progress"}
        )
        # Assigned but not planned yet: still a draft, hidden from the worker.
        draft = self.env["field.operation"].create(
            {
                "subject": "Assigned but still a draft",
                "status": "draft",
                "person_ids": [(6, 0, employee.ids)],
            }
        )
        # Assigned and closed: readable for the history, but not writable.
        finished = self.env["field.operation"].create(
            {
                "subject": "Assigned and finished",
                "status": "done",
                "person_ids": [(6, 0, employee.ids)],
            }
        )

        visible = self.env["field.operation"].with_user(worker_user).search([])

        self.assertIn(assigned, visible)
        self.assertIn(finished, visible)
        self.assertNotIn(unassigned, visible)
        self.assertNotIn(draft, visible)
        # An explicit id search must not leak the hidden record either.
        self.assertFalse(
            self.env["field.operation"]
            .with_user(worker_user)
            .search([("id", "=", unassigned.id)])
        )

    def test_06_my_jobs_filter_targets_assigned_user(self):
        """The default filter must match the current user's assigned jobs."""
        arch = etree.fromstring(
            self.env.ref(
                "field_operation_worker.view_field_operation_worker_filter"
            ).arch
        )
        domains = {
            node.get("name"): node.get("domain")
            for node in arch.iter("filter")
            if node.get("name")
        }
        self.assertIn("my_jobs", domains)
        self.assertEqual(domains["my_jobs"], "[('person_ids.user_id','=',uid)]")

    def test_07_worker_writes_only_open_jobs(self):
        """Writing is limited to the open flow, even for the worker's own jobs."""
        worker_group = self.env.ref("field_operation.service_group_worker")
        worker_user = self.env["res.users"].create(
            {
                "name": "Worker Write Scope",
                "login": "worker_write_scope@example.com",
                "group_ids": [(6, 0, [worker_group.id])],
            }
        )
        employee = self.env["hr.employee"].create(
            {"name": "Worker Write Employee", "user_id": worker_user.id}
        )
        planned = self.env["field.operation"].create(
            {
                "subject": "Open job",
                "status": "planned",
                "person_ids": [(6, 0, employee.ids)],
            }
        )
        done = self.env["field.operation"].create(
            {
                "subject": "Closed job",
                "status": "done",
                "person_ids": [(6, 0, employee.ids)],
            }
        )

        planned.with_user(worker_user).write({"subject": "Worker note"})
        self.assertEqual(planned.subject, "Worker note")
        with self.assertRaises(AccessError):
            done.with_user(worker_user).write({"subject": "Too late"})
