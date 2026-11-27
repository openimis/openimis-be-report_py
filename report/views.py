import io
import json
import logging
import os
import re
import tempfile

from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, FileResponse
from django.template import loader
from django.utils.translation import gettext as _
from django.views.decorators.clickjacking import xframe_options_exempt
from reportbro import ReportBroError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from report.services import generate_report, get_report_definition

from .apps import ReportConfig

logger = logging.getLogger(__file__)


class HasReportRight(IsAuthenticated):
    """
    Authenticated, and holding the generic report right.

    Backport of the view-level check of the CVE-2026-82489 fix. core's
    check_user_rights(ReportConfig.gql_query_report_perms) is not used here: on
    this branch ReportConfig.ready() rebinds the attribute from the module
    configuration, so a list captured by a decorator at import time could be the
    empty class default, and has_perms([]) is True for every user. The right is
    read on each request instead.
    """

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.has_perms(
            ReportConfig.gql_query_report_perms
        )


# Previews live in a directory of their own, so that a key can only ever name a
# file this view wrote. The key is the basename of a NamedTemporaryFile: "tmp"
# followed by characters from tempfile's alphabet, never a path separator or
# a dot (OP-3352).
PREVIEW_DIR_NAME = "openimis-report-preview"
PREVIEW_KEY_PATTERN = re.compile(r"tmp[A-Za-z0-9_]+")


def _preview_dir():
    path = os.path.realpath(os.path.join(tempfile.gettempdir(), PREVIEW_DIR_NAME))
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def _remove_preview(path):
    # Two requests for the same key may race; the loser has nothing to remove.
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _preview_path(key):
    """
    Path of the preview a key names, or None if the key could name anything else.
    fullmatch rather than match with "$": "$" also matches before a trailing
    newline. realpath resolves symlinks and "..", so a key is also refused if it
    resolves outside the preview directory.
    """
    if not isinstance(key, str) or not PREVIEW_KEY_PATTERN.fullmatch(key):
        return None
    preview_dir = _preview_dir()
    path = os.path.realpath(os.path.join(preview_dir, key))
    if os.path.dirname(path) != preview_dir:
        return None
    return path


@api_view(["GET"])
# Only authentication is enforced here: which right grants *this* report
# depends on the report being asked for, which the permission class cannot see.
# The rights check is below, once report_config is resolved.
@permission_classes([IsAuthenticated])
def report(request, report_name, report_format="pdf", alternate=None):
    """
    Run a report
    :param request: Predefined by Django
    :param report_name: Report name within the module
    :param report_format: pdf (default) or xlsx
    :param alternate: Future use, allows several templates for a single report: different languages or report variants
    :return: view
    """
    logger.debug(
        "report name %s in %s format",
        report_name,
        report_format,
    )
    report_config = ReportConfig.get_report(report_name)
    if not report_config:
        raise Http404("Poll does not exist")
    report_definition = get_report_definition(
        report_name, report_config["default_report"]
    )
    # Either the generic "may run reports" right or the right the report
    # declares for itself is enough. A report that declares none is reachable
    # with the generic right alone.
    report_permission = report_config.get("permission")
    if not (
        request.user.has_perms(ReportConfig.gql_query_report_perms)
        or (report_permission and request.user.has_perms(report_permission))
    ):
        raise PermissionDenied(_("unauthorized"))

    # parameters tend to get put in lists because they *could* be repeated
    unlisted = {
        k: (v[0] if isinstance(v, list) and len(v) == 0 else v)
        for k, v in request.GET.items()
    }

    data = report_config["python_query"](request.user, **unlisted)

    return FileResponse(
        io.BytesIO(
            generate_report(
                report_name,
                report_definition,
                data,
                report_format,
            )
        ), filename=f"{report_name}.{report_format}", as_attachment=False
    )


@api_view(["GET", "PUT", "POST"])
@xframe_options_exempt
@permission_classes([HasReportRight])
def reportbro_designer(request):
    template = loader.get_template("report/reportbro.html")

    context = {}
    return HttpResponse(template.render(context, request))


@api_view(["GET", "PUT", "POST"])
@xframe_options_exempt
@permission_classes([HasReportRight])
def reportbro_previewer(request):
    """
    Generates a report preview within the designer. This can work in two ways:
    1. The report details are passed as a PUT. We generate the report and store the result in a temporary file.
       The Designer then runs a GET request to retrieve the generated report with the key returned by the PUT request.
       This only generates PDFs in theory.
    2. The report is generated on the fly. This is used by the Designer to generate PDFs and XLSX files.
    """
    response = HttpResponse('')
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, PUT, OPTIONS'
    response['Access-Control-Allow-Headers'] = \
        'Origin, X-Requested-With, X-HTTP-Method-Override, Content-Type, Accept, Authorization, Z-Key'

    if request.method == "PUT":
        json_data = json.loads(request.body.decode('utf-8'))
        output_format = json_data.get('outputFormat')
        if output_format not in ('pdf', 'xlsx'):
            return HttpResponseBadRequest('outputFormat parameter missing or invalid')
        if not isinstance(json_data, dict) or not isinstance(json_data.get('report'), dict) or \
                not isinstance(json_data.get('data'), dict) or not isinstance(json_data.get('isTestData'), bool):
            return HttpResponseBadRequest('invalid report values')
        report_definition = json_data.get('report')
        data = json_data.get('data')
        is_test_data = json_data.get('isTestData')
        with tempfile.NamedTemporaryFile(dir=_preview_dir(), prefix="tmp", delete=False) as temp_file:
            preview_path = temp_file.name
        try:
            generate_report("preview", report_definition, data, output_format,
                            local_file=preview_path, is_test_data=is_test_data)
            return HttpResponse('key:' + os.path.basename(preview_path))
        except ReportBroError as e:
            _remove_preview(preview_path)
            logger.exception(e.error)
            return HttpResponse(json.dumps(dict(errors=[e.error])))
        except Exception as e:
            _remove_preview(preview_path)
            logger.exception(e)
            return HttpResponseBadRequest('failed to generate report: ' + str(e))
    if request.method == 'GET':
        output_format = request.GET.get('outputFormat')
        if output_format not in ('pdf', 'xlsx'):
            return HttpResponseBadRequest('outputFormat parameter missing or invalid')
        key = request.GET.get('key')
        if not key:
            # in case there is a GET request without a key we expect all report data to be available.
            # this is NOT used by ReportBro Designer and only added for the sake of completeness.
            json_data = json.loads(request.body.decode('utf-8'))
            if not isinstance(json_data, dict) or not isinstance(json_data.get('report'), dict) or \
                    not isinstance(json_data.get('data'), dict) or not isinstance(json_data.get('isTestData'), bool):
                return HttpResponseBadRequest('invalid report values')
            report_definition = json_data.get('report')
            data = json_data.get('data')
            is_test_data = json_data.get('isTestData')
            if not isinstance(report_definition, dict) or not isinstance(data, dict):
                return HttpResponseBadRequest('report_definition or data missing')
            return FileResponse(
                io.BytesIO(
                    generate_report(
                        "preview",
                        report_definition,
                        data,
                        output_format,
                        is_test_data=is_test_data,
                    )
                ), filename=f"preview.{output_format}", as_attachment=False
            )
        preview_path = _preview_path(key)
        if preview_path is None:
            return HttpResponseBadRequest('invalid preview key')
        try:
            with open(preview_path, 'rb') as f:
                content = f.read()
        except FileNotFoundError:
            return HttpResponseNotFound('preview not found')
        # A preview is served once: the designer asks for a new one on every
        # change, and nothing else would ever clean it up.
        _remove_preview(preview_path)
        response = HttpResponse(content, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="report_preview.pdf"'
        return response
    return HttpResponseBadRequest('invalid request method')
