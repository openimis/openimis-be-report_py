from django.apps import AppConfig
from openIMIS.openimisapps import openimis_apps
import importlib.util
import logging

from core.rights_declaration import RightsDeclaration

logger = logging.getLogger(__file__)

MODULE_NAME = "report"


# Droits, par entite puis par action.
#
# Deux familles, et c'est voulu :
#
#  * `report` est le gabarit : le catalogue lisible (131200) et la surcharge de la
#    definition ReportBro stockee en base (131224/25/26). Un seul objet metier,
#    quatre actions canoniques, un seul modele (`ReportDefinition`).
#
#  * les 23 autres entites sont les *etats* du catalogue openIMIS : un etat = un
#    rapport nomme, livre en code par un module (`report_definitions`), avec un
#    identifiant a lui. Chacun n'a qu'une action, `query` - le lancer. Ils sont
#    declares une entite chacun plutot qu'en actions de `report` parce qu'un etat
#    n'est pas une operation sur le gabarit : c'est un objet metier distinct, dote
#    de sa propre requete et de son propre droit, que `report` ne fait
#    qu'heberger. Meme forme que `claim_batch.capitationPaymentReport`.
#
# Le pont vers le catalogue est `CATALOGUE_STATES` plus bas : c'est lui qui rend
# lisible quel etat sert quel `report_definitions[*]["name"]`, correspondance que
# seul l'entier ecrit en dur dans chaque module portait jusqu'ici.
#
# Neuf etats ne gardent aujourd'hui aucun rapport du catalogue (marques
# "dormant"). Ils sont conserves : `RoleRight.right_id` est un entier et ces
# entiers sont semes sur les roles (fixtures solution-builder, cartes de
# permissions) ; les retirer casserait le registre nom -> identifiant sur lequel
# s'appuie le semis, et rendrait l'identifiant reattribuable par erreur.
DJANGO_PERMS = {
    # Le gabarit et le catalogue.
    "report": {
        "query": ("report.view_reportdefinition", 131200),
        "create": ("report.add_reportdefinition", 131224),
        "update": ("report.change_reportdefinition", 131225),
        "delete": ("report.delete_reportdefinition", 131226),
    },
    # Les etats. Pas de modele django derriere : le nom reste declaratif, forme
    # sur le nom de l'entite, comme `claim_batch.view_capitationpaymentreport`.
    "primaryOperationalIndicatorPoliciesReport": {
        "query": ("report.view_primaryoperationalindicatorpoliciesreport", 131201),
    },
    "primaryOperationalIndicatorsClaimsReport": {
        "query": ("report.view_primaryoperationalindicatorsclaimsreport", 131202),
    },
    "derivedOperationalIndicatorsReport": {
        "query": ("report.view_derivedoperationalindicatorsreport", 131203),
    },
    "contributionCollectionReport": {
        "query": ("report.view_contributioncollectionreport", 131204),
    },
    "productSalesReport": {
        "query": ("report.view_productsalesreport", 131205),
    },
    "contributionDistributionReport": {
        "query": ("report.view_contributiondistributionreport", 131206),
    },
    "userActivityReport": {
        "query": ("report.view_useractivityreport", 131207),
    },
    # Dormant : aucun `report_definitions` ne porte 131208. L'etat "enrolment
    # performance indicators" n'est pas livre par les modules de cet assemblage.
    "enrolmentPerformanceIndicatorsReport": {
        "query": ("report.view_enrolmentperformanceindicatorsreport", 131208),
    },
    "statusOfRegisterReport": {
        "query": ("report.view_statusofregisterreport", 131209),
    },
    # Dormant : `insuree.insuree_missing_photo` est l'etat que ce droit nomme,
    # mais le catalogue lui applique 131215 (voir CATALOGUE_STATES). Conserve
    # comme registre nom -> identifiant ; le recablage est un autre lot.
    "insureeWithoutPhotosReport": {
        "query": ("report.view_insureewithoutphotosreport", 131210),
    },
    "paymentCategoryOverviewReport": {
        "query": ("report.view_paymentcategoryoverviewreport", 131211),
    },
    # Dormant : aucun rapport "matching funds" dans cet assemblage.
    "matchingFundsReport": {
        "query": ("report.view_matchingfundsreport", 131212),
    },
    "claimOverviewReport": {
        "query": ("report.view_claimoverviewreport", 131213),
    },
    "percentageReferralsReport": {
        "query": ("report.view_percentagereferralsreport", 131214),
    },
    # Porte a lui seul les quatre etats insuree du catalogue - voir
    # CATALOGUE_STATES : ce n'est pas un choix, c'est l'etat des lieux.
    "familiesInsureesOverviewReport": {
        "query": ("report.view_familiesinsureesoverviewreport", 131215),
    },
    # Dormant, comme 131210 : `insuree.insurees_pending_enrollment` est bien
    # l'etat que ce droit nomme, mais le catalogue lui applique 131215.
    "pendingInsureesReport": {
        "query": ("report.view_pendinginsureesreport", 131216),
    },
    "renewalsReport": {
        "query": ("report.view_renewalsreport", 131217),
    },
    # Dormant ici, vivant ailleurs : 131218 est aussi declare par
    # `claim_batch.capitationPaymentReport`, qui heberge l'etat capitation. Meme
    # entier, deux noms django (l'app_label suit le module qui declare) : une
    # reutilisation assumee, pas une collision. Conserve ici parce que c'est le
    # bloc report qui alloue l'identifiant.
    "capitationPaymentReport": {
        "query": ("report.view_capitationpaymentreport", 131218),
    },
    # Dormant : aucun rapport "rejected photo" dans cet assemblage.
    "rejectedPhotoReport": {
        "query": ("report.view_rejectedphotoreport", 131219),
    },
    # Dormant : aucun rapport "contribution payment" dans cet assemblage.
    "contributionPaymentReport": {
        "query": ("report.view_contributionpaymentreport", 131220),
    },
    # Dormant : l'attribution de numero de controle vit dans les modules de
    # paiement (contribution/payment), qui ne publient pas d'etat.
    "controlNumberAssignmentReport": {
        "query": ("report.view_controlnumberassignmentreport", 131221),
    },
    # Dormant : l'etat "commissions" n'est pas livre par cet assemblage.
    "overviewOfCommissionsReport": {
        "query": ("report.view_overviewofcommissionsreport", 131222),
    },
    "claimHistoryReport": {
        "query": ("report.view_claimhistoryreport", 131223),
    },
}

_PERM_CFG = {
    "gql_query_report_perms": ("report", "query"),
    "gql_mutation_report_add_perms": ("report", "create"),
    "gql_mutation_report_edit_perms": ("report", "update"),
    "gql_mutation_report_delete_perms": ("report", "delete"),
    "gql_reports_primary_operational_indicator_policies_perms": (
        "primaryOperationalIndicatorPoliciesReport", "query",
    ),
    "gql_reports_primary_operational_indicators_claims_perms": (
        "primaryOperationalIndicatorsClaimsReport", "query",
    ),
    "gql_reports_derived_operational_indicators_perms": (
        "derivedOperationalIndicatorsReport", "query",
    ),
    "gql_reports_contribution_collection_perms": ("contributionCollectionReport", "query"),
    "gql_reports_product_sales_perms": ("productSalesReport", "query"),
    "gql_reports_contribution_distribution_perms": ("contributionDistributionReport", "query"),
    "gql_reports_user_activity_perms": ("userActivityReport", "query"),
    "gql_reports_enrolment_performance_indicators_perms": (
        "enrolmentPerformanceIndicatorsReport", "query",
    ),
    "gql_reports_status_of_register_perms": ("statusOfRegisterReport", "query"),
    "gql_reports_insuree_without_photos_perms": ("insureeWithoutPhotosReport", "query"),
    "gql_reports_payment_category_overview_perms": ("paymentCategoryOverviewReport", "query"),
    "gql_reports_matching_funds_perms": ("matchingFundsReport", "query"),
    "gql_reports_claim_overview_report_perms": ("claimOverviewReport", "query"),
    "gql_reports_percentage_referrals_perms": ("percentageReferralsReport", "query"),
    "gql_reports_families_insurees_overview_perms": (
        "familiesInsureesOverviewReport", "query",
    ),
    "gql_reports_pending_insurees_perms": ("pendingInsureesReport", "query"),
    "gql_reports_renewals_perms": ("renewalsReport", "query"),
    "gql_reports_capitation_payment_perms": ("capitationPaymentReport", "query"),
    "gql_reports_rejected_photo_perms": ("rejectedPhotoReport", "query"),
    "gql_reports_contribution_payment_perms": ("contributionPaymentReport", "query"),
    "gql_reports_control_number_assignment_perms": (
        "controlNumberAssignmentReport", "query",
    ),
    "gql_reports_overview_of_commissions_perms": ("overviewOfCommissionsReport", "query"),
    "gql_reports_claim_history_report_perms": ("claimHistoryReport", "query"),
}

RIGHTS = RightsDeclaration(MODULE_NAME, DJANGO_PERMS, _PERM_CFG)

perms = RIGHTS.perms
django_perms = RIGHTS.django_perm_names
configured_perms = RIGHTS.configured
require = RIGHTS.require


# Le pont, jusqu'ici implicite, entre le catalogue et les etats declares ci-dessus.
#
# Chaque module publie ses rapports dans `report_definitions`, ou la cle
# "permission" est un entier ecrit en dur, sans nom : rien ne disait a quel etat
# du catalogue openIMIS il correspondait, ni qu'un droit nomme pour cet etat
# existait et restait inerte. C'est ce trou qui a laisse les quatre rapports
# insuree partir tous les quatre sur 131215 alors que 131210
# (insureeWithoutPhotosReport) et 131216 (pendingInsureesReport) leur sont
# assignes dans le catalogue.
#
# Cette table dit ce qui est *applique* aujourd'hui, pas ce qui devrait l'etre :
# les quatre entrees insuree pointent donc familiesInsureesOverviewReport. Le
# test de non-regression epingle la correspondance, divergences comprises, pour
# que le recablage (autre lot) soit visible en revue.
CATALOGUE_STATES = {
    # claim
    "claim_percentage_referrals": "percentageReferralsReport",
    "claims_overview": "claimOverviewReport",
    "claim_history": "claimHistoryReport",
    "claims_primary_operational_indicators": "primaryOperationalIndicatorsClaimsReport",
    # contribution
    "premium_collection": "contributionCollectionReport",
    "payment_category_overview": "paymentCategoryOverviewReport",
    "contributions_distribution": "contributionDistributionReport",
    # core
    "user_activity": "userActivityReport",
    "registers_status": "statusOfRegisterReport",
    # insuree - les quatre sur le meme etat, cf. ci-dessus
    "insuree_missing_photo": "familiesInsureesOverviewReport",
    "insurees_pending_enrollment": "familiesInsureesOverviewReport",
    "insuree_family_overview": "familiesInsureesOverviewReport",
    "enrolled_families": "familiesInsureesOverviewReport",
    # policy
    "policy_renewals": "renewalsReport",
    "policy_primary_operational_indicators": "primaryOperationalIndicatorPoliciesReport",
    # product
    "product_sales": "productSalesReport",
    "product_derived_operational_indicators": "derivedOperationalIndicatorsReport",
}


def catalogue_state_rights(report_name):
    """
    Les droits de l'etat servi par ce rapport du catalogue, ou None s'il n'en
    declare aucun - l'appelant doit alors echouer ferme.

    L'equivalent de `Model.get_rights` pour une entite qui n'a pas de modele :
    un etat est du code (une requete + un gabarit), pas une ligne en base. Lit la
    valeur configuree a l'appel, jamais a l'import : les cles `_perms` ne valent
    leur valeur qu'apres `ready()`.

    Les vues lisent encore `report_definitions[*]["permission"]` en direct ; les
    y brancher est un autre lot.
    """
    entity = CATALOGUE_STATES.get(report_name)
    if entity is None:
        return None
    return RIGHTS.configured(entity, "query")


DEFAULT_CFG = {

}


class ReportConfig(AppConfig):
    name = MODULE_NAME

    # Rights: constants, no longer overridable. They go neither through DEFAULT_CFG
    # nor through ready(): `ModuleConfiguration.get_or_default` now ignores any
    # `_perms` key stored in the database.
    gql_query_report_perms = RIGHTS.perms("report", "query")
    gql_mutation_report_add_perms = RIGHTS.perms("report", "create")
    gql_mutation_report_edit_perms = RIGHTS.perms("report", "update")
    gql_mutation_report_delete_perms = RIGHTS.perms("report", "delete")

    gql_reports_primary_operational_indicator_policies_perms = RIGHTS.perms(
        "primaryOperationalIndicatorPoliciesReport", "query"
    )
    gql_reports_primary_operational_indicators_claims_perms = RIGHTS.perms(
        "primaryOperationalIndicatorsClaimsReport", "query"
    )
    gql_reports_derived_operational_indicators_perms = RIGHTS.perms(
        "derivedOperationalIndicatorsReport", "query"
    )
    gql_reports_contribution_collection_perms = RIGHTS.perms(
        "contributionCollectionReport", "query"
    )
    gql_reports_product_sales_perms = RIGHTS.perms("productSalesReport", "query")
    gql_reports_contribution_distribution_perms = RIGHTS.perms(
        "contributionDistributionReport", "query"
    )
    gql_reports_user_activity_perms = RIGHTS.perms("userActivityReport", "query")
    gql_reports_enrolment_performance_indicators_perms = RIGHTS.perms(
        "enrolmentPerformanceIndicatorsReport", "query"
    )
    gql_reports_status_of_register_perms = RIGHTS.perms("statusOfRegisterReport", "query")
    gql_reports_insuree_without_photos_perms = RIGHTS.perms(
        "insureeWithoutPhotosReport", "query"
    )
    gql_reports_payment_category_overview_perms = RIGHTS.perms(
        "paymentCategoryOverviewReport", "query"
    )
    gql_reports_matching_funds_perms = RIGHTS.perms("matchingFundsReport", "query")
    gql_reports_claim_overview_report_perms = RIGHTS.perms("claimOverviewReport", "query")
    gql_reports_percentage_referrals_perms = RIGHTS.perms(
        "percentageReferralsReport", "query"
    )
    gql_reports_families_insurees_overview_perms = RIGHTS.perms(
        "familiesInsureesOverviewReport", "query"
    )
    gql_reports_pending_insurees_perms = RIGHTS.perms("pendingInsureesReport", "query")
    gql_reports_renewals_perms = RIGHTS.perms("renewalsReport", "query")
    gql_reports_capitation_payment_perms = RIGHTS.perms("capitationPaymentReport", "query")
    gql_reports_rejected_photo_perms = RIGHTS.perms("rejectedPhotoReport", "query")
    gql_reports_contribution_payment_perms = RIGHTS.perms(
        "contributionPaymentReport", "query"
    )
    gql_reports_control_number_assignment_perms = RIGHTS.perms(
        "controlNumberAssignmentReport", "query"
    )
    gql_reports_overview_of_commissions_perms = RIGHTS.perms(
        "overviewOfCommissionsReport", "query"
    )
    gql_reports_claim_history_report_perms = RIGHTS.perms("claimHistoryReport", "query")

    reports = []

    def __load_config(self, cfg):
        for field in cfg:
            if hasattr(ReportConfig, field):
                setattr(ReportConfig, field, cfg[field])

    @classmethod
    def get_report(cls, report_name):
        for report in cls.reports:
            if report["name"] == report_name:
                return report
        return None

    def ready(self):
        from core.models import ModuleConfiguration

        cfg = ModuleConfiguration.get_or_default(MODULE_NAME, DEFAULT_CFG)
        self.__load_config(cfg)

        all_apps = openimis_apps()

        for app in all_apps:
            try:
                self.load_app_reports(app)
            except Exception as exc:
                logger.debug(f"{app}: unknown exception occurred while adding report_definitions: {exc}")

        logger.debug("done loading reports")

    def load_app_reports(self, app_):
        spec = importlib.util.find_spec(f"{app_}.report")
        if spec:
            app = __import__(f"{app_}.report")
            if (
                hasattr(app, "report") and
                hasattr(app.report, "report_definitions") and
                isinstance(app.report.report_definitions, list)
            ):
                self.reports += app.report.report_definitions
                logger.debug(
                    f"{app_} {len(app.report.report_definitions)} reports loaded"
                )
            else:
                logger.debug(
                    f"{app_} has report submodule but no valid report_definitions"
                )
        else:
            logger.debug(
                logger.debug(f"{app_} has no report submodule, skipping")
            )
