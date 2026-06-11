# Deploy Guide — put the Job Lead Tool on the internet with Render

Render hosts the app on a real web address and stores the data in a cloud Postgres
database, so nothing depends on your own computer staying on (or on antivirus
leaving the files alone). The repo already contains `render.yaml`, which tells
Render everything it needs. Total time: about 15 minutes, mostly waiting.

**Have ready before you start:**
- Your GitHub login (the one that owns this repository).
- The `FERNET_KEY` value from the `.env` file on your computer (open `.env` in
  Notepad and copy the long string after `FERNET_KEY=`). Using the *same* key in
  the cloud means any data-source keys you saved locally stay decryptable.
  If you skip it, Render still works — you'd just re-enter source keys in the app.
- Optional: your `ANTHROPIC_API_KEY` (same file) if you want resume auto-drafting
  in the cloud version.

## Steps

1. **Create a Render account** — https://render.com → "Get Started" → sign up
   **with GitHub** (this lets Render see your repository).
2. **Start a Blueprint deploy** — in the Render dashboard click **New +** →
   **Blueprint** → choose the **job-lead-tool** repository → pick the branch
   (normally `main`). Render reads `render.yaml` and shows two items:
   a web service named **job-lead-tool** and a database named **joblead-db**.
3. **Fill in the two secret values when prompted:**
   - `FERNET_KEY` → paste the value from your local `.env`.
   - `ANTHROPIC_API_KEY` → paste your key, or leave blank to skip LLM drafting.
   (`SESSION_SECRET` and `DATABASE_URL` are generated automatically — don't touch.)
4. **Click Apply / Deploy** and wait. First build takes a few minutes. It's done
   when the service shows **Live** and the health check (`/healthz`) is green.
5. **Open the app** — Render gives you a URL like
   `https://job-lead-tool.onrender.com`. First visit asks you to set a passcode,
   exactly like local. The cloud copy starts with an empty profile (it has its own
   database) — re-enter the profile or upload the resume again, then connect your
   data-source keys on the Data Sources tab.

## Good to know

- **Free-plan behavior:** the service "sleeps" after ~15 minutes idle; the first
  visit after that takes ~30–60 seconds to wake. Fine for one candidate.
- **Free Postgres expires after 90 days** on Render's free tier — Render emails
  you first. Upgrading the database to the cheapest paid tier (~$7/mo) removes
  the limit; do this if the tool is in real daily use.
- **Updates:** every push to the deployed branch on GitHub redeploys
  automatically. The local copy keeps working as before — they're independent.
- **The URL is part of your security** (spec §9): the passcode is the real lock,
  but don't post the URL publicly.
