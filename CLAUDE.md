# CLAUDE.md — context for Claude Code

You are helping build the **Job Lead Tool**. The product owner is **not an experienced
developer**, so: explain what you're doing in plain language, work in small verifiable steps,
commit often, and never assume prior knowledge. Prefer clarity over cleverness.

## Read these first
- `spec/job-lead-tool-spec.md` — the authoritative product + technical spec. Follow it.
- `frontend/index.html` + `frontend/app.js` — the live UI, wired to the backend API. The
  tabs, labels, flows, and states in it are the UX reference; keep them consistent.

## Current status: v1 is BUILT and WORKING (verified by `smoke_test.py`)
The original build order (steps 1–6) is complete. What exists today:
- `backend/main.py` — FastAPI app, all routes implemented (no stubs): server-side sessions,
  profile, sources, lead refresh (search → score → de-dupe → persist), add-a-job
  read/extract/expand, reset.
- `backend/models.py` — SQLite by default, Postgres-ready (set `DATABASE_URL`). Hand-rolled
  column migration for existing SQLite files lives in `_migrate_columns` — add new Lead/AppState
  columns there too.
- `backend/sources/` — six real adapters behind `base.SourceAdapter`, listed in
  `__init__.REGISTRY`: Adzuna, Greenhouse (keyless), Lever (keyless), USAJOBS,
  SerpApi Google Jobs (paid), Indeed via Bright Data vendor (paid).
  Add a source = add a file + register it.
- `backend/scoring.py` — transparent weighted scoring (keyword/location/seniority/salary/
  affinity/industry + rejection-pattern penalties). No ML, on purpose.
- `backend/llm.py` — Anthropic parsing of resume (PDF/DOCX/TXT) and narrative into draft
  profile answers; job-posting extraction with a regex fallback when no key is set.
- `backend/auth.py` — bcrypt passcode hash, signed expiring session tokens, rate-limited
  login. Enforced by middleware on all `/api/*` except `/api/auth/*`.
- `backend/crypto.py` — Fernet encryption for stored source credentials (needs `FERNET_KEY`).
- `smoke_test.py` — end-to-end backend checks. Run it after backend changes:
  `python smoke_test.py` (uses a throwaway DB). Keep it green; extend it with new endpoints.
- `render.yaml` + `DEPLOY.md` — Render deployment (web service + free Postgres).

## What's next (remaining roadmap)
1. Batch history / anti-repeat (spec §4 "batch history", Phase 4): record which leads were
   shown in each batch so rebuilding doesn't repeat ignored leads.
2. Phase 3 — competitor portal-check: discover orgs similar to the seed organizations,
   probe their Greenhouse/Lever boards (Yes / Unknown), pull matching openings.
3. Phase 4 polish: approval-trend analytics, optional scheduled pulls.

## Conventions
- Keep `Lead` shape consistent across adapters (see `sources/base.Lead`).
- Don't put secrets in code or commit `.env`. Read keys from environment / encrypted source
  config. `.env` and `joblead.db` exist only on the owner's machine — never assume they're
  in the repo.
- After each working step: run `python smoke_test.py`, then
  `uvicorn backend.main:app --reload` to verify by hand, then commit.

## Definition of done for v1 (met)
The seven tabs work against live data: profile (with LLM drafting), on-demand lead batches
with scoring + approve/reject feedback, pipeline, add-a-job, data sources with
connect/credentials + cost meter, dashboard summary, passcode gate, reset.
