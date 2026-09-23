"""
Guard rails on report's rights declaration.

Same structure as `claim`: `DJANGO_PERMS` by entity then by action, `_PERM_CFG`
deriving the config keys from it, and `ReportDefinition.get_rights` as the access
point.

What is specific to report is that every other right protects not a model but a
catalogue *statement* - a named report, shipped in code by another module in
`report_definitions`, where the "permission" key carries the integer hard-coded and
nothing else. `CATALOGUE_STATES` is the bridge between the two, and that is what this
file pins down: a moved integer, a renamed statement or a report that changes right
becomes visible in review.

This file describes the state as *enforced*, not as it ought to be: the four insuree
reports share 131215 while 131210 and 131216 are the ones assigned to them by name in
the catalogue. The divergence is listed, not fixed (another batch of work).
"""

from django.test import TestCase

from report.apps import (
    CATALOGUE_STATES,
    DJANGO_PERMS,
    ReportConfig,
    _PERM_CFG,
    catalogue_state_rights,
    configured_perms,
    django_perms,
    perms,
)
from report.models import ReportDefinition

# The identifiers as deployed. Changing one is incompatible with the existing roles:
# this test has to be updated *and* the new right granted.
EXPECTED_RIGHTS = {
    "gql_query_report_perms": ["131200"],
    "gql_mutation_report_add_perms": ["131224"],
    "gql_mutation_report_edit_perms": ["131225"],
    "gql_mutation_report_delete_perms": ["131226"],
    "gql_reports_primary_operational_indicator_policies_perms": ["131201"],
    "gql_reports_primary_operational_indicators_claims_perms": ["131202"],
    "gql_reports_derived_operational_indicators_perms": ["131203"],
    "gql_reports_contribution_collection_perms": ["131204"],
    "gql_reports_product_sales_perms": ["131205"],
    "gql_reports_contribution_distribution_perms": ["131206"],
    "gql_reports_user_activity_perms": ["131207"],
    "gql_reports_enrolment_performance_indicators_perms": ["131208"],
    "gql_reports_status_of_register_perms": ["131209"],
    "gql_reports_insuree_without_photos_perms": ["131210"],
    "gql_reports_payment_category_overview_perms": ["131211"],
    "gql_reports_matching_funds_perms": ["131212"],
    "gql_reports_claim_overview_report_perms": ["131213"],
    "gql_reports_percentage_referrals_perms": ["131214"],
    "gql_reports_families_insurees_overview_perms": ["131215"],
    "gql_reports_pending_insurees_perms": ["131216"],
    "gql_reports_renewals_perms": ["131217"],
    "gql_reports_capitation_payment_perms": ["131218"],
    "gql_reports_rejected_photo_perms": ["131219"],
    "gql_reports_contribution_payment_perms": ["131220"],
    "gql_reports_control_number_assignment_perms": ["131221"],
    "gql_reports_overview_of_commissions_perms": ["131222"],
    "gql_reports_claim_history_report_perms": ["131223"],
}

# Declared statements that no catalogue report serves. Kept because
# `RoleRight.right_id` is an integer seeded onto the roles: the identifier has to stay
# reserved and its name findable. Removing one from here requires first checking that
# no role, no fixture and no permission map carries it.
DORMANT_STATES = {
    "enrolmentPerformanceIndicatorsReport",  # 131208, statement not shipped
    "insureeWithoutPhotosReport",            # 131210, the catalogue applies 131215
    "matchingFundsReport",                   # 131212, statement not shipped
    "pendingInsureesReport",                 # 131216, the catalogue applies 131215
    "capitationPaymentReport",               # 131218, the statement lives in claim_batch
    "rejectedPhotoReport",                   # 131219, statement not shipped
    "contributionPaymentReport",             # 131220, statement not shipped
    "controlNumberAssignmentReport",         # 131221, statement not shipped
    "overviewOfCommissionsReport",           # 131222, statement not shipped
}

# The catalogue as it stands today: report name -> integer enforced by
# `report_definitions[*]["permission"]` in the module that publishes it. That is what
# `CATALOGUE_STATES` has to reflect.
EXPECTED_CATALOGUE_RIGHTS = {
    "claim_percentage_referrals": ["131214"],
    "claims_overview": ["131213"],
    "claim_history": ["131223"],
    "claims_primary_operational_indicators": ["131202"],
    "premium_collection": ["131204"],
    "payment_category_overview": ["131211"],
    "contributions_distribution": ["131206"],
    "user_activity": ["131207"],
    "registers_status": ["131209"],
    # The four insuree statements are enforced with the same right, while 131210 and
    # 131216 are assigned to them in the catalogue and stay inert. An observation, not
    # a target: the rewiring is another batch of work.
    "insuree_missing_photo": ["131215"],
    "insurees_pending_enrollment": ["131215"],
    "insuree_family_overview": ["131215"],
    "enrolled_families": ["131215"],
    "policy_renewals": ["131217"],
    "policy_primary_operational_indicators": ["131201"],
    "product_sales": ["131205"],
    "product_derived_operational_indicators": ["131203"],
}


class ReportPermissionDeclarationTestCase(TestCase):
    def test_right_ids_unchanged(self):
        self.assertEqual(
            {key: getattr(ReportConfig, key) for key in EXPECTED_RIGHTS}, EXPECTED_RIGHTS
        )

    def test_perm_cfg_covers_every_declared_action(self):
        declared = {
            (entity, action)
            for entity, actions in DJANGO_PERMS.items()
            for action in actions
        }
        self.assertEqual(set(_PERM_CFG.values()), declared)

    def test_perm_cfg_matches_config_attributes(self):
        """`__load_config` ignores the keys with no class attribute."""
        missing = [key for key in _PERM_CFG if not hasattr(ReportConfig, key)]
        self.assertEqual(missing, [])

    def test_no_right_list_is_empty(self):
        empty = [key for key in _PERM_CFG if not getattr(ReportConfig, key)]
        self.assertEqual(empty, [])

    def test_attributes_carry_the_declared_right(self):
        for key, (entity, action) in _PERM_CFG.items():
            with self.subTest(key=key):
                self.assertEqual(getattr(ReportConfig, key), perms(entity, action))

    def test_every_state_has_exactly_one_action(self):
        """Un etat se lance, point : `query` et rien d'autre."""
        for entity, actions in DJANGO_PERMS.items():
            if entity == "report":
                continue
            with self.subTest(entity=entity):
                self.assertEqual(list(actions), ["query"])

    def test_right_ids_are_not_shared(self):
        """
        No identifier sharing in this module: one statement = one integer. 131218 is
        also declared by `claim_batch.capitationPaymentReport`, but that is a sharing
        between modules, invisible from here.
        """
        seen = {}
        for entity, actions in DJANGO_PERMS.items():
            for action, (_, right_id) in actions.items():
                seen.setdefault(right_id, []).append(f"{entity}.{action}")
        shared = {right: who for right, who in seen.items() if len(who) > 1}
        self.assertEqual(shared, {})

    def test_django_permission_names_are_unique(self):
        seen = {}
        for entity, actions in DJANGO_PERMS.items():
            for action, (name, _) in actions.items():
                seen.setdefault(name, []).append(f"{entity}.{action}")
        shared = {name: who for name, who in seen.items() if len(who) > 1}
        self.assertEqual(shared, {})

    def test_unknown_entity_or_action_raises(self):
        with self.assertRaises(KeyError):
            perms("nosuchentity", "query")
        with self.assertRaises(KeyError):
            perms("report", "nosuchaction")
        with self.assertRaises(KeyError):
            django_perms("report", "nosuchaction")

    # --- le pont vers le catalogue ----------------------------------------
    def test_catalogue_states_point_to_declared_entities(self):
        undeclared = sorted(
            {entity for entity in CATALOGUE_STATES.values() if entity not in DJANGO_PERMS}
        )
        self.assertEqual(undeclared, [])

    def test_catalogue_state_rights_match_the_catalogue(self):
        """
        The right `CATALOGUE_STATES` denotes has to be the one the module publishing
        the report hard-codes in `report_definitions[*]["permission"]`.
        """
        for report in ReportConfig.reports:
            name = report["name"]
            with self.subTest(report=name):
                self.assertIn(
                    name,
                    CATALOGUE_STATES,
                    f"{name} is published by a module but attached to no statement",
                )
                self.assertEqual(catalogue_state_rights(name), report["permission"])

    def test_catalogue_rights_unchanged(self):
        """Pins the integer enforced by every report present in the assembly."""
        applied = {
            report["name"]: report["permission"]
            for report in ReportConfig.reports
            if report["name"] in EXPECTED_CATALOGUE_RIGHTS
        }
        self.assertEqual(
            applied,
            {
                name: right
                for name, right in EXPECTED_CATALOGUE_RIGHTS.items()
                if name in applied
            },
        )

    def test_catalogue_state_rights_is_none_for_an_unknown_report(self):
        """None means "no rule": the caller must fail closed."""
        self.assertIsNone(catalogue_state_rights("nosuchreport"))

    def test_dormant_states_are_the_expected_ones(self):
        """
        A statement that no longer appears in `CATALOGUE_STATES` becomes dormant
        silently: its right stops being enforced while the roles still carry it.
        """
        served = set(CATALOGUE_STATES.values())
        dormant = {
            entity
            for entity in DJANGO_PERMS
            if entity != "report" and entity not in served
        }
        self.assertEqual(dormant, DORMANT_STATES)

    # --- the access point through the model -------------------------------
    def test_model_exposes_every_action_of_its_entity(self):
        for action in DJANGO_PERMS["report"]:
            with self.subTest(action=action):
                self.assertEqual(
                    ReportDefinition.get_rights(action),
                    configured_perms("report", action),
                )
                self.assertTrue(ReportDefinition.get_rights(action))

    def test_model_returns_none_for_an_undeclared_action(self):
        self.assertIsNone(ReportDefinition.get_rights("nosuchaction"))

    def test_model_reads_the_configured_value_not_the_declared_default(self):
        original = ReportConfig.gql_query_report_perms
        try:
            ReportConfig.gql_query_report_perms = ["999999"]
            self.assertEqual(ReportDefinition.get_rights("query"), ["999999"])
            self.assertEqual(perms("report", "query"), ["131200"])
        finally:
            ReportConfig.gql_query_report_perms = original
