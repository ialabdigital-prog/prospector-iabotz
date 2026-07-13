from __future__ import annotations

import importlib.util
import json
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from app.composio_gmail import gmail_status


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class ReleaseSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deploy = load_module(
            "deploy_reference", "skills/deploy-aapanel/references/deploy.py"
        )
        cls.whatsapp = load_module(
            "whatsapp_reference",
            "skills/proposta-whatsapp/references/proposta_whatsapp.py",
        )

    def test_public_subdomain_prefers_original_hostname(self):
        label = self.deploy.public_subdomain(
            "internal-long-lead-slug", "https://www.Acme-Clinic.example/path"
        )
        self.assertEqual(label, "acme-clinic")

    def test_public_subdomain_obeys_dns_label_limit(self):
        label = self.deploy.public_subdomain("a" * 100)
        self.assertLessEqual(len(label), 63)
        self.assertRegex(label, r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")

    def test_evolution_api_uses_top_level_text(self):
        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return b"{}"

        def fake_urlopen(request, timeout=0):
            captured.update(json.loads(request.data))
            return Response()

        config = {
            "envio": {
                "whatsapp": {
                    "evolution_api": {
                        "url": "https://api.example.com",
                        "api_key": "test-only",
                        "instance": "demo",
                    }
                }
            }
        }
        with patch.object(self.whatsapp.urllib.request, "urlopen", fake_urlopen):
            result = self.whatsapp.send_via_evolution_api(
                config, "5511999999999", "mensagem de teste"
            )

        self.assertTrue(result["success"])
        self.assertEqual(captured["text"], "mensagem de teste")
        self.assertNotIn("textMessage", captured)

    def test_composio_requires_an_active_gmail_account(self):
        client = SimpleNamespace(
            connected_accounts=SimpleNamespace(
                list=lambda **_kwargs: SimpleNamespace(items=[])
            )
        )
        with patch("app.composio_gmail._client", return_value=client):
            status = gmail_status("test-key", "configured-user")
        self.assertFalse(status["connected"])
        self.assertIn("Nenhuma conta Gmail ACTIVE", status["reason"])

    def test_composio_uses_the_only_active_account_on_legacy_id_mismatch(self):
        account = SimpleNamespace(id="ca_test", user_id="actual-user")
        client = SimpleNamespace(
            connected_accounts=SimpleNamespace(
                list=lambda **_kwargs: SimpleNamespace(items=[account])
            )
        )
        with patch("app.composio_gmail._client", return_value=client):
            status = gmail_status("test-key", "legacy-user")
        self.assertTrue(status["connected"])
        self.assertTrue(status["configured_user_mismatch"])
        self.assertEqual(status["user_id"], "actual-user")


if __name__ == "__main__":
    unittest.main()
