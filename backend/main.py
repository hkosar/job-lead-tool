"""FastAPI app entrypoint.

Run locally:   uvicorn backend.main:app --reload
Then open:     http://localhost:8000   (serves frontend/index.html)
API docs:      http://localhost:8000/docs

All real logic is implemented here against the spec: server-side passcode sessions,
encrypted source credentials, and a /api/leads/refresh that pulls from every enabled
source, scores, de-dupes, and persists.
"""
from __future__ import annotations
import os as _os
from dotenv import load_dotenv
# Load .env from the project root by absolute path so it works no matter what
# directory the server is launched from.
load_dotenv(_os.path.join(_os.path.dirname(__file__), "..", ".env"))

from fastapi import FastAPI, UploadFile, File, Form, Body, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from dataclasses import asdict
import os, re

from .models import engine, init_db, AppState, Lead, get_state, jload, jdump, now_iso
from .sources import REGISTRY
from . import auth, llm, scoring, crypto

app = FastAPI(title="Job Lead Tool")


@app.on_event("startup")
def _startup():
    init_db()


# ---------- server-side session gate (spec section 9) ----------
@app.middleware("http")
async def require_session(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/auth/"):
        token = request.headers.get("authorization", "")
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if not auth.verify_session_token(token):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)


def _client_id(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---------- auth ----------
@app.get("/api/auth/status")
def auth_status():
    with Session(engine) as s:
        return {"passcode_set": bool(get_state(s).passcode_hash)}


@app.post("/api/auth/set")
def auth_set(request: Request, passcode: str = Body(..., embed=True)):
    if len(passcode or "") < 4:
        return JSONResponse({"detail": "Passcode must be at least 4 characters."}, status_code=400)
    with Session(engine) as s:
        st = get_state(s)
        if st.passcode_hash:
            return JSONResponse({"detail": "Passcode already set; use login."}, status_code=409)
        st.passcode_hash = auth.set_passcode(passcode); s.add(st); s.commit()
    return {"ok": True, "token": auth.create_session_token()}


@app.post("/api/auth/login")
def auth_login(request: Request, passcode: str = Body(..., embed=True)):
    cid = _client_id(request)
    if auth.too_many_attempts(cid):
        return JSONResponse({"detail": "Too many attempts. Wait a few minutes and try again."},
                            status_code=429)
    with Session(engine) as s:
        ok = auth.check_passcode(passcode, get_state(s).passcode_hash)
    if not ok:
        auth.record_attempt(cid)
        return {"ok": False}
    auth.clear_attempts(cid)
    return {"ok": True, "token": auth.create_session_token()}


# ---------- profile ----------
@app.get("/api/profile")
def get_profile():
    with Session(engine) as s:
        st = get_state(s)
        return {"profile": jload(st.profile_json, {}), "intro": st.intro}


@app.put("/api/profile")
def put_profile(profile: dict = Body(...), intro: str = Body("")):
    with Session(engine) as s:
        st = get_state(s); st.profile_json = jdump(profile); st.intro = intro
        s.add(st); s.commit()
    return {"ok": True}


@app.post("/api/profile/parse")
async def parse_profile(resume: UploadFile | None = File(None), narrative: str = Form("")):
    """Resume upload OR free-text -> drafted answers (the client fills blanks only)."""
    text = narrative or ""
    if resume is not None:
        text = llm.extract_resume_text(await resume.read(), resume.filename)
    return {"draft": llm.parse_to_profile(text)}


# ---------- sources ----------
@app.get("/api/sources")
def list_sources():
    with Session(engine) as s:
        cfg = jload(get_state(s).sources_json, {})
    out = []
    for key, a in REGISTRY.items():
        c = cfg.get(key, {})
        creds = crypto.decrypt_creds(c.get("creds"))
        out.append({
            "key": key, "name": a.name, "tier": a.tier, "cost": a.monthly_cost,
            "keyless": a.keyless, "on": c.get("on", a.keyless),
            "connected": a.is_connected(creds),
            "fields": [vars(f) for f in a.fields],
            # send back only the last 4 chars of the first cred so the UI can show "•••• 1234"
            "cred_hint": _cred_hint(a, creds),
        })
    return {"sources": out}


def _cred_hint(adapter, creds):
    if adapter.keyless or not creds:
        return ""
    first = adapter.fields[0].id if adapter.fields else ""
    v = (creds.get(first) or "")
    return v[-4:] if len(v) >= 4 else ("•" * len(v))


@app.post("/api/sources/{key}/connect")
def connect_source(key: str, creds: dict = Body(...)):
    if key not in REGISTRY:
        return JSONResponse({"detail": "unknown source"}, status_code=404)
    with Session(engine) as s:
        st = get_state(s); cfg = jload(st.sources_json, {})
        entry = cfg.setdefault(key, {})
        entry["creds"] = crypto.encrypt_creds(creds)     # ENCRYPTED at rest
        entry["connected"] = True
        entry["on"] = True
        st.sources_json = jdump(cfg); s.add(st); s.commit()
    return {"ok": True}


@app.post("/api/sources/{key}/toggle")
def toggle_source(key: str):
    if key not in REGISTRY:
        return JSONResponse({"detail": "unknown source"}, status_code=404)
    a = REGISTRY[key]
    with Session(engine) as s:
        st = get_state(s); cfg = jload(st.sources_json, {})
        cur = cfg.setdefault(key, {})
        creds = crypto.decrypt_creds(cur.get("creds"))
        turning_on = not cur.get("on", a.keyless)
        if turning_on and not a.is_connected(creds):
            return JSONResponse({"detail": "Connect this source first."}, status_code=400)
        cur["on"] = turning_on
        st.sources_json = jdump(cfg); s.add(st); s.commit()
        return {"on": cur["on"]}


# ---------- leads / batch ----------
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _source_enabled(cfg: dict, key: str) -> bool:
    """Leads from registered sources count only while that source is on+connected;
    manual / internal leads are always eligible."""
    if key not in REGISTRY:
        return True
    a = REGISTRY[key]
    c = cfg.get(key, {})
    return bool(c.get("on", a.keyless) and a.is_connected(crypto.decrypt_creds(c.get("creds"))))


def _current_batch(s: Session) -> int:
    top = s.exec(select(Lead.batch_id).order_by(Lead.batch_id.desc())).first()
    return int(top or 0)


def _reject_history(s: Session) -> dict:
    """Tally rejection reasons across archived leads -> {reason: count} for scoring."""
    tally: dict[str, int] = {}
    for l in s.exec(select(Lead).where(Lead.status == "archived")).all():
        for r in jload(l.reasons_json, []):
            tally[r] = tally.get(r, 0) + 1
    return tally


@app.post("/api/leads/refresh")
def refresh_leads():
    """Pull from every enabled+connected source, score, de-dupe, and store new leads."""
    with Session(engine) as s:
        st = get_state(s)
        profile = jload(st.profile_json, {})
        cfg = jload(st.sources_json, {})
        reject_hist = _reject_history(s)

        # index existing leads to avoid duplicates (by url and by company+title)
        existing = s.exec(select(Lead)).all()
        seen_urls = {l.url for l in existing if l.url and l.url != "#"}
        seen_pairs = {(_norm(l.company), _norm(l.title)) for l in existing}

        found, added, errors = 0, 0, []
        for key, a in REGISTRY.items():
            c = cfg.get(key, {})
            creds = crypto.decrypt_creds(c.get("creds"))
            if not (c.get("on", a.keyless) and a.is_connected(creds)):
                continue
            try:
                results = a.search(profile, creds)
            except Exception as e:
                errors.append(f"{a.name}: {e}")
                continue
            for ld in results:
                found += 1
                d = asdict(ld)
                pair = (_norm(d["company"]), _norm(d["title"]))
                if (d.get("url") in seen_urls) or (pair in seen_pairs) or not d["title"]:
                    continue
                seen_urls.add(d.get("url")); seen_pairs.add(pair)
                d["score"] = scoring.score_lead(d, profile, reject_hist)
                lead = Lead(
                    title=d["title"], company=d["company"], location=d["location"],
                    salary=d["salary"], url=d["url"], description=d["description"],
                    source_key=d["source_key"], source=d["source"], ats=d["ats"],
                    portal=d["portal"], score=d["score"], status="new",
                    date_found=now_iso(),
                )
                s.add(lead); added += 1
        s.commit()
    return {"found": found, "added": added, "errors": errors}


@app.post("/api/leads/batch")
def assemble_batch(n: int = Body(20, embed=True)):
    """Assemble the next batch of up to n unreviewed leads (spec: batch history /
    anti-repeat). Leads never shown before come first, ranked by score; leads from
    earlier batches repeat only when fresh ones run out (oldest-shown first). The
    chosen leads are stamped with a batch number and presentation time."""
    n = max(1, min(50, n or 20))
    with Session(engine) as s:
        cfg = jload(get_state(s).sources_json, {})
        pool = [l for l in s.exec(select(Lead).where(Lead.status == "new")).all()
                if _source_enabled(cfg, l.source_key)]
        pool.sort(key=lambda l: (1 if l.date_presented else 0,
                                 l.date_presented or "", -l.score))
        chosen = pool[:n]
        fresh = sum(1 for l in chosen if not l.date_presented)
        batch = _current_batch(s) + (1 if chosen else 0)
        stamp = now_iso()
        for l in chosen:
            l.batch_id = batch
            l.date_presented = stamp
            s.add(l)
        s.commit()
        return {"batch": batch, "fresh": fresh, "pool": len(pool),
                "leads": [_lead_dict(l) for l in chosen]}


@app.get("/api/leads")
def get_leads(status: str | None = None):
    with Session(engine) as s:
        q = select(Lead)
        if status:
            q = q.where(Lead.status == status)
        return {"leads": [_lead_dict(l) for l in s.exec(q).all()],
                "current_batch": _current_batch(s)}


def _lead_dict(l: Lead) -> dict:
    return {
        "id": l.id, "title": l.title, "company": l.company, "location": l.location,
        "salary": l.salary, "url": l.url, "description": l.description,
        "source": l.source or l.source_key, "source_key": l.source_key, "ats": l.ats,
        "portal": l.portal, "score": l.score, "status": l.status,
        "reasons": jload(l.reasons_json, []), "addedManually": l.added_manually,
        "dateFound": l.date_found, "datePresented": l.date_presented,
        "batchId": l.batch_id,
    }


@app.post("/api/leads/add")
def add_lead(company: str = Body(...), title: str = Body(...),
             location: str = Body(""), salary: str = Body(""),
             url: str = Body("#"), status: str = Body("in_progress")):
    """Manually add a job to the pipeline (Add-a-Job tab)."""
    if not company or not title:
        return JSONResponse({"detail": "company and title are required"}, status_code=400)
    with Session(engine) as s:
        lead = Lead(title=title, company=company, location=location or "—",
                    salary=salary or "—", url=url or "#", source="manual",
                    source_key="manual", ats="manual", portal="unknown",
                    status=status or "in_progress", added_manually=True,
                    date_found=now_iso())
        s.add(lead); s.commit(); s.refresh(lead)
        return {"ok": True, "lead": _lead_dict(lead)}


@app.post("/api/leads/{lead_id}/status")
def set_lead_status(lead_id: int, status: str = Body(..., embed=True),
                    reasons: list[str] = Body(default=[])):
    with Session(engine) as s:
        l = s.get(Lead, lead_id)
        if not l:
            return JSONResponse({"detail": "not found"}, status_code=404)
        l.status = status
        if status == "archived":
            l.reasons_json = jdump(reasons)
        elif reasons == [] and status != "archived":
            l.reasons_json = "[]"
        s.add(l); s.commit()
    return {"ok": True}


# ---------- Add-a-Job: read / extract / expand ----------
_READABLE = re.compile(r"greenhouse|lever|ashbyhq|workable|boards\.|jobs\.lever|myworkdayjobs", re.I)


@app.post("/api/jobs/read")
def read_job(url: str = Body(..., embed=True)):
    """Try to read a posting automatically from keyless ATS boards. If the site
    blocks automated reading (Indeed/LinkedIn), tell the client to ask for a paste."""
    if not url:
        return {"ok": False, "needs_paste": True, "detail": "No URL."}
    details = _read_greenhouse(url) or _read_lever(url)
    if details:
        return {"ok": True, "details": details}
    return {"ok": False, "needs_paste": not bool(_READABLE.search(url)),
            "detail": "Could not read this posting automatically."}


def _read_greenhouse(url: str):
    m = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url) or re.search(r"boards\.greenhouse\.io/([^/?#]+)", url)
    if not m or "greenhouse" not in url:
        return None
    from .sources.base import get_json
    if m.lastindex == 2:
        from .sources.base import strip_html
        token, jid = m.group(1), m.group(2)
        j = get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{jid}")
        if j:
            content = strip_html(j.get("content", "") or "")
            return {"company": token.replace("-", " ").title(), "title": j.get("title", ""),
                    "location": (j.get("location") or {}).get("name", ""), "salary": "",
                    "url": j.get("absolute_url", url), "description": content[:400]}
    return None


def _read_lever(url: str):
    m = re.search(r"lever\.co/([^/]+)/([0-9a-f\-]+)", url)
    if not m or "lever" not in url:
        return None
    from .sources.base import get_json
    company, jid = m.group(1), m.group(2)
    j = get_json(f"https://api.lever.co/v0/postings/{company}/{jid}")
    if j:
        return {"company": company.replace("-", " ").title(), "title": j.get("text", ""),
                "location": (j.get("categories") or {}).get("location", ""), "salary": "",
                "url": j.get("hostedUrl", url), "description": (j.get("descriptionPlain", "") or "")[:400]}
    return None


@app.post("/api/jobs/extract")
def extract_job(text: str = Body(..., embed=True)):
    """Parse a pasted job description into structured fields (LLM, with heuristic fallback)."""
    return {"details": llm.parse_job_posting(text)}


@app.post("/api/expand")
def expand_search(company: str = Body(..., embed=True)):
    """Scan the given organization's public Greenhouse/Lever board for more openings
    that match the profile, and add any new ones to the Leads queue."""
    from .sources.base import org_slugs, all_role_terms
    from .sources.greenhouse import GreenhouseAdapter
    from .sources.lever import LeverAdapter
    with Session(engine) as s:
        st = get_state(s); profile = jload(st.profile_json, {})
        reject_hist = _reject_history(s)
        existing = s.exec(select(Lead)).all()
        seen_pairs = {(_norm(l.company), _norm(l.title)) for l in existing}

        # build a one-org pseudo-profile so the keyless adapters target this company
        slug_seed = {"dream": {"derived": company}}
        probe = dict(profile); probe["dream"] = slug_seed["dream"]
        # the candidate asked for these explicitly, so put them straight into the
        # current batch (if one exists) instead of waiting for the next build
        cur_batch = _current_batch(s)
        stamp = now_iso() if cur_batch else ""
        added = 0
        for adapter in (GreenhouseAdapter(), LeverAdapter()):
            try:
                for ld in adapter.search(probe):
                    pair = (_norm(ld.company), _norm(ld.title))
                    if pair in seen_pairs or not ld.title:
                        continue
                    seen_pairs.add(pair)
                    d = asdict(ld)
                    d["score"] = scoring.score_lead(d, profile, reject_hist)
                    s.add(Lead(title=d["title"], company=d["company"], location=d["location"],
                               salary=d["salary"], url=d["url"], description=d["description"],
                               source_key=d["source_key"], source=d["source"], ats=d["ats"],
                               portal=d["portal"], score=d["score"], status="new",
                               date_found=now_iso(), batch_id=cur_batch,
                               date_presented=stamp))
                    added += 1
            except Exception as e:
                print("expand error:", e)
        s.commit()
    return {"added": added}


# ---------- Phase 3: competitor portal check ----------
@app.post("/api/competitors/scan")
def scan_competitors():
    """Discover organizations similar to the candidate's seed orgs (LLM-suggested),
    then probe each one's public Greenhouse/Lever board. portal='yes' comes with a
    count of openings matching the target role; orgs without a queryable board are
    honestly 'unknown' (spec section 2)."""
    from .sources.base import org_names, all_role_terms
    with Session(engine) as s:
        profile = jload(get_state(s).profile_json, {})
    seeds = org_names(profile)
    if not seeds:
        return {"ok": False, "needs_seeds": True,
                "detail": "Add seed organizations in your Candidate Profile first "
                          "(the 'organizations you'd love to work for' question)."}
    industries = (profile.get("industries", {}) or {}).get("derived", "") or ""
    names = llm.suggest_competitors(seeds, industries)
    if not names:
        return {"ok": False, "needs_key": True,
                "detail": "Competitor discovery uses the LLM to suggest similar "
                          "organizations — set ANTHROPIC_API_KEY to enable it."}
    terms = all_role_terms(profile)
    seen = {_norm(x) for x in seeds}
    rows = []
    for name in names[:8]:
        if not name or _norm(name) in seen:
            continue
        seen.add(_norm(name))
        rows.append(_probe_org(name, terms))
    return {"ok": True, "competitors": rows}


def _probe_org(name: str, terms: list[str]) -> dict:
    """Check one organization's public ATS boards. Greenhouse/Lever give a real
    'yes' (queryable portal); anything else is 'unknown' — they may still hire
    through Workday or a custom site we can't read."""
    from .sources.base import slugs_for, get_json, matches_role, strip_html
    for slug in slugs_for(name)[:2]:
        g = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                     params={"content": "true"})
        if g and "jobs" in g:
            jobs = g.get("jobs", [])
            hits = sum(1 for j in jobs if matches_role(
                f"{j.get('title', '')} {strip_html(j.get('content', '') or '')}", terms))
            return {"company": name, "portal": "yes", "ats": "greenhouse",
                    "openings": len(jobs), "matching": hits}
        lv = get_json(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
        if isinstance(lv, list) and lv:
            hits = sum(1 for j in lv if matches_role(
                f"{j.get('text', '')} {j.get('descriptionPlain', '') or ''}", terms))
            return {"company": name, "portal": "yes", "ats": "lever",
                    "openings": len(lv), "matching": hits}
    return {"company": name, "portal": "unknown", "ats": "", "openings": 0, "matching": 0}


# ---------- reset ----------
@app.post("/api/reset")
def reset_all():
    """Wipe everything for the next candidate (profile, leads, sources, passcode)."""
    with Session(engine) as s:
        for l in s.exec(select(Lead)).all():
            s.delete(l)
        st = get_state(s)
        st.passcode_hash = ""; st.profile_json = "{}"; st.intro = ""; st.sources_json = "{}"
        s.add(st); s.commit()
    return {"ok": True}


# ---------- health check (used by the hosting platform; no auth) ----------
@app.get("/healthz")
def healthz():
    return {"ok": True}


# ---------- serve the frontend ----------
FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
