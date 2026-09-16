from core.rights_role_test_case import RightsRoleGraphQLTestCase
from core.test_helpers import (
    create_accountant_role,
    create_data_entry_clerk_hf_role,
    create_district_manager_role,
    create_enrolment_officer_role,
    create_hf_admin_role,
    create_hf_bound_role_user,
    create_manager_role,
    create_medical_advisor_role,
    create_medical_officer_role,
    create_monitoring_evaluation_role,
    create_raf_role,
    create_right_only_user,
    create_role_user,
    create_test_officer,
)
from location.test_helpers import (
    create_basic_test_locations,
    create_test_health_facility,
    create_test_village,
)


REPORTS_QUERY = """
query {
  reports {
    name
    module
  }
}
"""


class ReportRightsTests(RightsRoleGraphQLTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_basic_test_locations()

    def test_query_reports_right(self):
        allowed = create_right_only_user(
            "r_rep_q", ["gql_query_report_perms"], district_codes=self.DISTRICT_CODES
        )
        denied = create_right_only_user("r_rep_q_no", [], district_codes=self.DISTRICT_CODES)
        self.assert_gql_ok(allowed, REPORTS_QUERY)
        self.assert_gql_unauthorized(denied, REPORTS_QUERY)


class ReportRoleTests(RightsRoleGraphQLTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_basic_test_locations()
        village = create_test_village()
        district = village.parent.parent
        hf = create_test_health_facility(code="REPHF", location_id=district.id)
        districts = cls.DISTRICT_CODES + [district.code]
        officer = create_test_officer(villages=[village], custom_props={"code": "REPEO"})
        cls.users = {
            "accountant": create_role_user(
                "rep_acc", create_accountant_role(), district_codes=districts
            ),
            "enrolment_officer": create_role_user(
                "rep_eo",
                create_enrolment_officer_role(),
                district_codes=districts,
                officer=officer,
            ),
            "hf_admin": create_role_user(
                "rep_hf", create_hf_admin_role(), district_codes=districts
            ),
            "manager": create_role_user(
                "rep_mgr", create_manager_role(), district_codes=districts
            ),
            "medical_officer": create_role_user(
                "rep_mo", create_medical_officer_role(), district_codes=districts
            ),
            "data_entry_clerk": create_hf_bound_role_user(
                "rep_dec",
                create_data_entry_clerk_hf_role(),
                health_facility=hf,
                with_officer=True,
                villages=[village],
                district_codes=districts,
            ),
            "district_manager": create_role_user(
                "rep_dm", create_district_manager_role(), district_codes=districts
            ),
            "medical_advisor": create_role_user(
                "rep_ma", create_medical_advisor_role(), district_codes=districts
            ),
            "raf": create_role_user(
                "rep_raf", create_raf_role(), district_codes=districts
            ),
            "me": create_role_user(
                "rep_me", create_monitoring_evaluation_role(), district_codes=districts
            ),
        }

    def test_roles_can_query_reports(self):
        for name, user in self.users.items():
            with self.subTest(role=name):
                self.assert_user_has_named_perms(user, ["gql_query_report_perms"])
                self.assert_gql_ok(user, REPORTS_QUERY)
