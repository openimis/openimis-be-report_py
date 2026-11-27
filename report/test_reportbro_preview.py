"""The ReportBro preview endpoint must only ever serve the previews it wrote.

The designer previews a report in two steps: a PUT renders it into a file and
answers with a key, then a GET with that key returns the file. The key used to
be joined to the temp directory unchecked, so an absolute path or a path with
``..`` made the GET return any file the backend process could read (OP-3352).

A key is now accepted only in the shape the PUT produces, it must resolve
inside the dedicated preview directory, and a preview is deleted once served.
"""
import json
import os
import tempfile
import uuid
from unittest import mock

from django.conf import settings
from rest_framework import status
from rest_framework.test import APITestCase

from core.models.openimis_graphql_test_case import BaseTestContext
from core.test_helpers import create_test_interactive_user, create_test_role

# Restated rather than imported, so the test does not depend on the name the
# implementation gives it.
PREVIEW_DIR = os.path.join(tempfile.gettempdir(), "openimis-report-preview")

MINIMAL_REPORT = {
    # No element: an empty page is still a valid PDF, and a text element
    # would need every style property spelled out.
    "docElements": [],
    "parameters": [],
    "styles": [],
    "version": 4,
    "documentProperties": {
        "pageFormat": "A4",
        "orientation": "portrait",
        "contentHeight": "",
        "marginLeft": "20",
        "marginTop": "20",
        "marginRight": "20",
        "marginBottom": "10",
        "header": False,
        "footer": False,
        "patternLocale": "en",
    },
}


class ReportBroPreviewTestCase(APITestCase):
    URL = None

    @classmethod
    def setUpTestData(cls):
        cls.URL = f"/{settings.SITE_ROOT()}report/reportbro/preview"
        cls.permitted = create_test_interactive_user(
            username="reportPreviewPermitted",
            roles=[
                create_test_role(
                    perm_names=["gql_query_report_perms"], name="ReportPreviewRole"
                ).id
            ],
        )
        cls.permitted_token = BaseTestContext(user=cls.permitted).get_jwt()
        cls.unprivileged = create_test_interactive_user(
            username="reportPreviewUnprivileged",
            roles=[create_test_role(perm_names=[], name="ReportPreviewNoRights").id],
        )
        cls.unprivileged_token = BaseTestContext(user=cls.unprivileged).get_jwt()

    def setUp(self):
        # A file outside the preview directory that no key may ever reach.
        self.secret_content = f"op-3352-secret-{uuid.uuid4().hex}".encode()
        fd, self.secret_path = tempfile.mkstemp(prefix="op3352secret")
        with os.fdopen(fd, "wb") as f:
            f.write(self.secret_content)
        self.addCleanup(self._remove, self.secret_path)

    @staticmethod
    def _remove(path):
        if os.path.lexists(path):
            os.remove(path)

    def _auth(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}

    def _get(self, key, token="permitted"):
        token = self.permitted_token if token == "permitted" else token
        return self.client.get(
            self.URL, {"outputFormat": "pdf", "key": key}, **self._auth(token)
        )

    def _put(self, token="permitted"):
        token = self.permitted_token if token == "permitted" else token
        return self.client.put(
            self.URL,
            data=json.dumps(
                {
                    "outputFormat": "pdf",
                    "report": MINIMAL_REPORT,
                    "data": {},
                    "isTestData": True,
                }
            ),
            content_type="application/json",
            **self._auth(token),
        )

    def _assert_refused(self, key):
        with mock.patch("report.views.open", create=True, wraps=open) as opened:
            response = self._get(key)
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code, key)
        self.assertNotIn(self.secret_content, response.content)
        opened.assert_not_called()

    def test_absolute_path_key_is_refused(self):
        self._assert_refused(self.secret_path)

    def test_relative_path_key_with_dotdot_is_refused(self):
        # Climbs out of the temp directory and back into it, so that before the
        # fix it reached the secret file through `..`.
        tempdir = tempfile.gettempdir()
        key = os.path.join(
            "..", os.path.basename(tempdir), os.path.basename(self.secret_path)
        )
        self._assert_refused(key)

    def test_key_not_in_temp_file_format_is_refused(self):
        for key in (
            os.path.basename(self.secret_path).replace("op3352secret", "x"),
            "tmp/../" + os.path.basename(self.secret_path),
            "tmpabc\n",
            "tmpabc.pdf",
            "tmp",
        ):
            self._assert_refused(key)

    def test_symlink_escaping_preview_directory_is_refused(self):
        # A well-formed key that resolves outside the preview directory.
        os.makedirs(PREVIEW_DIR, exist_ok=True)
        link = os.path.join(PREVIEW_DIR, f"tmpop3352{uuid.uuid4().hex}")
        os.symlink(self.secret_path, link)
        self.addCleanup(self._remove, link)
        response = self._get(os.path.basename(link))
        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND),
        )
        self.assertNotIn(self.secret_content, response.content)

    def test_unknown_well_formed_key_is_not_found(self):
        response = self._get(f"tmpop3352{uuid.uuid4().hex}")
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_key_from_put_returns_preview_once(self):
        put = self._put()
        self.assertEqual(status.HTTP_200_OK, put.status_code, put.content)
        body = put.content.decode()
        self.assertTrue(body.startswith("key:"), body)
        key = body[len("key:"):]
        path = os.path.join(PREVIEW_DIR, key)
        self.addCleanup(self._remove, path)
        self.assertTrue(os.path.isfile(path), "preview not written to its directory")

        response = self._get(key)
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertTrue(response.content.startswith(b"%PDF"))
        # Served once, then gone: the file must not linger in the temp directory.
        self.assertFalse(os.path.exists(path))
        self.assertEqual(status.HTTP_404_NOT_FOUND, self._get(key).status_code)

    def test_anonymous_get_is_unauthorized(self):
        response = self._get(f"tmpop3352{uuid.uuid4().hex}", token=None)
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_anonymous_put_is_unauthorized(self):
        response = self._put(token=None)
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_missing_rights_is_forbidden(self):
        response = self._get(
            f"tmpop3352{uuid.uuid4().hex}", token=self.unprivileged_token
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
