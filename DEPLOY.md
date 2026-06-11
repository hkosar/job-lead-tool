# Deploy Guide — put the Job Lead Tool on the internet with Render

Render hosts the app on a real web address and stores the data in a cloud Postgres
database, so nothing depends on your own computer staying on (or on antivirus
leaving the files alone). The repo already contains `render.yaml`, which tells
Render everything it needs. Total time: about 15 minutes, mostly waiting.

**Have ready before you start:**
- Your GitHub login (the one that owns this repository).
- Optional: an `ANTHROPIC_API_KEY` from https://console.anthropic.com/ if you want
  resume auto-drafting and competitor discovery. Everything else works without it,
  and you can add it later in Render's dashboard (Environment tab).

All security keys (`SESSION_SECRET`, `FERNET_KEY`) are **generated automatically**
by Render — there is nothing to copy from any other machine.

## Steps

1. **Create a Render account** — https://render.com → "Get Started" → sign up
   **with GitHub** (this lets Render see your repository).
2. **Start a Blueprint deploy** — in the Render dashboard click **New +** →
   **Blueprint** → choose the **job-lead-tool** repository → pick the branch
   (normally `main`). Render reads `render.yaml` and shows two items:
   a web service named **job-lead-tool** and a database named **joblead-db**.
3. **When prompted for `ANTHROPIC_API_KEY`** — paste your key, or leave it blank
   to skip LLM features for now. (Everything else is filled automatically.)
4. **Click Apply / Deploy** and wait. First build takes a few minutes. It's done
   when the service shows **Live** and the health check (`/healthz`) is green.
5. **Open the app** — Render gives you a URL like
   `https://job-lead-tool.onrender.com`. First visit asks you to set a passcode.
   The cloud copy starts fresh: enter the profile (or upload the resume), then
   connect your data-source keys on the Data Sources tab.

## Good to know

- **Free-plan behavior:** the service "sleeps" after ~15 minutes idle; the first
  visit after that takes ~30–60 seconds to wake. Fine for one candidate.
- **Free Postgres expires after 90 days** on Render's free tier — Render emails
  you first. Upgrading the database to the cheapest paid tier (~$7/mo) removes
  the limit; do this if the tool is in real daily use.
- **Updates:** every change merged to the deployed branch on GitHub redeploys
  automatically — build with Claude Code on the web, merge the pull request,
  and the live site updates itself a few minutes later.
- **The URL is part of your security** (spec §9): the passcode is the real lock,
  but don't post the URL publicly.
