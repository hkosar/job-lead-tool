# CLAUDE.md — context for Claude Code

You are helping build the **Job Lead Tool**. The product owner is **not an experienced
developer**, so: explain what you're doing in plain language, work in small verifiable steps,
commit often, and never assume prior knowledge. Prefer clarity over cleverness.

## Read these first
- `spec/job-lead-tool-spec.md` — the authoritative product + technical spec. Follow it.
- `frontend/index.html` — the working clickable prototype. It is the UX reference: the
  production UI should match its tabs, labels, flows, and states. (It currently uses
  localStorage + sample data; the build wires it to the backend API.)

## What's here
- `backend/main.py` — FastAPI app with routes wired to **stub** behavior so it runs today.
- `backend/models.py` — SQLite (SQLModel) single-candidate data model.
- `backend/sources/` — one adapter per data source behind `base.SourceAdapter`; `__init__.REGISTRY`
  lists them. Add a source = add a file + register it. Each adapter has a `TODO` for the real API call.
- `backend/scoring.py` — transparent weighted scoring (no ML). Has `TODO`s for salary/seniority/affinity.
- `backend/llm.py` — Anthropic-based parsing of resume/narrative into draft profile answers.
- `backend/auth.py` — single-passcode gate; **must be enforced server-side** (see spec §9).

## Build order (suggested)
1. Make the frontend talk to the backend API (replace its localStorage with `fetch` calls to `/api/*`).
2. Implement the Adzuna, Greenhouse, and Lever adapters (free) + `/api/leads/refresh` (search, score, de-dupe, persist).
3. Wire LLM parsing (`/api/profile/parse`) into the resume upload + narrative box (fill blanks only, never overwrite).
4. Real server-side auth: session token issued on passcode login; require it on `/api/*` except `/api/auth/*`; rate-limit.
5. Encrypt source credentials before storing (`connect_source` has a TODO).
6. Paid adapters (SerpApi Google Jobs, Indeed vendor) with the connect/credential UI.
7. Phase 3: competitor portal-check (Yes/No for Greenhouse/Lever, Unknown otherwise).

## Conventions
- Keep `Lead` shape consistent across adapters (see `sources/base.Lead`).
- Don't put secrets in code or commit `.env`. Read keys from environment / encrypted source config.
- After each working step: run `uvicorn backend.main:app --reload`, verify, then commit.

## Definition of done for v1
The seven tabs in the prototype work against live data: profile (with LLM drafting),
on-demand lead batches with scoring + approve/reject feedback, pipeline, add-a-job,
data sources with connect/credentials + cost meter, dashboard summary, passcode gate, reset.
