# Job Lead Tool

A single-candidate job-search assistant: build a profile (resume / narrative / weighted
questions), get on-demand batches of matching job leads, approve or reject them to train
the ranking, and track every application through a pipeline.

- **`spec/job-lead-tool-spec.md`** — the full product + technical spec (read this first).
- **`SETUP-GUIDE.md`** — step-by-step setup for a non-developer. **Start here if you've never run code before.**
- **`DEPLOY.md`** — put the app online with Render (cloud hosting + cloud database).
- **`CLAUDE.md`** — context for Claude Code; it reads this automatically.
- **`first-prompts-for-claude-code.md`** — copy-paste prompts to start the build.
- **`frontend/index.html`** — the working clickable prototype (the UX reference).
- **`backend/`** — FastAPI skeleton: API routes, data model, source adapters, scoring, LLM parsing, auth.

## Run it (the build is done)

This repo is already set up with a virtual environment and a `.env` containing
auto-generated security keys. To start the app on Windows (PowerShell), from this folder:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
# then open http://localhost:8000   (API docs at http://localhost:8000/docs)
```

First visit asks you to **set a passcode**; after that it's your login. On the
**Data Sources** tab, Greenhouse and Lever work with no keys — add seed organizations
in your **Candidate Profile** (the "dream organizations" question) and press **Build
batch** on the Leads tab to pull real openings from those companies' public boards.

To enable more sources, paste their keys on the Data Sources tab (stored encrypted):
- **Adzuna** (free): App ID + App Key from https://developer.adzuna.com/
- **USAJOBS** (free): API key + your email from https://developer.usajobs.gov/
- **Google Jobs / Indeed** (paid): connect once you subscribe.

For resume/narrative auto-drafting and smarter Add-a-Job parsing, put an
`ANTHROPIC_API_KEY` in `.env` (https://console.anthropic.com/). Everything else works without it.

If you ever need to recreate the environment from scratch:
```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env   # then fill in keys; SESSION_SECRET/FERNET_KEY can be regenerated
```

## Status
**Built and working.** Server-side passcode sessions, encrypted credential storage,
six source adapters (Adzuna, Greenhouse, Lever, USAJOBS, SerpApi Google Jobs, Indeed
vendor), transparent weighted scoring, LLM resume/narrative parsing (PDF + DOCX), the
Add-a-Job read/extract/expand flow, and all seven tabs wired to the live API.
`smoke_test.py` exercises the backend end to end.
