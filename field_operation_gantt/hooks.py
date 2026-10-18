# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).


def uninstall_hook(env):
    """Remove the ``gantt_soft`` mode from the action this module extended.

    ``view_mode`` is a comma separated Char: nothing removes a mode when the
    module that added it disappears, so the action would keep advertising a
    view mode no view type can answer any more. The action is targeted by its
    xml id rather than searched globally, so the same mode on another action
    is left alone.
    """
    action = env.ref("field_operation.action_field_operation", raise_if_not_found=False)
    if not action:
        return
    modes = [
        mode
        for mode in (action.view_mode or "").split(",")
        if mode and mode != "gantt_soft"
    ]
    action.view_mode = ",".join(modes)
