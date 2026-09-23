"""
Garde-fous sur la declaration des droits de report.

Meme structure que `claim` : `DJANGO_PERMS` par entite puis par action, `_PERM_CFG` qui
en derive les cles de config, et `ReportDefinition.get_rights` comme point d'acces.

La specificite de report est qu'un droit sur deux ne protege pas un modele mais un
*etat* du catalogue - un rapport nomme, livre en code par un autre module dans
`report_definitions`, ou la cle "permission" porte l'entier en dur et rien d'autre.
`CATALOGUE_STATES` est le pont entre les deux, et c'est ce que ce fichier epingle :
un entier deplace, un etat renomme ou un rapport qui change de droit devient visible
en revue.

Ce fichier decrit l'etat *applique*, pas l'etat souhaitable : les quatre rapports
insuree partagent 131215 alors que 131210 et 131216 leur sont nommement assignes dans
le catalogue. La divergence est listee, pas corrigee (autre lot).
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

# Etats declares qu'aucun rapport du catalogue ne sert. Conserves parce que
# `RoleRight.right_id` est un entier seme sur les roles : l'identifiant doit rester
# reserve et son nom retrouvable. En retirer un d'ici demande de verifier d'abord
# qu'aucun role, aucune fixture et aucune carte de permissions ne le porte.
DORMANT_STATES = {
    "enrolmentPerformanceIndicatorsReport",  # 131208, etat non livre
    "insureeWithoutPhotosReport",            # 131210, le catalogue applique 131215
    "matchingFundsReport",                   # 131212, etat non livre
    "pendingInsureesReport",                 # 131216, le catalogue applique 131215
    "capitationPaymentReport",               # 131218, l'etat vit dans claim_batch
    "rejectedPhotoReport",                   # 131219, etat non livre
    "contributionPaymentReport",             # 131220, etat non livre
    "controlNumberAssignmentReport",         # 131221, etat non livre
    "overviewOfCommissionsReport",           # 131222, etat non livre
}

# Le catalogue tel qu'il est aujourd'hui : nom du rapport -> entier applique par
# `report_definitions[*]["permission"]` dans le module qui le publie. C'est ce que
# `CATALOGUE_STATES` doit refleter.
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
    # Les quatre etats insuree sont appliques avec le meme droit, alors que
    # 131210 et 131216 leur sont assignes dans le catalogue et restent inertes.
    # Constat, pas cible : le recablage est un autre lot.
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
        Aucun partage d'identifiant dans ce module : un etat = un entier. 131218 est
        aussi declare par `claim_batch.capitationPaymentReport`, mais c'est un partage
        entre modules, invisible d'ici.
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
        Le droit que `CATALOGUE_STATES` designe doit etre celui que le module publiant
        le rapport ecrit en dur dans `report_definitions[*]["permission"]`.
        """
        for report in ReportConfig.reports:
            name = report["name"]
            with self.subTest(report=name):
                self.assertIn(
                    name,
                    CATALOGUE_STATES,
                    f"{name} est publie par un module mais n'est rattache a aucun etat",
                )
                self.assertEqual(catalogue_state_rights(name), report["permission"])

    def test_catalogue_rights_unchanged(self):
        """Epingle l'entier applique par chaque rapport present dans l'assemblage."""
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
        Un etat qui n'apparait plus dans `CATALOGUE_STATES` devient dormant sans bruit :
        son droit cesse d'etre applique alors que les roles le portent toujours.
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
