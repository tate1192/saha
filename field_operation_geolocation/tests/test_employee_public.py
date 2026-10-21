"""The home address must be readable through the public employee profile.

``hr.employee.fetch()`` redirects a read made by a user without HR rights to
``hr.employee.public`` and refuses any field that is not declared there. When
``home_location_id`` lived on ``hr.employee`` only, opening an employee card
from the team form (or exporting the employee list) raised

    The fields "home_location_id", which you are trying to read, are not
    available for employee public profiles.

This test pins the field on the public model so the read keeps working.
"""

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEmployeePublicHomeLocation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.home = cls.env["res.partner"].create(
            {
                "name": "Driver Home",
                "street": "Ev Sokak 1",
                "city": "Istanbul",
                "partner_latitude": 41.0,
                "partner_longitude": 29.0,
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {"name": "Home Location Driver", "home_location_id": cls.home.id}
        )
        # An internal user without any HR group: this is the profile that
        # triggers the public fallback.
        cls.office_user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Office Without HR",
                    "login": "no_hr_public_profile_test",
                    "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
        )

    def test_the_field_is_declared_on_the_public_profile(self):
        self.assertIn("home_location_id", self.env["hr.employee.public"]._fields)

    def test_a_user_without_hr_rights_can_read_the_home_address(self):
        if self.office_user.has_group("hr.group_hr_user"):
            self.skipTest("The probe user unexpectedly has HR rights.")
        employee_as_user = self.env["hr.employee"].with_user(self.office_user).browse(
            self.employee.id
        )
        values = employee_as_user.read(["name", "home_location_id"])[0]
        self.assertEqual(values["home_location_id"], (self.home.id, self.home.display_name))

    def test_the_public_record_returns_the_same_address(self):
        public = (
            self.env["hr.employee.public"]
            .with_user(self.office_user)
            .search([("id", "=", self.employee.id)])
        )
        self.assertEqual(public.home_location_id, self.home)
