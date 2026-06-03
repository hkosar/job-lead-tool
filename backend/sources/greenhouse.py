"""Greenhouse adapter — FREE, KEYLESS. Public board JSON, no auth:
  GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
Board tokens come from the candidate's seed/dream organizations (profile 'dream').
Also powers the step-5 portal check: portal="yes" when a match exists on the board.
"""
from __future__ import annotations
from .base import (SourceAdapter, Lead, get_json, org_slugs,
                   all_role_terms, matches_role, strip_html)


class GreenhouseAdapter(SourceAdapter):
    key = "greenhouse"
    name = "Greenhouse boards"
    tier = "Free"
    monthly_cost = 0
    keyless = True

    def search(self, profile, creds=None):
        terms = all_role_terms(profile)
        leads = []
        for slug in org_slugs(profile)[:12]:
            data = get_json(
                f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                params={"content": "true"},
            )
            if not data or "jobs" not in data:
                continue                          # org not on Greenhouse
            company = self._company_name(data, slug)
            for j in data.get("jobs", []):
                title = j.get("title", "").strip()
                loc = (j.get("location") or {}).get("name", "")
                content = strip_html(j.get("content", "") or "")
                if not matches_role(f"{title} {content}", terms):
                    continue
                leads.append(Lead(
                    title=title, company=company, location=loc, salary="",
                    url=j.get("absolute_url", "#"),
                    description=content[:600],
                    source_key="greenhouse", source="Greenhouse",
                    ats="greenhouse", portal="yes",
                ))
        return leads

    @staticmethod
    def _company_name(data, slug):
        name = (data.get("meta") or {}).get("company_name")
        return name or slug.replace("-", " ").title()
