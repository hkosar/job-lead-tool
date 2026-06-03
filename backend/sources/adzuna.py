"""Adzuna adapter — FREE. Register an app at https://developer.adzuna.com/ to get
App ID + App Key. Docs: https://developer.adzuna.com/docs/search
"""
from __future__ import annotations
from .base import (SourceAdapter, CredField, Lead, get_json,
                   role_query, location_query)


class AdzunaAdapter(SourceAdapter):
    key = "adzuna"
    name = "Adzuna"
    tier = "Free"
    monthly_cost = 0
    fields = [CredField("app_id", "App ID"), CredField("app_key", "App Key")]

    def search(self, profile, creds=None):
        creds = creds or {}
        app_id, app_key = creds.get("app_id"), creds.get("app_key")
        if not app_id or not app_key:
            return []
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": role_query(profile),
            "results_per_page": 25,
            "content-type": "application/json",
        }
        where = location_query(profile)
        if where:
            params["where"] = where
        data = get_json("https://api.adzuna.com/v1/api/jobs/us/search/1", params=params)
        if not data:
            return []
        leads = []
        for r in data.get("results", []):
            sal = ""
            lo, hi = r.get("salary_min"), r.get("salary_max")
            if lo and hi:
                sal = f"${int(lo/1000)}k–${int(hi/1000)}k"
            elif lo:
                sal = f"${int(lo/1000)}k+"
            leads.append(Lead(
                title=r.get("title", "").strip(),
                company=(r.get("company") or {}).get("display_name", "").strip(),
                location=(r.get("location") or {}).get("display_name", "").strip(),
                salary=sal,
                url=r.get("redirect_url", "#"),
                description=(r.get("description", "") or "")[:600],
                source_key="adzuna", source="Adzuna", ats="unknown", portal="unknown",
            ))
        return leads
