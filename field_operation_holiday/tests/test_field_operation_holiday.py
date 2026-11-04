"""Tests for the time off integration of the field operations.

Pins the behaviour a planner relies on: an approved leave puts one operation per
leave day on the board, and it disappears again when the leave is cancelled or
deleted - without disabling the leave check of ``field.operation`` itself.
"""

from datetime import date

import pytz

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("field_operation_holiday", "post_install", "-at_install")
class TestFieldOperationHoliday(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operations = cls.env["field.operation"]
        cls.leaves = cls.env["hr.leave"]
        # A real timezone on purpose: with the UTC calendar of the test database the
        # day split would look right even when it cuts at UTC midnight.
        cls.calendar = cls.env["resource.calendar"].create(
            {
                "name": "Istanbul 40h",
                "tz": "Europe/Istanbul",
                "company_id": cls.env.company.id,
                "attendance_ids": [
                    (
                        0,
                        0,
                        {
                            "name": label,
                            "dayofweek": str(day),
                            "hour_from": hour_from,
                            "hour_to": hour_to,
                        },
                    )
                    for day in range(5)
                    for label, hour_from, hour_to in (
                        ("Morning", 8, 12),
                        ("Afternoon", 13, 17),
                    )
                ],
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Leave Marker Employee",
                "resource_calendar_id": cls.calendar.id,
            }
        )
        # Own type on purpose: the type found in a given database may be a half-day
        # one ("Unpaid leave" in a fresh database), which silently shortens a
        # 3-day request to 2 days and hides day-split regressions.
        cls.leave_type = cls.env["hr.leave.type"].create(
            {
                "name": "Leave Marker Test",
                "requires_allocation": False,
                "leave_validation_type": "no_validation",
                "request_unit": "day",
            }
        )

    def _leave(self, date_from=date(2026, 11, 10), date_to=date(2026, 11, 12)):
        leave = self.leaves.create(
            {
                "employee_id": self.employee.id,
                "holiday_status_id": self.leave_type.id,
                "request_date_from": date_from,
                "request_date_to": date_to,
            }
        )
        if leave.state != "validate":
            leave.write({"state": "validate"})
        return leave

    def test_01_approved_leave_creates_one_operation_per_day(self):
        leave = self._leave()
        self.assertEqual(leave.state, "validate")

        operations = leave.operation_ids
        self.assertEqual(len(operations), 3, "one operation per leave day")
        for operation in operations:
            self.assertEqual(operation.person_ids, self.employee)
            self.assertEqual(operation.leave_id, leave)
            self.assertEqual(operation.status, "planned")
            self.assertTrue(operation.is_leave_marker)
            self.assertIn(self.employee.name, operation.subject)
            self.assertIn(self.leave_type.name, operation.subject)

        # The split follows the leave timezone: no operation may cross a local
        # midnight, and the first/last one carry the leave's own local edges.
        tz = pytz.timezone(leave.tz)
        self.assertEqual(tz.zone, "Europe/Istanbul")
        operations = operations.sorted("start_date")
        days = [
            self._local(operation.start_date, tz).date() for operation in operations
        ]
        self.assertEqual(
            days, [date(2026, 11, 10), date(2026, 11, 11), date(2026, 11, 12)]
        )
        self.assertEqual(
            self._local(operations[0].start_date, tz),
            self._local(leave.date_from, tz),
            "the first operation must start when the leave starts (local time)",
        )
        self.assertEqual(
            self._local(operations[-1].end_date, tz),
            self._local(leave.date_to, tz),
            "the last operation must end when the leave ends (local time)",
        )
        for operation in operations:
            self.assertEqual(
                self._local(operation.start_date, tz).date(),
                self._local(operation.end_date, tz).date(),
                "an operation must stay inside one local day",
            )

    @staticmethod
    def _local(moment, tz):
        return pytz.utc.localize(moment).astimezone(tz)

    def test_02_changing_the_dates_rebuilds_the_operations(self):
        """An approved leave is amended by resetting it and approving again."""
        leave = self._leave(date_from=date(2026, 11, 10), date_to=date(2026, 11, 11))
        self.assertEqual(len(leave.operation_ids), 2)

        leave.write({"state": "confirm"})
        self.assertFalse(leave.operation_ids, "a leave back in approval is not planned")

        leave.write(
            {
                "request_date_from": date(2026, 11, 10),
                "request_date_to": date(2026, 11, 13),
            }
        )
        leave.write({"state": "validate"})

        self.assertEqual(len(leave.operation_ids), 4, "the operations are rebuilt")
        tz = pytz.timezone(leave.tz)
        self.assertEqual(
            sorted(
                self._local(operation.start_date, tz).date()
                for operation in leave.operation_ids
            ),
            [
                date(2026, 11, 10),
                date(2026, 11, 11),
                date(2026, 11, 12),
                date(2026, 11, 13),
            ],
        )

    def test_03_cancelled_leave_removes_its_operations(self):
        leave = self._leave()
        self.assertTrue(leave.operation_ids)

        leave.write({"state": "cancel"})
        self.assertFalse(leave.operation_ids)

    def test_04_deleted_leave_takes_its_operations_with_it(self):
        leave = self._leave()
        operation_ids = leave.operation_ids.ids
        leave.unlink()
        self.assertFalse(self.operations.browse(operation_ids).exists())

    def test_05_real_service_during_a_leave_is_still_refused(self):
        """The generator must not disarm the leave check of field.operation."""
        leave = self._leave(date_from=date(2026, 11, 10), date_to=date(2026, 11, 10))
        self.assertTrue(leave.operation_ids)

        with self.assertRaises(ValidationError) as error:
            self.operations.create(
                {
                    "subject": "Real service",
                    "person_ids": [(6, 0, self.employee.ids)],
                    "start_date": "2026-11-10 08:00:00",
                    "end_date": "2026-11-10 10:00:00",
                    "status": "planned",
                }
            )
        self.assertIn(self.employee.name, str(error.exception))

    def test_06_markers_carry_the_leave_service_type(self):
        leave = self._leave()
        service_type = self.env.ref("field_operation_holiday.operation_type_leave")
        self.assertEqual(leave.operation_ids.service_type_id, service_type)
        self.assertEqual(service_type.type, "leave")

    def test_07_sync_does_not_need_operation_rights(self):
        """The generator runs as sudo: HR needs no field.operation ACL at all.

        The leave is read and rewritten by a Time Off officer who only has the
        read-only field worker group on the operations; a delete/rebuild of the
        markers must still go through.
        """
        officer = self.env["res.users"].create(
            {
                "name": "Time Off Officer",
                "login": "time_off_officer_without_operation_rights",
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("hr_holidays.group_hr_holidays_user").id,
                            self.env.ref("field_operation.service_group_worker").id,
                        ]
                    )
                ],
            }
        )
        self.assertFalse(
            self.env["field.operation"].with_user(officer).has_access("unlink"),
            "the test user must not be allowed to unlink operations",
        )

        leave = self._leave()
        self.assertEqual(len(leave.operation_ids), 3)

        leave.with_user(officer)._sync_leave_operations()

        self.assertEqual(len(leave.operation_ids), 3)
