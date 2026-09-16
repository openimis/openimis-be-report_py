"""Every registered report must actually render.

A report is only reachable through ``ReportConfig.reports``, so a broken one
fails nothing at import time: the owning module's suite stays green and the
report 500s in production instead. These tests walk the registry itself, so a
report contributed by any module is covered the day it is registered, and an
engine change -- reportbro, the database driver -- is caught across all of them
at once rather than the handful that happen to have a test of their own.

Both runs matter. Several queries only reach their filtering SQL, and the type
coercions in it, once a parameter is actually given a value; and a query that
rejects its parameters returns ``{"error": ...}`` rather than raising, which
renders into a perfectly valid PDF, so the error payload is asserted against
explicitly.

Models are reached through ``apps.get_model`` rather than imported: the sweep
covers reports from modules that ``report`` must not depend on.
"""
import inspect

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import RoleRight
from core.models.openimis_graphql_test_case import BaseTestContext
from core.test_helpers import create_test_interactive_user, create_test_role
from report.apps import ReportConfig
from report.services import generate_report, get_report_definition

# Values that do not depend on what is in the database.
LITERAL_PARAMS = {
    # Dates, deliberately wide so a report that filters on them still has the
    # database's rows in range.
    "date_start": "2019-01-01",
    "date_end": "2099-12-31",
    "date_from": "2019-01-01",
    "date_to": "2099-12-31",
    "dateFrom": "2019-01-01",
    "dateTo": "2099-12-31",
    "yearMonth": "2019-01-01",
    # Periods.
    "requested_month": 1,
    "requested_quarter": 1,
    "requested_year": 2019,
    # Closed vocabularies. These are self-checking: a query answers an unknown
    # value with {"error": ...}, which _generate asserts against.
    "action": "A",  # user_activity: every action
    "entity": "ENTITY_ALL",  # user_activity: every entity
    "scope": "F",  # claims_overview / claim_history: full
    "requested_sorting": "D",  # policy_renewals: by date
    "requested_payment_type": "A",  # premium_collection: every type
    "requested_claim_status": -5,  # claims_overview: sentinel for "any status"
}

# Parameters naming a row that has to exist: the queries validate them and
# answer "the requested X does not exist" for an id that does not. Resolved
# against the database at run time; see _resolve_id_params.
ID_PARAMS = {
    "region_id": ("location", "Location", {"type": "R"}),
    "requested_region_id": ("location", "Location", {"type": "R"}),
    "district_id": ("location", "Location", {"type": "D"}),
    "requested_district_id": ("location", "Location", {"type": "D"}),
    "locationId": ("location", "Location", {"type": "D"}),
    "requested_hf_id": ("location", "HealthFacility", {}),
    "requested_product_id": ("product", "Product", {}),
    "prodId": ("product", "Product", {}),
    "requested_insuree_id": ("insuree", "Insuree", {}),
    "officerId": ("core", "Officer", {}),
    "requested_officer_id": ("core", "Officer", {}),
}

# Parameters a report cannot actually run without, even though its signature
# gives them a default. Their defaults are sentinels the query then rejects --
# requested_year defaults to 0, which fails a `2010 <= year < 2100` check, and
# claim_history validates requested_insuree_id unconditionally, with no
# "all insurees" sentinel to fall back on.
EFFECTIVELY_REQUIRED = {
    "claims_primary_operational_indicators": ["requested_year", "requested_region_id"],
    "contributions_distribution": ["requested_year", "requested_product_id"],
    "product_derived_operational_indicators": ["requested_year", "requested_product_id"],
    "claim_history": ["requested_insuree_id"],
}


class ReportGenerationTestCase(TestCase):
    """Generate every report in the registry, with and without its options."""

    @classmethod
    def setUpTestData(cls):
        cls.user = create_test_interactive_user(username="reportSweepUser")
        cls.sample_params = dict(LITERAL_PARAMS)
        cls.sample_params["requested_user_id"] = cls.user.i_user.id
        cls.unresolved_ids = set()
        for name, (app_label, model_name, filters) in ID_PARAMS.items():
            row_id = cls._existing_id(app_label, model_name, filters)
            if row_id is None:
                cls.unresolved_ids.add(name)
            else:
                cls.sample_params[name] = row_id

    @staticmethod
    def _existing_id(app_label, model_name, filters):
        """The id of any matching row, or None if there is none to point at."""
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            return None
        queryset = model.objects.filter(**filters)
        if any(f.name == "validity_to" for f in model._meta.get_fields()):
            queryset = queryset.filter(validity_to__isnull=True)
        return queryset.values_list("pk", flat=True).first()

    @staticmethod
    def _parameter_names(report):
        """``(accepted, required)`` parameter names of a report query.

        ``user`` is passed positionally and ``**kwargs`` absorbs anything extra,
        so neither is a parameter the test has to supply.
        """
        parameters = [
            parameter
            for parameter in inspect.signature(
                report["python_query"]
            ).parameters.values()
            if parameter.name != "user"
            and parameter.kind
            not in (parameter.VAR_KEYWORD, parameter.VAR_POSITIONAL)
        ]
        required = [
            p.name for p in parameters if p.default is inspect.Parameter.empty
        ] + EFFECTIVELY_REQUIRED.get(report["name"], [])
        return [p.name for p in parameters], required

    def _sample(self, report, names, required):
        """Values for `names`, dropping optional ids the database cannot supply.

        An id the database has no row for is left out so the query keeps its own
        default, which every id parameter but one treats as "no filter". Where
        the report cannot run without it, there is nothing to fall back to and
        the test says so rather than asserting against a bogus id.
        """
        blocked = [n for n in required if n in self.unresolved_ids]
        if blocked:
            app_label, model_name, filters = ID_PARAMS[blocked[0]]
            self.skipTest(
                f"report '{report['name']}' requires {blocked}, and the test "
                f"database has no {app_label}.{model_name} matching {filters}"
            )

        usable = [
            name
            for name in names
            if name in required or name not in self.unresolved_ids
        ]
        unknown = [name for name in usable if name not in self.sample_params]
        self.assertFalse(
            unknown,
            f"report '{report['name']}' takes {unknown}, which this test has no "
            f"value for -- add one to LITERAL_PARAMS or ID_PARAMS so the report "
            f"stays covered",
        )
        return {name: self.sample_params[name] for name in usable}

    def _generate(self, report, kwargs, report_format="pdf"):
        name = report["name"]
        # One savepoint per report: a query that trips a database error leaves
        # the transaction aborted, and without this every later report in the
        # loop would report "current transaction is aborted" instead of its own
        # outcome.
        with transaction.atomic():
            data = report["python_query"](self.user, **kwargs)
            if isinstance(data, dict):
                self.assertNotIn(
                    "error",
                    data,
                    f"report '{name}' rejected {sorted(kwargs)}: {data.get('error')}",
                )
            definition = get_report_definition(name, report["default_report"])
            generated = generate_report(name, definition, data, report_format)
        self.assertTrue(generated, f"report '{name}' produced an empty {report_format}")

    def _reports(self):
        reports = sorted(ReportConfig.reports, key=lambda report: report["name"])
        self.assertTrue(
            reports,
            "no reports registered -- ReportConfig.ready() collects them from "
            "every installed module, so an empty registry means this sweep "
            "covers nothing",
        )
        return reports

    def test_every_report_generates_without_optional_parameters(self):
        for report in self._reports():
            with self.subTest(report=report["name"]):
                _, required = self._parameter_names(report)
                self._generate(report, self._sample(report, required, required))

    def test_every_report_generates_with_all_parameters(self):
        for report in self._reports():
            with self.subTest(report=report["name"]):
                accepted, required = self._parameter_names(report)
                self._generate(report, self._sample(report, accepted, required))

    def test_every_report_generates_as_xlsx(self):
        # The spreadsheet path is a separate reportbro renderer, so a working
        # PDF says nothing about it.
        for report in self._reports():
            with self.subTest(report=report["name"]):
                _, required = self._parameter_names(report)
                self._generate(
                    report,
                    self._sample(report, required, required),
                    report_format="xlsx",
                )


class ReportAPIStatusTestCase(APITestCase):
    """The REST endpoint must answer with the status the situation deserves.

    Not-found, forbidden and unauthorized were already right and are pinned
    here so they stay that way. The two that were not: an unsupported format
    reached the caller as a 500, and a rejected parameter as a 200 whose PDF
    contained the error message.
    """

    # Takes only parameters whose defaults are valid, so a bare call succeeds.
    RENDERABLE = "insuree_missing_photo"
    # Its requested_year default (0) fails the report's own range check.
    REJECTS_ITS_DEFAULTS = "claims_primary_operational_indicators"

    @classmethod
    def setUpTestData(cls):
        cls.permitted = create_test_interactive_user(
            username="reportApiPermitted",
            roles=[
                create_test_role(
                    perm_names=["gql_query_report_perms"], name="ReportApiRole"
                ).id
            ],
        )
        cls.permitted_token = BaseTestContext(user=cls.permitted).get_jwt()
        cls.unprivileged = create_test_interactive_user(
            username="reportApiUnprivileged",
            roles=[create_test_role(perm_names=[], name="ReportApiNoRightsRole").id],
        )
        cls.unprivileged_token = BaseTestContext(user=cls.unprivileged).get_jwt()

    def _get(self, report_name, report_format="pdf", token=None, query=""):
        url = f"/{settings.SITE_ROOT()}report/{report_name}/{report_format}/{query}"
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        return self.client.get(url, **headers)

    def test_renderable_report_is_ok(self):
        response = self._get(self.RENDERABLE, token=self.permitted_token)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_unknown_report_is_not_found(self):
        response = self._get("no_such_report", token=self.permitted_token)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_unsupported_format_is_a_bad_request(self):
        # The format comes out of the URL, so an unknown one is the caller's
        # mistake -- it used to reach generate_report and raise a bare
        # Exception, which the caller saw as a 500.
        response = self._get(self.RENDERABLE, "docx", token=self.permitted_token)
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_rejected_parameters_are_a_bad_request(self):
        # The query answers with {"error": ...} rather than raising. That used
        # to be rendered into the report and returned 200, so the client got a
        # PDF of an error message.
        response = self._get(self.REJECTS_ITS_DEFAULTS, token=self.permitted_token)
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_missing_rights_is_forbidden(self):
        response = self._get(self.RENDERABLE, token=self.unprivileged_token)
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_report_specific_right_is_enough(self):
        # The generic report right is not the only way in: a role holding just
        # the right the report declares must be able to run that report.
        # Taken from the report's own declaration rather than restated here,
        # so the test cannot drift from the right it is meant to check.
        permission = ReportConfig.get_report(self.RENDERABLE)["permission"]
        role = create_test_role(perm_names=[], name="ReportApiSpecificRole")
        for right_id in permission:
            RoleRight.objects.get_or_create(
                role=role, right_id=int(right_id), defaults={"audit_user_id": -1}
            )
        cache.clear()  # rights are cached per user
        user = create_test_interactive_user(
            username="reportApiSpecific", roles=[role.id]
        )
        response = self._get(
            self.RENDERABLE, token=BaseTestContext(user=user).get_jwt()
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_anonymous_is_unauthorized(self):
        response = self._get(self.RENDERABLE)
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)
