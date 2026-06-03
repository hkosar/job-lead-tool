"""Indeed via licensed data vendor — PAID (~$45/mo, usage-based).
Indeed has no public search API and is not in Google Jobs, so coverage comes from a
vendor (e.g. Bright Data) that runs the scraping. ToS gray area — see spec section 5.

Bright Data's "Dataset API" is asynchronous: you trigger a collection, then poll a
snapshot until it's ready. We trigger and poll briefly within the request; if the
snapshot isn't ready in time we return what we have (often empty) rather than block.
Set the dataset/collector id in the connect form to target Indeed specifically.
"""
from __future__ import annotations
import time
import httpx
from .base import (SourceAdapter, CredField, Lead, HTTP_TIMEOUT,
                   role_query, location_query)

_TRIGGER = "https://api.brightdata.com/datasets/v3/trigger"
_SNAPSHOT = "https://api.brightdata.com/datasets/v3/snapshot/{sid}"


class IndeedVendorAdapter(SourceAdapter):
    key = "indeed"
    name = "Indeed (data vendor)"
    tier = "Paid"
    monthly_cost = 45
    fields = [CredField("api_token", "Vendor API Token"),
              CredField("dataset", "Dataset / Collector ID", "optional", optional=True)]

    def search(self, profile, creds=None):
        creds = creds or {}
        token = creds.get("api_token")
        dataset = creds.get("dataset")
        if not token or not dataset:
            # Without a dataset id we can't target Indeed; stay silent rather than error.
            return []
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = [{"keyword": role_query(profile), "location": location_query(profile) or "United States"}]
        try:
            r = httpx.post(_TRIGGER, headers=headers,
                           params={"dataset_id": dataset, "format": "json"},
                           json=payload, timeout=HTTP_TIMEOUT)
            if r.status_code not in (200, 202):
                print("Indeed vendor trigger failed:", r.status_code, r.text[:200])
                return []
            sid = (r.json() or {}).get("snapshot_id")
            if not sid:
                return []
            rows = self._poll(sid, headers)
            return [self._to_lead(x) for x in rows][:25]
        except Exception as e:
            print("Indeed vendor search failed:", e)
            return []

    def _poll(self, sid, headers, tries=6, delay=2.0):
        for _ in range(tries):
            try:
                r = httpx.get(_SNAPSHOT.format(sid=sid), headers=headers,
                              params={"format": "json"}, timeout=HTTP_TIMEOUT)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        return data
                # 202 = still running
            except Exception as e:
                print("Indeed vendor poll error:", e)
            time.sleep(delay)
        return []

    @staticmethod
    def _to_lead(x: dict) -> Lead:
        return Lead(
            title=x.get("job_title") or x.get("title", ""),
            company=x.get("company_name") or x.get("company", ""),
            location=x.get("location", ""),
            salary=x.get("salary", "") or "",
            url=x.get("url") or x.get("job_link", "#"),
            description=(x.get("description", "") or "")[:600],
            source_key="indeed", source="Indeed", ats="unknown", portal="unknown",
        )
