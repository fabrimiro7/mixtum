import unittest

from django.conf import settings

if "plugins.documents" not in settings.INSTALLED_APPS:
    raise unittest.SkipTest("Documents è testato con la composizione prodotto dedicata.")

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from base_modules.user_manager.models import User
from base_modules.workspace.models import Workspace, WorkspaceUser

from plugins.documents.models import Document, DocumentPermission
from plugins.documents.pdf import validate_area


class DocumentsApiTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(workspace_name="Documents")
        self.other = Workspace.objects.create(workspace_name="Other")
        self.owner = User.objects.create_user("owner-docs", "owner-docs@example.test")
        self.member = User.objects.create_user("member-docs", "member-docs@example.test")
        self.foreign = User.objects.create_user("foreign-docs", "foreign-docs@example.test")
        WorkspaceUser.objects.create(user=self.owner, workspace=self.workspace, role=WorkspaceUser.OWNER)
        WorkspaceUser.objects.create(user=self.member, workspace=self.workspace)
        WorkspaceUser.objects.create(user=self.foreign, workspace=self.other)
        self.header = {"HTTP_X_WORKSPACE_ID": str(self.workspace.pk)}
        self.client = APIClient()

    def upload(self, user, *, visibility="workspace"):
        self.client.force_authenticate(user)
        return self.client.post("/api/plugin-documents/documents/", {
            "title": "Specifica", "visibility": visibility,
            "file": SimpleUploadedFile("spec.txt", b"Pagina completa e senza troncamenti.", content_type="text/plain"),
        }, format="multipart", **self.header)

    def test_upload_extract_and_cross_workspace_denial(self):
        response = self.upload(self.owner)
        self.assertEqual(response.status_code, 201, response.data)
        document_id = response.data["id"]
        version_id = response.data["versions"][0]["id"]
        extracted = self.client.post(
            f"/api/plugin-documents/documents/{document_id}/versions/{version_id}/extract/",
            {}, format="json", **self.header,
        )
        self.assertEqual(extracted.status_code, 200, extracted.data)
        self.assertIn("senza troncamenti", extracted.data["chunks"][0]["text"])
        self.client.force_authenticate(self.foreign)
        self.assertEqual(self.client.get(
            f"/api/plugin-documents/documents/{document_id}/", **self.header,
        ).status_code, 403)

    def test_restricted_document_requires_explicit_permission(self):
        response = self.upload(self.owner, visibility="restricted")
        document = Document.objects.get(pk=response.data["id"])
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get("/api/plugin-documents/documents/", **self.header).data, [])
        DocumentPermission.objects.create(document=document, user=self.member, can_run=False)
        listed = self.client.get("/api/plugin-documents/documents/", **self.header)
        self.assertEqual(len(listed.data), 1)
        version_id = document.versions.get().pk
        denied = self.client.post(
            f"/api/plugin-documents/documents/{document.pk}/versions/{version_id}/extract/",
            {}, format="json", **self.header,
        )
        self.assertEqual(denied.status_code, 403)

    def test_invalid_pdf_area_never_falls_back_to_full_page(self):
        for area in (
            {"x": 0, "y": 0, "width": 0, "height": 1},
            {"x": .8, "y": 0, "width": .3, "height": 1},
            {"x": 0, "y": 0, "width": 1},
        ):
            with self.assertRaises(Exception):
                validate_area(area)

    def test_pdf_processes_all_pages_and_area_without_silent_fallback(self):
        import pymupdf as fitz

        pdf = fitz.open()
        for index in range(6):
            page = pdf.new_page(width=600, height=800)
            page.insert_text((40, 80), f"LEFT-{index + 1}")
            page.insert_text((420, 80), f"RIGHT-{index + 1}")
        upload = SimpleUploadedFile("six-pages.pdf", pdf.tobytes(), content_type="application/pdf")
        pdf.close()
        self.client.force_authenticate(self.owner)
        response = self.client.post("/api/plugin-documents/documents/", {
            "title": "Sei pagine", "visibility": "workspace", "file": upload,
        }, format="multipart", **self.header)
        self.assertEqual(response.status_code, 201, response.data)
        document_id = response.data["id"]
        version_id = response.data["versions"][0]["id"]
        full = self.client.post(
            f"/api/plugin-documents/documents/{document_id}/versions/{version_id}/extract/",
            {}, format="json", **self.header,
        )
        self.assertEqual(full.status_code, 200, full.data)
        self.assertEqual(len(full.data["chunks"]), 6)
        area = self.client.post(
            f"/api/plugin-documents/documents/{document_id}/versions/{version_id}/extract/",
            {"pages": [1], "area": {"x": 0, "y": 0, "width": .5, "height": 1}},
            format="json", **self.header,
        )
        self.assertIn("LEFT-1", area.data["chunks"][0]["text"])
        self.assertNotIn("RIGHT-1", area.data["chunks"][0]["text"])
