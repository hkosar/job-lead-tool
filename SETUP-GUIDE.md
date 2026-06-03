# Setup Guide — for someone new to building software

This walks you from zero to a running app and a productive build session with Claude Code.
Take it one numbered step at a time. You do **not** need to understand the code to do this.

---

## A 60-second glossary (so the steps make sense)
- **Repo / repository** — the folder holding all the project's files (this folder).
- **Terminal** — the text window where you type commands. (Mac: "Terminal" app. Windows: "PowerShell".)
- **Python** — the programming language the backend is written in.
- **Backend** — the program that runs on a server, talks to job sites, and stores data.
- **Frontend** — the web page the candidate sees in their browser.
- **API key** — a password-like string a service gives you so your app can use it.
- **Environment variable / `.env`** — a private file holding your keys, never shared or committed.
- **Claude Code** — Anthropic's coding assistant that edits files and runs commands for you in this repo.
- **Git / GitHub** — version control: saves snapshots of your code so nothing is ever lost.
- **Deploy / hosting** — putting the app on the internet so it has a real web address.

---

## Step 1 — Install the basics (once)
1. **Python 3.11+** — download from https://www.python.org/downloads/ and install. On Windows, tick "Add Python to PATH" during install.
2. **Git** — https://git-scm.com/downloads (just accept the defaults).
3. **A code editor** — VS Code is free: https://code.visualstudio.com/
4. **Claude Code** — follow Anthropic's install guide at https://docs.claude.com/en/docs/claude-code . You'll sign in with your Claude account.

*If any install step is confusing, that's fine — in Step 4 you can literally ask Claude Code "help me finish installing the prerequisites" and it will guide you.*

---

## Step 2 — Put this project under version control
Open a terminal **in this folder** (in VS Code: File → Open Folder → choose this folder, then Terminal → New Terminal) and run:
```bash
git init
git add .
git commit -m "Starter scaffold + spec"
```
Optional but recommended: create a free GitHub account, make a **private** repo, and follow GitHub's "push an existing repository" instructions so your code is backed up online.

---

## Step 3 — Run the skeleton once (to see it work)
In the terminal, in this folder:
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
uvicorn backend.main:app --reload
```
Open **http://localhost:8000** — you'll see the prototype UI. Open **http://localhost:8000/docs** — you'll see the API. Press `Ctrl+C` in the terminal to stop it.

> Seeing the page = your machine is set up correctly. The buttons won't pull real jobs yet — that's the build.

---

## Step 4 — Get your API keys (do the free ones now, paid ones later)
You enter most keys **inside the app** (Data Sources tab) once it's built, except the LLM key which goes in `.env`.

**Now (free, needed for the core app):**
- **Anthropic (LLM parsing)** — https://console.anthropic.com/ → create an API key → paste it into `.env` as `ANTHROPIC_API_KEY`. This is the one key that lives in `.env`.
- **Adzuna (free jobs)** — https://developer.adzuna.com/ → register an app → you'll get an **App ID** and **App Key**.
- **USAJOBS (free, optional)** — https://developer.usajobs.gov/ → request a key.
- **Greenhouse & Lever** — nothing to do; they're keyless public boards.

**Later (paid, only if you want broader coverage):**
- **SerpApi / Google Jobs** — https://serpapi.com/ → subscribe (~$75/mo) → copy your private API key.
- **Indeed vendor** — e.g. https://brightdata.com/ → subscribe → get an API token. (Note the terms-of-service caveat in the spec, section 5.)

Keep every key somewhere safe (a password manager). Never paste keys into chat, email, or commit them to Git.

---

## Step 5 — Build it with Claude Code
In the terminal, in this folder, start Claude Code (e.g. type `claude`). Then open
**`first-prompts-for-claude-code.md`** and paste the prompts in order. Claude Code will read
`CLAUDE.md` and the spec automatically, implement the `TODO`s, run the app, and fix issues as you go.
Work in small steps; after each working change, commit (`git add . && git commit -m "..."`)
or just tell Claude Code to commit for you.

---

## Step 6 — Put it online (when it works locally)
The easiest beginner hosts are **Render** (https://render.com) or **Railway** (https://railway.app).
Ask Claude Code: *"Help me deploy this FastAPI app to Render, including setting my environment
variables and switching the database to Postgres."* It will walk you through it.

---

## If you get stuck
Copy the exact error text into Claude Code and say what you were doing. Errors are normal and
fixable — describing them precisely is the whole skill. You've got this.
