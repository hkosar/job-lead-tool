"""Source adapter interface + shared helpers.

Every job-data source (Adzuna, Greenhouse, Indeed vendor, ...) is a subclass of
SourceAdapter. The app calls .search(profile, creds) on every ENABLED + CONNECTED
source and merges the results. Adding a new source = adding one file here and
registering it in REGISTRY (see __init__.py). Nothing else in the app needs to change.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re, html as _html

import httpx

HTTP_TIMEOUT = 20.0


@dataclass
class Lead:
    """A single job opening, normalized across all sources."""
    title: str
    company: str
    location: str = ""
    salary: str = ""
    url: str = "#"
    description: str = ""
    source_key: str = ""          # which adapter produced it (e.g. "adzuna")
    source: str = ""              # display name shown in the UI (e.g. "Adzuna")
    ats: str = "unknown"          # greenhouse | lever | workday | custom | unknown
    portal: str = "unknown"       # yes | no | unknown  (step-5 coverage)
    score: float = 0.0            # filled by scoring.py, not the adapter


@dataclass
class CredField:
    id: str
    label: str
    placeholder: str = ""
    optional: bool = False


class SourceAdapter:
    """Base class. Override key/name/tier/cost/fields and implement search()."""
    key: str = "base"
    name: str = "Base"
    tier: str = "Free"            # "Free" | "Paid"
    monthly_cost: int = 0         # USD/month estimate for the cost meter
    keyless: bool = False         # True = no credentials needed (public boards)
    fields: list[CredField] = []  # credential inputs shown in the connect form

    def search(self, profile: dict, creds: Optional[dict] = None) -> list[Lead]:
        """Return matching leads for the candidate profile. Implement per source."""
        raise NotImplementedError

    def is_connected(self, creds: Optional[dict]) -> bool:
        if self.keyless:
            return True
        if not creds:
            return False
        return all(creds.get(f.id) for f in self.fields if not f.optional)


# ---------- shared profile -> search-term helpers ----------
def _derived(profile: dict, qid: str) -> str:
    return (profile.get(qid, {}) or {}).get("derived", "") or ""


def role_query(profile: dict) -> str:
    """Best single free-text query for the candidate's target role."""
    role = _derived(profile, "role").split("·")[0]
    first = re.split(r"[,/;|]", role)[0].strip()
    return first or "communications"


def all_role_terms(profile: dict) -> list[str]:
    """Every target title, lowercased — used to filter keyless board listings."""
    role = _derived(profile, "role").split("·")[0]
    terms = [t.strip().lower() for t in re.split(r"[,/;|]", role) if t.strip()]
    # also fold in must-have skill keywords for board filtering
    skills = [s.strip().lower() for s in re.split(r"[,/;|]", _derived(profile, "skills")) if s.strip()]
    return terms or skills or ["communications"]


def location_query(profile: dict) -> str:
    """A concrete place for APIs that need one; '' if the candidate is remote-only."""
    loc = _derived(profile, "location")
    parts = [p.strip() for p in re.split(r"[,;|]", loc) if p.strip()]
    for p in parts:
        if not p.lower().startswith(("remote", "hybrid")):
            return p
    return ""


def org_slugs(profile: dict) -> list[str]:
    """Candidate board slugs from the 'dream' (seed) organizations, for keyless ATS
    boards. 'United Way Worldwide' -> 'unitedwayworldwide', 'united-way', ..."""
    out: list[str] = []
    for org in org_names(profile):
        base = re.sub(r"[^a-z0-9]", "", org.lower())
        hyphen = re.sub(r"[^a-z0-9]+", "-", org.lower()).strip("-")
        for cand in (base, hyphen):
            if cand and cand not in out:
                out.append(cand)
    return out


def org_names(profile: dict) -> list[str]:
    raw = _derived(profile, "dream")
    return [o.strip() for o in re.split(r"[,;|]", raw) if o.strip()]


def strip_html(s: str) -> str:
    """Turn HTML (or entity-encoded HTML) into clean plain text.
    Unescape entities FIRST so '&lt;p&gt;' becomes a tag we then remove."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", _html.unescape(s))).strip()


def matches_role(text: str, terms: list[str]) -> bool:
    """True if any target term (or a salient word from it) appears in text."""
    t = (text or "").lower()
    for term in terms:
        if term and term in t:
            return True
        for word in term.split():
            if len(word) > 3 and word in t:
                return True
    return False


def get_json(url: str, params: dict | None = None, headers: dict | None = None):
    """Small GET helper returning parsed JSON, or None on any failure."""
    try:
        r = httpx.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT,
                      follow_redirects=True)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"GET {url} failed:", e)
    return None
