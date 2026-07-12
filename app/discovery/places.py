"""Google Places discovery — port of IABotz GooglePlacesService."""
from __future__ import annotations

import math
import time
from typing import Any
from urllib.parse import urlencode

import requests

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
NEARBY_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"

GENERIC_TYPES = {
    "point_of_interest",
    "establishment",
    "premise",
    "geocode",
    "political",
}


class GooglePlacesService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()

    def search(
        self,
        keyword: str,
        location: str = "",
        max_results: int = 60,
        lat: float | None = None,
        lng: float | None = None,
        radius_km: int = 15,
        on_progress=None,
    ) -> list[dict]:
        max_results = min(max(max_results, 1), 1000)
        use_nearby = lat is not None and lng is not None

        if not use_nearby and max_results > 60 and location:
            coords = self.geocode(location)
            if coords:
                lat, lng = coords["lat"], coords["lng"]
                use_nearby = True
                radius_km = max(radius_km, 10)

        if on_progress:
            on_progress("Buscando no Google Places…")

        if max_results > 60 and use_nearby:
            raw = self._grid_search(keyword, lat, lng, radius_km, max_results, on_progress)
        elif use_nearby:
            raw = self._nearby_search(keyword, lat, lng, radius_km, max_results)
        else:
            raw = self._text_search(keyword, location, max_results)

        query = keyword if use_nearby else (f"{keyword} em {location}" if location else keyword)
        return self._normalize(raw, query, max_results, on_progress)

    def geocode(self, location: str) -> dict | None:
        data = self._get(GEOCODING_URL, {"address": location, "key": self.api_key})
        if data.get("status") != "OK":
            return None
        loc = (data.get("results") or [{}])[0].get("geometry", {}).get("location")
        if not loc:
            return None
        return {"lat": float(loc["lat"]), "lng": float(loc["lng"])}

    def test_connection(self) -> dict:
        try:
            data = self._get(
                TEXT_SEARCH_URL,
                {"query": "cafe in Sao Paulo", "key": self.api_key, "language": "pt-BR"},
            )
            status = data.get("status")
            if status in ("OK", "ZERO_RESULTS"):
                return {"success": True, "message": f"Places OK ({status})"}
            return {
                "success": False,
                "message": f"{status}: {data.get('error_message', '')}".strip(),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _text_search(self, keyword: str, location: str, max_results: int) -> list:
        query = f"{keyword} em {location}" if location else keyword
        return self._paginated(
            TEXT_SEARCH_URL,
            {"query": query, "key": self.api_key, "language": "pt-BR"},
            max_results,
        )

    def _nearby_search(
        self, keyword: str, lat: float, lng: float, radius_km: int, max_results: int
    ) -> list:
        return self._paginated(
            NEARBY_SEARCH_URL,
            {
                "keyword": keyword,
                "location": f"{lat},{lng}",
                "radius": min(radius_km * 1000, 50000),
                "key": self.api_key,
                "language": "pt-BR",
            },
            max_results,
        )

    def _grid_search(
        self, keyword, lat, lng, radius_km, max_results, on_progress=None
    ) -> list:
        target_raw = min(int(math.ceil(max_results * 2.0)), 1500)
        grid_n = max(1, min(8, int(math.ceil(math.sqrt(target_raw / 60)))))
        cell_r = max(1, int(math.ceil((radius_km / grid_n) * 1.2)))
        points = self._grid_points(lat, lng, radius_km, grid_n)
        by_id: dict[str, Any] = {}
        for i, pt in enumerate(points):
            if len(by_id) >= target_raw:
                break
            if on_progress and i % 4 == 0:
                on_progress(f"Grid Places {i+1}/{len(points)} ({len(by_id)} lugares)")
            results = self._paginated(
                NEARBY_SEARCH_URL,
                {
                    "keyword": keyword,
                    "location": f"{pt['lat']},{pt['lng']}",
                    "radius": min(cell_r * 1000, 50000),
                    "key": self.api_key,
                    "language": "pt-BR",
                },
                60,
            )
            for r in results:
                pid = r.get("place_id") or ""
                if pid:
                    by_id[pid] = r
        return list(by_id.values())[: max_results * 3]

    def _grid_points(self, center_lat, center_lng, total_km, grid_n):
        if grid_n == 1:
            return [{"lat": center_lat, "lng": center_lng}]
        d_lat = 1.0 / 111.32
        d_lng = 1.0 / (111.32 * math.cos(math.radians(center_lat)))
        spacing = (2.0 * total_km) / grid_n
        points = []
        for i in range(grid_n):
            for j in range(grid_n):
                olat = -total_km + spacing * (i + 0.5)
                olng = -total_km + spacing * (j + 0.5)
                points.append(
                    {
                        "lat": round(center_lat + olat * d_lat, 6),
                        "lng": round(center_lng + olng * d_lng, 6),
                    }
                )
        return points

    def _paginated(self, base_url: str, params: dict, max_results: int) -> list:
        all_results = []
        page_token = None
        for page in range(3):
            p = dict(params)
            if page_token:
                time.sleep(1.2)
                p["pagetoken"] = page_token
            data = self._get(base_url, p)
            status = data.get("status")
            if status == "REQUEST_DENIED":
                raise RuntimeError(
                    f"Google Places REQUEST_DENIED: {data.get('error_message', '')}"
                )
            if status not in ("OK", "ZERO_RESULTS"):
                break
            for r in data.get("results") or []:
                if len(all_results) >= max_results:
                    break
                all_results.append(r)
            page_token = data.get("next_page_token")
            if not page_token or len(all_results) >= max_results:
                break
        return all_results

    def _place_details(self, place_id: str) -> dict:
        data = self._get(
            DETAILS_URL,
            {
                "place_id": place_id,
                "fields": "formatted_phone_number,international_phone_number,website,formatted_address",
                "key": self.api_key,
                "language": "pt-BR",
            },
        )
        return data.get("result") or {}

    def _normalize(self, raw, query, max_results, on_progress=None) -> list[dict]:
        prospects = []
        details_limit = min(len(raw), max(200, max_results))
        details_called = 0
        for place in raw:
            if len(prospects) >= max_results:
                break
            phone = self._extract_phone(place)
            website = place.get("website") or ""
            address = place.get("formatted_address") or place.get("vicinity") or ""
            place_id = place.get("place_id") or ""
            if (not phone or not website) and place_id and details_called < details_limit:
                details = self._place_details(place_id)
                details_called += 1
                phone = phone or self._extract_phone(details)
                website = website or details.get("website") or ""
                address = address or details.get("formatted_address") or ""
            types = place.get("types") or []
            category = next((t for t in types if t not in GENERIC_TYPES), types[0] if types else "")
            prospects.append(
                {
                    "nome": place.get("name") or "",
                    "telefone": phone or "",
                    "site": website,
                    "endereco": address,
                    "nota": float(place["rating"]) if place.get("rating") is not None else None,
                    "avaliacoes": int(place.get("user_ratings_total") or 0),
                    "place_id": place_id,
                    "categoria": category,
                    "maps_url": f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                    if place_id
                    else "",
                    "query": query,
                    "engine": "google_places",
                }
            )
            if on_progress and len(prospects) % 10 == 0:
                on_progress(f"Normalizados {len(prospects)} lugares")
        return prospects

    @staticmethod
    def _extract_phone(obj: dict) -> str:
        return (
            obj.get("international_phone_number")
            or obj.get("formatted_phone_number")
            or obj.get("phone")
            or ""
        )

    def _get(self, url: str, params: dict) -> dict:
        r = self.session.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
