import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient

from base_modules.user_manager.models import User
from .models import Attachment


class AttachmentAuthorizationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", "owner@example.test", password="unused")
        self.other = User.objects.create_user("other", "other@example.test", password="unused")
        self.owned = Attachment.objects.create(author=self.owner, title="Owned")
        self.foreign = Attachment.objects.create(author=self.other, title="Foreign")
        self.client = APIClient()

    def test_anonymous_requests_are_rejected(self):
        requests = (
            ("get", "/api/attachments/list/", None),
            ("get", f"/api/attachments/details/{self.owned.pk}/", None),
            ("get", f"/api/attachments/download/{self.owned.pk}/", None),
            ("post", "/api/attachments/create/", {"title": "New"}),
            ("patch", f"/api/attachments/update/{self.owned.pk}/", {"title": "Changed"}),
            ("delete", f"/api/attachments/delete/{self.owned.pk}/", None),
        )
        for method, url, data in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, data=data)
                self.assertIn(response.status_code, (401, 403))
        self.owned.refresh_from_db()
        self.assertEqual(self.owned.title, "Owned")

    def test_list_and_object_operations_are_owner_scoped(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get("/api/attachments/list/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [self.owned.pk])

        foreign_urls = (
            ("get", f"/api/attachments/details/{self.foreign.pk}/", None),
            ("get", f"/api/attachments/download/{self.foreign.pk}/", None),
            ("patch", f"/api/attachments/update/{self.foreign.pk}/", {"title": "Changed"}),
            ("delete", f"/api/attachments/delete/{self.foreign.pk}/", None),
        )
        for method, url, data in foreign_urls:
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(url, data=data).status_code, 404)
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.title, "Foreign")

        self.assertEqual(self.client.get(f"/api/attachments/details/{self.owned.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/attachments/download/{self.owned.pk}/").status_code, 404)
        self.assertEqual(self.client.patch(
            f"/api/attachments/update/{self.owned.pk}/", {"title": "Updated", "author": self.other.pk}
        ).status_code, 200)
        self.owned.refresh_from_db()
        self.assertEqual(self.owned.title, "Updated")
        self.assertEqual(self.owned.author_id, self.owner.pk)
        self.assertEqual(self.client.delete(f"/api/attachments/delete/{self.owned.pk}/").status_code, 204)
        self.assertFalse(Attachment.objects.filter(pk=self.owned.pk).exists())

    def test_create_sets_owner_and_validation_errors_are_not_masked(self):
        self.client.force_authenticate(user=self.owner)
        created = self.client.post("/api/attachments/create/", {"title": "New", "author": self.other.pk})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(Attachment.objects.get(pk=created.data["Attachment"]["id"]).author_id, self.owner.pk)
        invalid = self.client.post("/api/attachments/create/", {"title": "x" * 201})
        self.assertEqual(invalid.status_code, 400)

    def test_file_url_is_private_endpoint_and_download_checks_owner(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            self.client.force_authenticate(user=self.owner)
            uploaded = SimpleUploadedFile("private.txt", b"private bytes", content_type="text/plain")
            created = self.client.post(
                "/api/attachments/create/", {"title": "Private", "file": uploaded}, format="multipart"
            )
            self.assertEqual(created.status_code, 201)
            attachment_id = created.data["Attachment"]["id"]
            url = created.data["Attachment"]["file"]
            self.assertEqual(urlsplit(url).path, f"/api/attachments/download/{attachment_id}/")
            self.assertNotIn("/media/", url)

            detail = self.client.get(f"/api/attachments/details/{attachment_id}/")
            self.assertEqual(detail.data["file"], url)
            updated = self.client.patch(f"/api/attachments/update/{attachment_id}/", {"title": "Renamed"})
            self.assertEqual(updated.data["Attachment"]["file"], url)
            response = self.client.get(urlsplit(url).path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"private bytes")
            self.assertIn("attachment;", response["Content-Disposition"])
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            response.close()

            self.client.force_authenticate(user=self.other)
            self.assertEqual(self.client.get(urlsplit(url).path).status_code, 404)
            self.client.force_authenticate(user=None)
            self.assertIn(self.client.get(urlsplit(url).path).status_code, (401, 403))

    def test_upload_limit_applies_before_create_or_update_storage_write(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory), \
                patch("base_modules.attachment.serializers.MAX_ATTACHMENT_BYTES", 8):
            self.client.force_authenticate(user=self.owner)
            count_before = Attachment.objects.count()
            large_create = self.client.post(
                "/api/attachments/create/",
                {"file": SimpleUploadedFile("large.bin", b"x" * 9)},
                format="multipart",
            )
            self.assertEqual(large_create.status_code, 400)
            self.assertEqual(Attachment.objects.count(), count_before)

            large_update = self.client.patch(
                f"/api/attachments/update/{self.owned.pk}/",
                {"file": SimpleUploadedFile("large.bin", b"x" * 9)},
                format="multipart",
            )
            self.assertEqual(large_update.status_code, 400)
            self.owned.refresh_from_db()
            self.assertFalse(self.owned.file)
            self.assertEqual(list(Path(directory).iterdir()), [])

            accepted = self.client.post(
                "/api/attachments/create/",
                {"file": SimpleUploadedFile("limit.bin", b"x" * 8)},
                format="multipart",
            )
            self.assertEqual(accepted.status_code, 201)
