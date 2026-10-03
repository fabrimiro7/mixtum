from unittest.mock import patch

from django.db import DatabaseError
from django.test import SimpleTestCase


class HealthTests(SimpleTestCase):
    def test_live_does_not_touch_database(self):
        with patch("mixtum_core.health.connections") as connections:
            response = self.client.get("/health/live/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok\n")
        self.assertEqual(response["Cache-Control"], "no-store")
        connections.__getitem__.assert_not_called()

    def test_ready_succeeds_when_database_answers(self):
        with patch("mixtum_core.health.connections") as connections:
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok\n")
        connections.__getitem__.assert_called_once_with("default")

    def test_ready_fails_without_exposing_database_details(self):
        with patch("mixtum_core.health.connections") as connections:
            connections.__getitem__.return_value.cursor.side_effect = DatabaseError("private host and password")
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"unavailable\n")
        self.assertNotIn(b"private", response.content)
        self.assertEqual(response["Cache-Control"], "no-store")
