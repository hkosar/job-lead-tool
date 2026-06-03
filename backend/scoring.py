"""Transparent weighted scoring (v1, no ML). See spec section 7.

score = keyword fit + location fit + seniority fit + salary fit + org affinity
        - rejection-pattern penalties,
each term scaled by the candidate's importance weight (1-5) for that preference.
Low importance shrinks a term's influence; high importance increases it (and a
firm exclusion/seniority mismatch can push a lead well down). Readable and
debuggable on purpose. Returns 0-100.
"""
from __future__ import annotations
import re

SENIOR_WORDS = ["chief", "vp", "vice president", "president", "executive director",
                "director", "head of", "head,", "senior", "principal", "lead ",
                "officer", "partner", "ceo", "coo", "cfo", "cmo", "cto"]
JUNIOR_WORDS = ["intern", "junior", "entry", "assistant", "coordinator",
                "associate", "trainee", "apprentice", "clerk"]


def _kw(text: str):
    return set(w for w in text.lower().replace(",", " ").split() if len(w) > 2)


def _salary_to_k(text: str) -> float | None:
    """Pull a representative salary (in $thousands) from free text.
    '$150k–$190k' -> 170 ; '$140,000' -> 140 ; 'Target ~$140k (flexible)' -> 140."""
    if not text:
        return None
    nums = []
    for m in re.finditer(r"\$?\s*(\d[\d,]*)\s*([kK])?", text):
        digits = m.group(1).replace(",", "")
        if not digits:
            continue
        val = float(digits)
        if m.group(2):              # explicit "k"
            val *= 1000
        if val < 1000:              # bare "140" means 140k in salary context
            val *= 1000
        if 10_000 <= val <= 1_000_000:
            nums.append(val / 1000.0)
    if not nums:
        return None
    return sum(nums) / len(nums)    # midpoint of a range, or the single value


def _has_any(text: str, words) -> bool:
    return any(w in text for w in words)


def score_lead(lead: dict, profile: dict, reject_history: dict | None = None) -> float:
    reject_history = reject_history or {}

    def derived(qid): return (profile.get(qid, {}) or {}).get("derived", "") or ""
    def weight(qid): return (profile.get(qid, {}) or {}).get("priority", 3) or 3

    title = (lead.get("title", "") or "").lower()
    text = f"{lead.get('title','')} {lead.get('description','')}".lower()
    score = 50.0

    # --- keyword / must-have fit (heaviest lever) ---
    musts = _kw(derived("skills")) | _kw(derived("role"))
    if musts:
        hit = sum(1 for k in musts if k in text) / len(musts)
        score += hit * 8 * weight("skills")

    # --- exclusions: hard-cut, softened by how firm they are ---
    for bad in _kw(derived("exclude")):
        if bad in text:
            score -= 6 * weight("exclude")

    # --- location fit ---
    loc = (lead.get("location", "") or "").lower()
    wants = [p.strip().lower() for p in derived("location").replace(";", ",").split(",") if p.strip()]
    if wants and any(p in loc or ("remote" in p and "remote" in loc) for p in wants):
        score += 3 * weight("location")

    # --- seniority fit ---
    role_text = derived("role").lower()
    wants_senior = _has_any(role_text, SENIOR_WORDS) or "exec" in role_text or "senior" in role_text
    if wants_senior:
        w = weight("role")
        if _has_any(title, SENIOR_WORDS):
            score += 2.5 * w
        if _has_any(title, JUNIOR_WORDS):
            score -= 5 * w               # firm wrong-level signal

    # --- salary fit (a target with an importance, not a hard floor) ---
    target = _salary_to_k(derived("salary"))
    offered = _salary_to_k(lead.get("salary", ""))
    if target and offered:
        w = weight("salary")
        ratio = offered / target
        if ratio >= 1.0:
            score += min(3.0, (ratio - 1.0) * 6) * w      # at/above target -> bonus
        else:
            score -= min(8.0, (1.0 - ratio) * 16) * w     # below target -> penalty, scaled by firmness

    # --- org affinity (dream / seed organizations) ---
    company = (lead.get("company", "") or "").lower()
    dreams = [d.strip().lower() for d in derived("dream").replace(";", ",").split(",") if d.strip()]
    if company and any(d and (d in company or company in d) for d in dreams):
        score += 4 * weight("dream")

    # --- industry fit (light touch) ---
    inds = _kw(derived("industries"))
    if inds and any(i in text for i in inds):
        score += 2 * weight("industries")

    # --- behavioral penalty: down-weight patterns the candidate keeps rejecting ---
    rl = " ".join(reject_history.keys()).lower()
    if "pay too low" in rl and offered and target and offered < target:
        score -= min(reject_history.get("Pay too low", 0), 5) * 1.5
    if "wrong location" in rl and wants and not (loc and any(p in loc for p in wants)):
        score -= min(reject_history.get("Wrong location", 0), 5) * 1.0
    if "wrong seniority" in rl and _has_any(title, JUNIOR_WORDS):
        score -= min(reject_history.get("Wrong seniority", 0), 5) * 1.0
    # generic mild damping for any heavily-repeated reason
    for reason, count in reject_history.items():
        score -= min(count, 5) * 0.2

    return max(0.0, min(100.0, round(score, 1)))
