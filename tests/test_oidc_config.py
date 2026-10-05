import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OidcLocalConfigTests(unittest.TestCase):
    def test_public_clients_are_distinct_pkce_only_and_local(self):
        realm = json.loads((ROOT / "docker/keycloak/realm-mixtum.json").read_text())
        clients = {client["clientId"]: client for client in realm["clients"]}
        self.assertEqual(set(clients), {"mixtum-console", "mixtum-public"})
        for name, port in (("mixtum-console", 4200), ("mixtum-public", 4300)):
            with self.subTest(client=name):
                client = clients[name]
                self.assertTrue(client["publicClient"])
                self.assertTrue(client["standardFlowEnabled"])
                self.assertFalse(client["implicitFlowEnabled"])
                self.assertFalse(client["directAccessGrantsEnabled"])
                self.assertEqual(client["attributes"]["pkce.code.challenge.method"], "S256")
                self.assertEqual(client["redirectUris"], [
                    f"http://127.0.0.1:{port}/", f"http://localhost:{port}/",
                ])
                self.assertEqual(client["webOrigins"], [
                    f"http://127.0.0.1:{port}", f"http://localhost:{port}",
                ])
                self.assertNotIn("secret", client)
                self.assertIn("basic", client["defaultClientScopes"])
                self.assertEqual(
                    client["protocolMappers"][0]["config"]["included.custom.audience"], "mixtum-api",
                )


if __name__ == "__main__":
    unittest.main()
