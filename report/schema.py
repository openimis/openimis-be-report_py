import logging

import graphene
from core.schema import OpenIMISMutation
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from core.utils import TimeUtils
from report.apps import ReportConfig
from report.models import ReportDefinition
from report.services import get_report_definition

logger = logging.getLogger(__file__)


class ReportGQLType(graphene.ObjectType):
    name = graphene.String()
    default_report = graphene.String()
    definition = graphene.String()
    description = graphene.String()
    module = graphene.String()
    permission = graphene.String()

    def resolve_definition(self, info, **kwargs):
        return get_report_definition(self.get("name"), self.get("default_report"))


class Query(graphene.ObjectType):
    reports = graphene.List(
        ReportGQLType,
        description="This lists all the available reports on the system, exposed by each module",
    )
    report = graphene.Field(
        ReportGQLType,
        name=graphene.String(required=True),
    )

    def resolve_reports(self, info, **kwargs):
        return [
            report
            for report in ReportConfig.reports
            if info.context.user.has_perms(report["permission"])
        ]

    def resolve_report(self, info, name, **kwargs):
        return ReportConfig.get_report(name)


def update_or_create_report_definition(data, user):
    data.pop("client_mutation_id", None)
    data.pop("client_mutation_label", None)
    name = data.pop("name", None)

    report_definition = ReportDefinition.objects.filter(
        name=name, validity_to__isnull=True
    ).first()
    if report_definition:
        report_definition.validity_to = TimeUtils.now()
    else:
        template = ReportConfig.get_report(name)
        report_definition = ReportDefinition.objects.create(
            name=template.get("name"), engine=template.get("engine")
        )

    [setattr(report_definition, k, v) for k, v in data.items()]
    report_definition.save()
    return report_definition


class OverrideReportMutation(OpenIMISMutation):
    """
    Override an existing Report (the default is provided by the report itself)
    """

    _mutation_module = "report"
    _mutation_class = "OverrideReportMutation"

    class Input(OpenIMISMutation.Input):
        name = graphene.String(required=True)
        definition = graphene.String(required=True)

    @classmethod
    def async_mutate(cls, user, **data):
        try:
            if type(user) is AnonymousUser or not user.id:
                raise ValidationError(_("mutation.authentication_required"))

            update_or_create_report_definition(data, user)
            return None
        except Exception as exc:
            logger.exception("report.mutation.failed_to_override_report")
            return [
                {
                    "message": _("report.mutation.failed_to_override_report"),
                    "detail": str(exc),
                }
            ]


class Mutation(graphene.ObjectType):
    override_report = OverrideReportMutation.Field()
