"""Apify Google Maps Scraper — fallback engine (same actor as IABotz SaaS)."""
from __future__ import annotations

import time
from typing import Callable

import requests

ACTOR_ID = "iJcISG5H8FJUSRoVA"
API_BASE = "https://api.apify.com/v2"


class ApifyGoogleMapsService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()

    def test_connection(self) -> dict:
        try:
            r = self.session.get(
                f"{API_BASE}/acts/{ACTOR_ID}",
                params={"token": self.api_key},
                timeout=15,
            )
            if r.status_code == 401:
                return {"success": False, "message": "Chave Apify inválida"}
            if r.status_code != 200:
                return {"success": False, "message": f"HTTP {r.status_code}"}
            data = r.json().get("data") or {}
            name = data.get("name") or data.get("title") or "Google Maps Scraper"
            return {"success": True, "message": f"Apify OK — {name}", "actor_name": name}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def start_search(self, keyword: str, max_results: int = 50, location: str = "") -> str:
        body = {
            "keywords": [keyword],
            "max_result_per_keyword": min(max(max_results, 1), 500),
        }
        if location:
            body["location"] = location
        result = self._request(
            "POST",
            f"/acts/{ACTOR_ID}/runs",
            params={"token": self.api_key},
            json_body=body,
        )
        run_id = (result.get("data") or {}).get("id")
        if not run_id:
            raise RuntimeError(f"Apify sem runId: {result}")
        return str(run_id)

    def get_run_status(self, run_id: str) -> dict:
        result = self._request(
            "GET",
            f"/actor-runs/{run_id}",
            params={"token": self.api_key},
        )
        data = result.get("data") or {}
        return {
            "status": data.get("status"),
            "item_count": (data.get("stats") or {}).get("itemCount") or 0,
        }

    def get_run_results(self, run_id: str, query: str = "") -> list[dict]:
        result = self._request(
            "GET",
            f"/actor-runs/{run_id}/dataset/items",
            params={"token": self.api_key, "clean": 1},
        )
        items = result if isinstance(result, list) else result.get("items") or []
        prospects = []
        for item in items:
            prospects.append(
                {
                    "nome": item.get("title") or item.get("name") or "",
                    "telefone": item.get("phoneNumber") or item.get("phone") or "",
                    "site": item.get("website") or "",
                    "endereco": item.get("address") or "",
                    "nota": _float(item.get("rating") or item.get("totalScore")),
                    "avaliacoes": _int(item.get("ratingCount") or item.get("reviewsCount")),
                    "place_id": item.get("placeId") or "",
                    "categoria": _category(item),
                    "maps_url": item.get("url") or "",
                    "query": query,
                    "engine": "apify",
                }
            )
        return prospects

    def search_sync(
        self,
        keyword: str,
        location: str = "",
        max_results: int = 50,
        on_progress: Callable[[str], None] | None = None,
        timeout_s: int = 600,
    ) -> list[dict]:
        if on_progress:
            on_progress("Iniciando Apify Google Maps Scraper…")
        run_id = self.start_search(keyword, max_results, location)
        if on_progress:
            on_progress(f"Apify run {run_id}")
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            st = self.get_run_status(run_id)
            status = (st.get("status") or "").upper()
            if on_progress:
                on_progress(f"Apify {status} ({st.get('item_count', 0)} items)")
            if status == "SUCCEEDED":
                return self.get_run_results(run_id, f"{keyword} em {location}".strip())
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise RuntimeError(f"Apify run {status}")
            time.sleep(5)
        raise TimeoutError("Apify timeout")

    def _request(self, method, path, params=None, json_body=None):
        r = self.session.request(
            method,
            API_BASE + path,
            params=params,
            json=json_body,
            timeout=60,
        )
        r.raise_for_status()
        if not r.content:
            return {}
        return r.json()


def _float(v):
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def _int(v):
    try:
        return int(v or 0)
    except Exception:
        return 0


def _category(item: dict) -> str:
    t = item.get("type") or item.get("categoryName")
    if isinstance(t, list):
        return t[0] if t else ""
    return str(t or "")
