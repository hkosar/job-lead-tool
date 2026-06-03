"""Lever adapter — FREE, KEYLESS. Public postings JSON, no auth:
  GET https://api.lever.co/v0/postings/{company}?mode=json
Company slugs come from the candidate's seed/dream organizations (profile 'dream').
"""
from __future__ import annotations
from .base import (SourceAdapter, Lead, get_json, org_slugs,
                   all_role_terms, matches_role, strip_html)


class LeverAdapter(SourceAdapter):
    key = "lever"
    name = "Lever boards"
    tier = "Free"
    monthly_cost = 0
    keyless = True

    def search(self, profile, creds=None):
        terms = all_role_terms(profile)
        leads = []
        for slug in org_slugs(profile)[:12]:
            data = get_json(f"https://api.lever.co/v0/postings/{slug}",
                            params={"mode": "json"})
            if not isinstance(data, list) or not data:
                continue                          # org not on Lever
            company = slug.replace("-", " ").title()
            for j in data:
                title = j.get("text", "").strip()
                cats = j.get("categories") or {}
                loc = cats.get("location", "")
                desc = strip_html(j.get("descriptionPlain") or j.get("description", "") or "")
                if not matches_role(f"{title} {desc}", terms):
                    continue
                leads.append(Lead(
                    title=title, company=company, location=loc, salary="",
                    url=j.get("hostedUrl", "#"),
                    description=desc[:600],
                    source_key="lever", source="Lever",
                    ats="lever", portal="yes",
                ))
        return leads
