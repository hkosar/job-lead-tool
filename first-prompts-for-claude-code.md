# First prompts for Claude Code

Paste these into Claude Code one at a time, in order. Wait for each to finish and show you a
working result before moving on. It's fine to say "that errored, here's the message: ..." —
that's how this works.

### 0. Orient
```
Read CLAUDE.md and spec/job-lead-tool-spec.md, then summarize the build plan back to me
in plain language and tell me what you'll do first. Don't write code yet.
```

### 1. Get it running locally
```
Set up a Python virtual environment, install requirements.txt, create my .env from
.env.example, and run the app. Walk me through anything I need to do, then confirm the
page loads at localhost:8000.
```

### 2. Connect the frontend to the backend
```
Right now frontend/index.html uses localStorage and sample data. Wire the Candidate Profile,
Leads, Pipeline, Add-a-Job, Data Sources, and Dashboard tabs to the backend API in backend/main.py
instead. Keep the exact look and behavior. Do one tab at a time and let me test each before moving on.
```

### 3. First real data source (free)
```
Implement the Adzuna adapter (backend/sources/adzuna.py) against their real API using my
ADZUNA keys, and finish /api/leads/refresh so it searches, scores with scoring.py, de-dupes,
and saves leads. Then let me build a batch in the UI and see real jobs.
```

### 4. Resume & narrative parsing
```
Wire /api/profile/parse so uploading a resume or submitting the "describe yourself" narrative
drafts answers via llm.py, filling ONLY the profile questions I haven't answered, never
overwriting my entries. Test it with a sample resume.
```

### 5. Real login
```
Replace the client-side passcode with real server-side auth: hash the passcode, issue a session
token on login, require it on all /api routes except /api/auth/*, and rate-limit attempts.
```

### 6. Keep going
```
Add the Greenhouse and Lever adapters next, then the paid SerpApi and Indeed adapters with the
connect/credentials flow. Follow the build order in CLAUDE.md. Commit after each working step.
```

### Anytime
```
Explain what you just changed and why, in plain language, and commit it with a clear message.
```
