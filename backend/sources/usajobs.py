"""USAJOBS adapter — FREE. Request a key at https://developer.usajobs.gov/.
Requires an 'Authorization-Key' header AND a 'User-Agent' set to your contact email.
Docs: https://developer.usajobs.gov/api-reference/get-api-search
"""
from __future__ import annotations
from .base import (SourceAdapter, CredField, Lead, get_json,
                   role_query, location_query)


class UsaJobsAdapter(SourceAdapter):
    key = "usajobs"
    name = "USAJOBS"
    tier = "Free"
    monthly_cost = 0
    fields = [CredField("email", "Contact email", "used as User-Agent"),
              CredField("api_key", "API Key")]

    def search(self, profile, creds=None):
        creds = creds or {}
        email, api_key = creds.get("email"), creds.get("api_key")
        if not email or not api_key:
            return []
        headers = {"Host": "data.usajobs.gov", "User-Agent": email,
                   "Authorization-Key": api_key}
        params = {"Keyword": role_query(profile), "ResultsPerPage": 25}
        loc = location_query(profile)
        if loc:
            params["LocationName"] = loc
        data = get_json("https://data.usajobs.gov/api/search", params=params, headers=headers)
        if not data:
            return []
        items = (data.get("SearchResult") or {}).get("SearchResultItems", [])
        leads = []
        for it in items:
            d = it.get("MatchedObjectDescriptor") or {}
            pay = (d.get("PositionRemuneration") or [{}])[0]
            sal = ""
            lo, hi = pay.get("MinimumRange"), pay.get("MaximumRange")
            if lo and hi:
                try:
                    sal = f"${int(float(lo)/1000)}k–${int(float(hi)/1000)}k"
                except Exception:
                    sal = ""
            locs = d.get("PositionLocationDisplay") or ", ".join(
                l.get("LocationName", "") for l in (d.get("PositionLocation") or []))
            leads.append(Lead(
                title=d.get("PositionTitle", "").strip(),
                company=d.get("OrganizationName", "").strip(),
                location=locs,
                salary=sal,
                url=d.get("PositionURI", "#"),
                description=((d.get("UserArea") or {}).get("Details", {}) or {}).get("JobSummary", "")[:600],
                source_key="usajobs", source="USAJOBS", ats="custom", portal="unknown",
            ))
        return leads
