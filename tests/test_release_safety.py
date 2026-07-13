from __future__ import annotations

import importlib.util
import json
import unittest
from types import SimpleNamespace
from datetime import datetime, timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from app.composio_gmail import gmail_status
from app.followups import business_days_since
from app.design_catalog import fallback_brief, normalize_llm_brief
from app.proposal_readiness import check_proposal_readiness


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

    def test_followup_waits_three_business_days(self):
        self.assertEqual(
            business_days_since("2026-07-10T10:00:00", datetime(2026, 7, 15, 10, 0, 0)),
            3,
        )

    def test_followup_is_created_only_once_per_channel(self):
        import app.db as database
        from app.followups import followup_candidates, mark_followup

        with TemporaryDirectory() as folder:
            db_path = Path(folder) / "test.db"
            with patch.object(database, "DB_FILE", db_path), patch.object(
                database, "LEADS_FILE", Path(folder) / "missing.md"
            ):
                database.init_db()
                sent = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
                with database.db() as conn:
                    conn.execute(
                        """INSERT INTO leads (slug,nome,email,status,emailSentAt)
                           VALUES ('lead-test','Lead Test','lead@example.com','proposta',?)""",
                        (sent,),
                    )
                self.assertTrue(followup_candidates("lead-test")[0]["due_email"])
                mark_followup("lead-test", "email")
                self.assertEqual(followup_candidates("lead-test"), [])

    def test_creative_brief_never_repeats_the_same_style_layout_pair(self):
        previous = [{"style_id": "luxury", "layout_id": "offset-editorial"}]
        brief = normalize_llm_brief(
            {"style_id": "luxury", "layout_id": "offset-editorial"},
            {"nome": "Escritório Exemplo", "nicho": "advogados"},
            previous,
        )
        self.assertNotEqual((brief["style_id"], brief["layout_id"]), ("luxury", "offset-editorial"))

    def test_same_niche_rotates_directions_by_brand(self):
        pairs = {
            (brief["style_id"], brief["layout_id"])
            for brief in (
                fallback_brief({"nome": name, "nicho": "advogados"})
                for name in ("Alfa Legal", "Bravo Advocacia", "Costa Jurídico", "Delta Law")
            )
        }
        self.assertGreater(len(pairs), 1)

    def test_outreach_is_blocked_when_proposal_contains_placeholders(self):
        import app.proposal_readiness as readiness

        with TemporaryDirectory() as folder, patch.object(readiness, "SITES_DIR", Path(folder)):
            site = Path(folder) / "lead-test"
            assets = site / "assets"
            assets.mkdir(parents=True)
            (site / "index.html").write_text("x" * 2_000)
            (assets / "before.png").write_bytes(b"x" * 12_000)
            (assets / "after.png").write_bytes(b"x" * 12_000)
            (site / "proposta.html").write_text(
                "<div class='card-img placeholder'>inserir screenshot</div>"
                "<img src='assets/before.png'><img src='assets/after.png'>" + "x" * 2_000
            )
            result = check_proposal_readiness("lead-test", verify_public=False)
            self.assertFalse(result["ready"])
            self.assertIn("a proposta ainda contém placeholders", result["errors"])

    def test_complete_local_proposal_is_ready(self):
        import app.proposal_readiness as readiness

        with TemporaryDirectory() as folder, patch.object(readiness, "SITES_DIR", Path(folder)):
            site = Path(folder) / "lead-test"
            assets = site / "assets"
            assets.mkdir(parents=True)
            (site / "index.html").write_text("x" * 2_000)
            (assets / "before.png").write_bytes(b"x" * 12_000)
            (assets / "after.png").write_bytes(b"x" * 12_000)
            (site / "proposta.html").write_text(
                "<img src='assets/before.png'><img src='assets/after.png'>" + "x" * 2_000
            )
            self.assertTrue(check_proposal_readiness("lead-test", verify_public=False)["ready"])


if __name__ == "__main__":
    unittest.main()
