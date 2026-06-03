"""Google Jobs via SerpApi — PAID (~$75/mo for 5k searches).
Key: https://serpapi.com/manage-api-key  Engine: https://serpapi.com/google-jobs-api
NOTE: Google Jobs does NOT include Indeed. Use the Indeed vendor adapter for that.
"""
from __future__ import annotations
from .base import (SourceAdapter, CredField, Lead, get_json,
                   role_query, location_query)


class SerpApiGoogleJobsAdapter(SourceAdapter):
    key = "googlejobs"
    name = "Google Jobs (SerpApi)"
    tier = "Paid"
    monthly_cost = 75
    fields = [CredField("api_key", "SerpApi API Key")]

    def search(self, profile, creds=None):
        creds = creds or {}
        api_key = creds.get("api_key")
        if not api_key:
            return []
        params = {"engine": "google_jobs", "q": role_query(profile), "api_key": api_key}
        loc = location_query(profile)
        if loc:
            params["location"] = loc
        data = get_json("https://serpapi.com/search.json", params=params)
        if not data:
            return []
        leads = []
        for j in data.get("jobs_results", []):
            # find a real apply link if present
            url = "#"
            for opt in (j.get("apply_options") or []):
                if opt.get("link"):
                    url = opt["link"]; break
            if url == "#":
                url = j.get("share_link", "#")
            salary = ""
            for ext in (j.get("detected_extensions") or {}).items():
                if ext[0] == "salary":
                    salary = ext[1]
            leads.append(Lead(
                title=j.get("title", "").strip(),
                company=j.get("company_name", "").strip(),
                location=j.get("location", "").strip(),
                salary=salary,
                url=url,
                description=(j.get("description", "") or "")[:600],
                source_key="googlejobs", source="Google Jobs", ats="unknown", portal="unknown",
            ))
        return leads
