import logging
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.field_operation_attendance.wizard import (
    attendance_report_wizard as wizard_module,
)

_logger = logging.getLogger(__name__)


# post_install: setUp() creates a company. Odoo 19 setups the model registry
# module by module while loading, and ``sale_stock`` (which adds the required
# res.company.security_lead field) is loaded long after this module. Running the
# tests at_install makes every company creation fail with a NOT NULL violation on
# a database where sale/stock are installed, so wait until the registry is full.
@tagged(
    "field_operation_attendance",
    "attendance_report",
    "post_install",
    "-at_install",
)
class TestAttendanceReportWizard(TransactionCase):
    """Test cases for Attendance Report Wizard"""

    def setUp(self):
        super().setUp()

        # Create test data
        self.company = self.env["res.company"].create(
            {
                "name": "Test Company",
            }
        )

        self.employee1 = self.env["hr.employee"].create(
            {
                "name": "John Doe",
                "job_title": "Field Technician",
                "active": True,
                "company_id": self.company.id,
            }
        )

        self.employee2 = self.env["hr.employee"].create(
            {
                "name": "Jane Smith",
                "job_title": "Senior Technician",
                "active": True,
                "company_id": self.company.id,
            }
        )

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
                "company_id": self.company.id,
            }
        )

        # Create wizard
        self.wizard = self.env["field.operation.attendance.wizard"].create(
            {
                "month": "3",
                "year": str(date.today().year),
                "theme": "light",
            }
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_operation(
        self, name, start_dt, end_dt, employees, company=None, status="done"
    ):
        """Create a field.operation that the report can pick up."""
        return self.env["field.operation"].create(
            {
                "name": name,
                "subject": name,
                "status": status,
                "start_date": start_dt,
                "end_date": end_dt,
                "person_ids": [(6, 0, employees.ids)],
                "company_id": (company or self.company).id,
            }
        )

    def _create_report_user(self, login, name):
        """Create a plain office user for the given test company."""
        return self.env["res.users"].create(
            {
                "name": name,
                "login": login,
                "company_id": self.company.id,
                "company_ids": [(6, 0, [self.company.id])],
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("field_operation.service_group_user").id,
                        ],
                    )
                ],
            }
        )

    def _employee_entry(self, data, employee):
        return next(
            emp for emp in data["employees"] if emp["employee_id"] == employee.id
        )

    # ------------------------------------------------------------------
    # Wizard basics
    # ------------------------------------------------------------------
    def test_01_wizard_creation(self):
        """Test wizard creation with default values"""
        self.assertEqual(self.wizard.month, "3")
        self.assertEqual(self.wizard.theme, "light")
        self.assertFalse(self.wizard.employee_ids)
        self.assertFalse(self.wizard.count_date_range)

    def test_02_month_selection(self):
        """Test month selection method"""
        month_selection = self.wizard._month_selection()
        self.assertEqual(len(month_selection), 12)
        self.assertIn(("1", "January"), month_selection)
        self.assertIn(("12", "December"), month_selection)

    def test_03_year_selection(self):
        """Test year selection method"""
        year_selection = self.wizard._year_selection()
        current_year = date.today().year
        expected_years = range(current_year - 2, current_year + 5)

        self.assertEqual(len(year_selection), len(expected_years))
        for y in expected_years:
            self.assertIn((str(y), str(y)), year_selection)

    def test_04_get_date_range_valid(self):
        """Test date range calculation with valid parameters"""
        self.wizard.month = "3"
        self.wizard.year = "2024"

        first_day, last_day, days_in_month = self.wizard._get_date_range()

        self.assertEqual(first_day, date(2024, 3, 1))
        self.assertEqual(last_day, date(2024, 3, 31))
        self.assertEqual(days_in_month, 31)

    def test_05_get_date_range_invalid_month(self):
        """Test date range with invalid month"""
        self.wizard.month = "13"
        self.wizard.year = "2024"

        with self.assertRaises(UserError):
            self.wizard._get_date_range()

    def test_06_get_date_range_invalid_year(self):
        """Test date range with invalid year"""
        self.wizard.month = "3"
        self.wizard.year = "1999"  # Too old

        with self.assertRaises(UserError):
            self.wizard._get_date_range()

    def test_07_get_employees_all(self):
        """Empty selection returns the expected employees, all of them active.

        The shared test database may hold other active employees, so the test
        checks containment (expected people are inside) instead of a hard count.
        """
        employees = self.wizard.with_company(self.company)._get_employees()

        self.assertIn(self.employee1, employees)
        self.assertIn(self.employee2, employees)
        self.assertTrue(all(emp.active for emp in employees))

    def test_08_get_employees_filtered(self):
        """Test getting filtered employees"""
        self.wizard.employee_ids = [(6, 0, [self.employee1.id])]
        employees = self.wizard._get_employees()
        self.assertEqual(len(employees), 1)
        self.assertEqual(employees, self.employee1)

    def test_09_get_status_domain(self):
        """Test status domain generation"""
        domain = self.wizard._get_status_domain()
        self.assertEqual(domain, [("status", "=", "done")])

    def test_10_initialize_employee_data(self):
        """Employee data is initialized for the selected employees only.

        No global employee count is assumed: the shared test database may hold
        other active employees, so we assert containment and the per-employee
        structure instead of ``len(employee_data) == 2``.
        """
        employees = self.wizard.with_company(self.company)._get_employees()
        employee_data = self.wizard._initialize_employee_data(employees, 31)

        self.assertIn(self.employee1.id, employee_data)
        self.assertIn(self.employee2.id, employee_data)
        self.assertGreaterEqual(len(employee_data), 2)

        emp_data = employee_data[self.employee1.id]
        self.assertEqual(emp_data["employee_name"], "John Doe")
        self.assertEqual(emp_data["job_title"], "Field Technician")
        self.assertEqual(len(emp_data["days"]), 31)
        self.assertEqual(emp_data["total_jobs"], 0)
        self.assertEqual(emp_data["total_hours"], 0.0)

    def test_11_generate_day_headers(self):
        """Test day headers generation"""
        day_headers = self.wizard._generate_day_headers(31)

        self.assertEqual(len(day_headers), 31)

        # Check first day
        self.assertEqual(day_headers[0]["day"], 1)
        self.assertIn(
            day_headers[0]["weekday"],
            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        )

        # Check weekend detection
        weekend_count = sum(1 for dh in day_headers if dh["is_weekend"])
        self.assertGreaterEqual(weekend_count, 8)  # At least 8 weekends in 31 days

    def test_12_calculate_totals(self):
        """Test totals calculation including the weekday/weekend split."""
        test_employees = [
            {
                "employee_name": "Test 1",
                "days": {"1": 1, "2": 0, "3": 1},
                "total_jobs": 2,
                "total_hours": 8.5,
                "work_days": 1,
                "weekend_days": 1,
                "total_days": 2,
            },
            {
                "employee_name": "Test 2",
                "days": {"1": 0, "2": 1, "3": 1},
                "total_jobs": 3,
                "total_hours": 12.0,
                "work_days": 2,
                "weekend_days": 0,
                "total_days": 2,
            },
        ]

        totals = self.wizard._calculate_totals(test_employees, 3)

        self.assertEqual(totals["days"]["1"], 1)
        self.assertEqual(totals["days"]["2"], 1)
        self.assertEqual(totals["days"]["3"], 2)
        self.assertEqual(totals["total_jobs"], 5)
        self.assertEqual(totals["total_hours"], 20.5)
        self.assertEqual(totals["work_days"], 3)
        self.assertEqual(totals["weekend_days"], 1)
        self.assertEqual(totals["total_days"], 4)

    def test_13_get_days_to_count_single_day(self):
        """Test days to count for single day operation"""
        work_start = date(2024, 3, 15)
        operation = MagicMock()
        operation.end_date = None

        days_to_count = self.wizard._get_days_to_count(
            work_start, operation, date(2024, 3, 1), date(2024, 3, 31)
        )
        self.assertEqual(days_to_count, [15])

    def test_14_get_days_to_count_date_range(self):
        """Test days to count for date range operation"""
        work_start = date(2024, 3, 10)
        operation = MagicMock()
        operation.end_date = datetime(2024, 3, 12)
        self.wizard.count_date_range = True

        days_to_count = self.wizard._get_days_to_count(
            work_start, operation, date(2024, 3, 1), date(2024, 3, 31)
        )
        self.assertEqual(days_to_count, [10, 11, 12])

    def test_15_get_days_to_count_out_of_range(self):
        """A February start must never be counted as a March day.

        28 February falls outside the reported March period, so the job
        interval has nothing in common with it and no day may be counted.
        """
        work_start = date(2024, 2, 28)  # February
        operation = MagicMock()
        operation.end_date = None

        days_to_count = self.wizard._get_days_to_count(
            work_start, operation, date(2024, 3, 1), date(2024, 3, 31)
        )
        self.assertEqual(days_to_count, [])  # February 28th not in March

    def test_16_update_employee_data(self):
        """Test employee data update with the counted days and hours."""
        emp_data = {
            "days": {"10": 0, "11": 0, "12": 0},
            "total_jobs": 0,
            "total_hours": 0.0,
        }

        self.wizard._update_employee_data(emp_data, [10, 11], 4.5)

        self.assertEqual(emp_data["days"]["10"], 1)
        self.assertEqual(emp_data["days"]["11"], 1)
        self.assertEqual(emp_data["days"]["12"], 0)
        self.assertEqual(emp_data["total_jobs"], 1)
        self.assertEqual(emp_data["total_hours"], 4.5)

    def test_17_action_print_pdf(self):
        """action_print_pdf feeds the report action with the wizard data.

        Odoo 19 model methods are read-only descriptors on the record, so the
        production method is patched on the model class, not on the record.
        """
        data = {"test": "data"}
        env_class = type(self.wizard.env)

        with patch.object(type(self.wizard), "get_attendance_data", return_value=data):
            with patch.object(env_class, "ref") as mock_ref:
                result = self.wizard.action_print_pdf()

        self.assertIsNotNone(result)
        mock_ref.assert_called_once_with(
            "field_operation_attendance.action_report_attendance"
        )
        mock_ref.return_value.report_action.assert_called_once_with(
            self.wizard, data=data
        )

    def test_18_no_employees_error(self):
        """No employees at all must raise a UserError.

        The employee lookup is patched on the class to return an empty
        recordset, so the guard is exercised independently of the data that a
        shared test database happens to contain.
        """
        empty_employees = self.env["hr.employee"]

        with patch.object(
            type(self.wizard), "_get_employees", return_value=empty_employees
        ):
            with self.assertRaises(UserError):
                self.wizard.get_attendance_data()

    @patch("xlsxwriter.Workbook")
    def test_19_export_with_xlsxwriter(self, mock_workbook):
        """Test Excel export with xlsxwriter"""
        mock_workbook_instance = MagicMock()
        mock_workbook.return_value = mock_workbook_instance

        mock_workbook_instance.add_worksheet.return_value = MagicMock()
        mock_workbook_instance.add_format.return_value = MagicMock()

        data = {
            "month_name": "March",
            "year": 2024,
            "days_in_month": 31,
            "day_headers": [{"day": 1, "weekday": "Fri", "is_weekend": False}],
            "employees": [],
            "totals": {
                "days": {},
                "total_jobs": 0,
                "total_hours": 0.0,
                "work_days": 0,
                "weekend_days": 0,
                "total_days": 0,
            },
        }

        with patch.object(type(self.wizard), "get_attendance_data", return_value=data):
            result = self.wizard._export_with_xlsxwriter()

        mock_workbook.assert_called_once()
        mock_workbook_instance.add_worksheet.assert_called_once_with("March 2024")
        self.assertEqual(result["type"], "ir.actions.act_url")

    def test_20_export_csv_fallback(self):
        """Test CSV fallback export"""
        data = {
            "month_name": "March",
            "year": 2024,
            "days_in_month": 31,
            "day_headers": [{"day": 1, "weekday": "Fri", "is_weekend": False}],
            "employees": [],
            "totals": {
                "days": {},
                "total_jobs": 0,
                "total_hours": 0.0,
                "work_days": 0,
                "weekend_days": 0,
                "total_days": 0,
            },
        }

        with patch.object(type(self.wizard), "get_attendance_data", return_value=data):
            result = self.wizard._export_csv_fallback()

        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertTrue(result["url"].startswith("/web/content/"))
        attachment = self.env["ir.attachment"].search(
            [("name", "=", "Field_Work_March_2024.csv")], limit=1
        )
        self.assertTrue(attachment, "CSV attachment was not created")

    def test_21_action_export_xlsx_with_fallback(self):
        """When xlsxwriter is missing the export action falls back to CSV.

        The module is imported by its full Odoo addon path, so the attribute can
        be patched without a ModuleNotFoundError.
        """
        with patch.object(wizard_module, "xlsxwriter", None):
            with patch.object(
                type(self.wizard), "_export_csv_fallback", return_value={"type": "test"}
            ) as mock_fallback:
                result = self.wizard.action_export_xlsx()

        mock_fallback.assert_called_once()
        self.assertEqual(result, {"type": "test"})

    def test_22_finalize_employee_data(self):
        """Test employee data finalization"""
        employee_data = {
            1: {"employee_name": "Zebra", "days": {}},
            2: {"employee_name": "Apple", "days": {}},
            3: {"employee_name": "Banana", "days": {}},
        }

        sorted_employees = self.wizard._finalize_employee_data(employee_data)

        self.assertEqual(len(sorted_employees), 3)
        self.assertEqual(sorted_employees[0]["employee_name"], "Apple")
        self.assertEqual(sorted_employees[1]["employee_name"], "Banana")
        self.assertEqual(sorted_employees[2]["employee_name"], "Zebra")

    def test_23_process_operations_empty(self):
        """Test processing empty operations keeps the zeroed totals."""
        employee_data = {
            self.employee1.id: {
                "days": {"1": 0, "2": 0},
                "total_jobs": 0,
                "work_days": 0,
                "weekend_days": 0,
                "total_days": 0,
                "total_hours": 0.0,
            }
        }

        result = self.wizard._process_operations(
            [],
            employee_data,
            date(2024, 3, 1),
            date(2024, 3, 31),
            datetime(2024, 3, 1, 0, 0, 0),
            datetime(2024, 3, 31, 23, 59, 59),
        )

        self.assertEqual(result[self.employee1.id]["total_days"], 0)
        self.assertEqual(result[self.employee1.id]["total_jobs"], 0)

    def test_24_create_attachment_helpers(self):
        """Test attachment creation helpers"""
        test_data = {"month_name": "March", "year": 2024}

        # Test Excel attachment
        mock_output = MagicMock()
        mock_output.read.return_value = b"excel_data"

        excel_result = self.wizard._create_excel_attachment(mock_output, test_data)
        self.assertEqual(excel_result["type"], "ir.actions.act_url")

        # Test CSV attachment
        csv_result = self.wizard._create_csv_attachment("csv,data", test_data)
        self.assertEqual(csv_result["type"], "ir.actions.act_url")

    def test_25_edge_cases(self):
        """Test various edge cases"""
        first_day = date(2024, 3, 1)
        last_day = date(2024, 3, 31)

        # Test with None work_start
        operation = MagicMock()
        operation.end_date = None
        days_to_count = self.wizard._get_days_to_count(
            None, operation, first_day, last_day
        )
        self.assertEqual(days_to_count, [])

        # Test with invalid work_end
        self.wizard.count_date_range = True
        operation.end_date = "invalid"
        days_to_count = self.wizard._get_days_to_count(
            date(2024, 3, 15), operation, first_day, last_day
        )
        self.assertEqual(days_to_count, [15])  # Should fall back to single day

    # ------------------------------------------------------------------
    # Month boundary clipping (T-A)
    # ------------------------------------------------------------------
    def test_26_days_to_count_clipped_to_report_month(self):
        """A job spanning two months only counts the days inside the report month."""
        self.wizard.month = "3"
        self.wizard.year = "2024"
        self.wizard.count_date_range = True

        operation = MagicMock()
        operation.end_date = datetime(2024, 3, 10)

        # Job starts 25 February, ends 10 March; report month is March.
        days_to_count = self.wizard._get_days_to_count(
            date(2024, 2, 25), operation, date(2024, 3, 1), date(2024, 3, 31)
        )

        self.assertEqual(days_to_count, list(range(1, 11)))
        self.assertNotIn(28, days_to_count)

    def test_27_month_boundary_clips_days_and_hours(self):
        """A job started last month is caught and clipped to this month's days/hours."""
        wizard = self.wizard
        wizard.month = "3"
        wizard.year = "2024"
        wizard.count_date_range = True

        operation = self._create_operation(
            "Spanning job",
            datetime(2024, 2, 25, 8, 0),
            datetime(2024, 3, 10, 17, 0),
            self.employee1,
        )
        full_hours = (
            operation.end_date - operation.start_date
        ).total_seconds() / 3600.0

        data = wizard.with_company(self.company).get_attendance_data()
        emp = self._employee_entry(data, self.employee1)

        worked_days = sorted(int(day) for day, val in emp["days"].items() if val > 0)
        self.assertEqual(worked_days, list(range(1, 11)))
        self.assertNotIn(28, worked_days)
        self.assertEqual(emp["total_days"], 10)

        # Hours are clipped to the reporting period, never the full job length.
        self.assertGreater(emp["total_hours"], 0.0)
        self.assertLess(emp["total_hours"], full_hours)

    # ------------------------------------------------------------------
    # Leap year (T-B)
    # ------------------------------------------------------------------
    def test_28_date_range_leap_year(self):
        """February has 29 days in a leap year and 28 days otherwise."""
        self.wizard.month = "2"

        self.wizard.year = "2024"
        first_day, last_day, days_in_month = self.wizard._get_date_range()
        self.assertEqual(first_day, date(2024, 2, 1))
        self.assertEqual(last_day, date(2024, 2, 29))
        self.assertEqual(days_in_month, 29)

        self.wizard.year = "2023"
        first_day, last_day, days_in_month = self.wizard._get_date_range()
        self.assertEqual(first_day, date(2023, 2, 1))
        self.assertEqual(last_day, date(2023, 2, 28))
        self.assertEqual(days_in_month, 28)

    # ------------------------------------------------------------------
    # Weekend separation (T-C)
    # ------------------------------------------------------------------
    def test_29_day_headers_weekend_flags(self):
        """Every day header carries the correct is_weekend flag."""
        self.wizard.month = "3"
        self.wizard.year = "2023"

        headers = self.wizard._generate_day_headers(31)
        self.assertEqual(len(headers), 31)

        for header in headers:
            real_day = date(2023, 3, header["day"])
            self.assertEqual(header["is_weekend"], real_day.weekday() >= 5)

        # 3-5 March 2023 = Fri, Sat, Sun -> exactly one weekday + two weekend.
        flags = {h["day"]: h["is_weekend"] for h in headers}
        self.assertFalse(flags[3])
        self.assertTrue(flags[4])
        self.assertTrue(flags[5])

    def test_30_employee_work_weekend_split(self):
        """Employee totals split worked days into weekday and weekend days."""
        wizard = self.wizard
        wizard.month = "3"
        wizard.year = "2023"
        wizard.count_date_range = True

        # 3-5 March 2023 = Friday, Saturday, Sunday.
        self._create_operation(
            "Weekend job",
            datetime(2023, 3, 3, 8, 0),
            datetime(2023, 3, 5, 17, 0),
            self.employee1,
        )

        data = wizard.with_company(self.company).get_attendance_data()
        emp = self._employee_entry(data, self.employee1)

        total_days = emp["total_days"]
        self.assertEqual(total_days, 3)
        self.assertEqual(emp["work_days"], 1)
        self.assertEqual(emp["weekend_days"], 2)
        self.assertEqual(emp["work_days"] + emp["weekend_days"], total_days)

    # ------------------------------------------------------------------
    # Company scope + sudo, record-rule independence (T-D)
    # ------------------------------------------------------------------
    def test_31_report_is_sudo_and_rule_independent(self):
        """Two ordinary users get the same totals for the same month.

        The report query must run with sudo (so record rules cannot hide jobs)
        and stay company-scoped, hence the identical totals below.
        """
        self.wizard.month = "3"
        self.wizard.year = "2024"

        self._create_operation(
            "Rule isolated job",
            datetime(2024, 3, 4, 8, 0),
            datetime(2024, 3, 4, 17, 0),
            self.employee1,
        )
        user1 = self._create_report_user("att_user_1", "Attendance User 1")
        user2 = self._create_report_user("att_user_2", "Attendance User 2")

        data1 = (
            self.wizard.with_user(user1)
            .with_company(self.company)
            .get_attendance_data()
        )
        data2 = (
            self.wizard.with_user(user2)
            .with_company(self.company)
            .get_attendance_data()
        )

        self.assertEqual(data1["totals"], data2["totals"])

        emp1 = self._employee_entry(data1, self.employee1)
        emp2 = self._employee_entry(data2, self.employee1)
        self.assertEqual(emp1["days"]["4"], 1)
        self.assertEqual(emp2["days"]["4"], 1)

    def test_32_report_is_company_scoped(self):
        """Another company's jobs are never counted in this company's report."""
        self.wizard.month = "3"
        self.wizard.year = "2024"

        company2 = self.env["res.company"].create({"name": "Other Company"})
        employee_c2 = self.env["hr.employee"].create(
            {
                "name": "Other Company Employee",
                "active": True,
                "company_id": company2.id,
            }
        )
        self._create_operation(
            "Foreign job",
            datetime(2024, 3, 5, 8, 0),
            datetime(2024, 3, 5, 17, 0),
            employee_c2,
            company=company2,
        )

        data_here = self.wizard.with_company(self.company).get_attendance_data()
        worked_here = {
            emp["employee_id"]
            for emp in data_here["employees"]
            if emp["total_jobs"] > 0
        }
        self.assertNotIn(employee_c2.id, worked_here)

        data_other = self.wizard.with_company(company2).get_attendance_data()
        worked_other = {
            emp["employee_id"]
            for emp in data_other["employees"]
            if emp["total_jobs"] > 0
        }
        self.assertIn(employee_c2.id, worked_other)

    # ------------------------------------------------------------------
    # Empty period (T-E)
    # ------------------------------------------------------------------
    def test_33_empty_period_returns_zero_structure(self):
        """Employees present, but no matching job: no crash, zeroed structure."""
        wizard = self.wizard
        wizard.month = "4"
        wizard.year = "2024"

        data = wizard.with_company(self.company).get_attendance_data()

        self.assertIn("employees", data)
        self.assertTrue(data["employees"])
        for emp in data["employees"]:
            self.assertEqual(emp["total_jobs"], 0)
            self.assertEqual(sum(emp["days"].values()), 0)

        self.assertEqual(data["totals"]["total_jobs"], 0)
        self.assertEqual(data["totals"]["total_hours"], 0.0)
