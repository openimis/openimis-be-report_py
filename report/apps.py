from django.apps import AppConfig
from openIMIS.openimisapps import openimis_apps
import importlib.util
import logging

from core.rights_declaration import RightsDeclaration

logger = logging.getLogger(__file__)

MODULE_NAME = "report"


# Rights, by entity then by action.
#
# Two families, and that is intended:
#
#  * `report` is the template: the readable catalogue (131200) and the override of
#    the ReportBro definition stored in the database (131224/25/26). A single
#    business object, four canonical actions, a single model (`ReportDefinition`).
#
#  * the other 23 entities are the openIMIS catalogue's *statements*: one statement
#    = one named report, shipped in code by a module (`report_definitions`), with
#    an identifier of its own. Each has a single action, `query` - running it. They
#    are declared as one entity each rather than as actions of `report` because a
#    statement is not an operation on the template: it is a distinct business
#    object, with its own query and its own right, which `report` merely hosts.
#    Same shape as `claim_batch.capitationPaymentReport`.
#
# The bridge to the catalogue is `CATALOGUE_STATES` further down: that is what makes
# readable which statement serves which `report_definitions[*]["name"]`, a mapping
# that until now only the integer hard-coded in each module carried.
#
# Nine statements guard no catalogue report today (marked "dormant"). They are kept:
# `RoleRight.right_id` is an integer and those integers are seeded onto the roles
# (solution-builder fixtures, permission maps); removing them would break the
# name -> identifier register the seeding relies on, and would make the identifier
# reassignable by mistake.
DJANGO_PERMS = {
    # The template and the catalogue.
    "report": {
        "query": ("report.view_reportdefinition", 131200),
        "create": ("report.add_reportdefinition", 131224),
        "update": ("report.change_reportdefinition", 131225),
        "delete": ("report.delete_reportdefinition", 131226),
    },
    # The statements. No django model behind them: the name stays declarative,
    # formed on the entity's name, like `claim_batch.view_capitationpaymentreport`.
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
    # Dormant: no `report_definitions` carries 131208. The "enrolment performance
    # indicators" statement is not shipped by this assembly's modules.
    "enrolmentPerformanceIndicatorsReport": {
        "query": ("report.view_enrolmentperformanceindicatorsreport", 131208),
    },
    "statusOfRegisterReport": {
        "query": ("report.view_statusofregisterreport", 131209),
    },
    # Dormant: `insuree.insuree_missing_photo` is the statement this right names,
    # but the catalogue applies 131215 to it (see CATALOGUE_STATES). Kept as a
    # name -> identifier register; the rewiring is another batch of work.
    "insureeWithoutPhotosReport": {
        "query": ("report.view_insureewithoutphotosreport", 131210),
    },
    "paymentCategoryOverviewReport": {
        "query": ("report.view_paymentcategoryoverviewreport", 131211),
    },
    # Dormant: no "matching funds" report in this assembly.
    "matchingFundsReport": {
        "query": ("report.view_matchingfundsreport", 131212),
    },
    "claimOverviewReport": {
        "query": ("report.view_claimoverviewreport", 131213),
    },
    "percentageReferralsReport": {
        "query": ("report.view_percentagereferralsreport", 131214),
    },
    # Carries on its own the catalogue's four insuree statements - see
    # CATALOGUE_STATES: that is not a choice, it is how things stand.
    "familiesInsureesOverviewReport": {
        "query": ("report.view_familiesinsureesoverviewreport", 131215),
    },
    # Dormant, like 131210: `insuree.insurees_pending_enrollment` really is the
    # statement this right names, but the catalogue applies 131215 to it.
    "pendingInsureesReport": {
        "query": ("report.view_pendinginsureesreport", 131216),
    },
    "renewalsReport": {
        "query": ("report.view_renewalsreport", 131217),
    },
    # Dormant here, alive elsewhere: 131218 is also declared by
    # `claim_batch.capitationPaymentReport`, which hosts the capitation statement.
    # Same integer, two django names (the app_label follows the declaring module): an
    # owned reuse, not a collision. Kept here because the report block is what
    # allocates the identifier.
    "capitationPaymentReport": {
        "query": ("report.view_capitationpaymentreport", 131218),
    },
    # Dormant: no "rejected photo" report in this assembly.
    "rejectedPhotoReport": {
        "query": ("report.view_rejectedphotoreport", 131219),
    },
    # Dormant: no "contribution payment" report in this assembly.
    "contributionPaymentReport": {
        "query": ("report.view_contributionpaymentreport", 131220),
    },
    # Dormant: control number assignment lives in the payment modules
    # (contribution/payment), which publish no statement.
    "controlNumberAssignmentReport": {
        "query": ("report.view_controlnumberassignmentreport", 131221),
    },
    # Dormant: the "commissions" statement is not shipped by this assembly.
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


# The bridge, implicit until now, between the catalogue and the statements declared
# above.
#
# Each module publishes its reports in `report_definitions`, where the "permission"
# key is a hard-coded integer with no name: nothing said which openIMIS catalogue
# statement it corresponded to, nor that a right named for that statement existed
# and stayed inert. That is the gap that let all four insuree reports go out on
# 131215 when 131210 (insureeWithoutPhotosReport) and 131216 (pendingInsureesReport)
# are the ones assigned to them in the catalogue.
#
# This table says what is *enforced* today, not what ought to be: the four insuree
# entries therefore point at familiesInsureesOverviewReport. The regression test pins
# the mapping down, divergences included, so that the rewiring (another batch of
# work) is visible in review.
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
    # insuree - all four on the same statement, see above
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
    The rights of the statement this catalogue report serves, or None when it
    declares none - the caller must then fail closed.

    The equivalent of `Model.get_rights` for an entity that has no model: a statement
    is code (a query plus a template), not a row in the database. Reads the configured
    value at call time, never at import: the `_perms` keys only hold their value after
    `ready()`.

    The views still read `report_definitions[*]["permission"]` directly; wiring them
    onto this is another batch of work.
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
