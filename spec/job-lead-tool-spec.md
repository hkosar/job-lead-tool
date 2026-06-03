# Job Lead Tool — Consolidated Build Spec (v2)

*Developer-ready specification. Supersedes the v1 feasibility draft. Written from the working prototype `job-lead-dashboard.html`, which is the functional reference for every flow described here.*

---

## 1. What it is

A single-candidate, web-based job-search operations tool. One job seeker (the "candidate") uses it via a link to: build a profile (from a resume, a free-text narrative, and/or 14 weighted intake questions), receive on-demand **batches** of matching job leads, approve/reject them with feedback that retrains ranking, and manage every resulting application through a pipeline. It is operated by the candidate themselves; it is reusable for the next person via a full **Reset**.

---

## 2. Locked decisions

These were decided with the product owner and are firm for v1:

- **Single active candidate.** One profile at a time. No multi-tenant/multi-candidate management. "Reuse" = a Reset that wipes everything for the next person.
- **Candidate-operated, link access, one passcode.** No accounts or role split. The site is reached by URL and protected by a single passcode the candidate sets on first visit. (Prototype enforces this client-side; **production must enforce it server-side** — see §9.)
- **In-dashboard delivery only.** Lead batches appear in the app's Leads tab. No email sending in v1 (this removes the original "emailed questionnaire" step — intake is in-app).
- **Hosted LLM parsing.** The resume and the free-text narrative are parsed by a hosted LLM (e.g. Claude) into draft profile answers. Requires a privacy notice; resume/PII leaves the server to the model provider.
- **Transparent weighted scoring for v1.** No ML. A readable weighted score (see §7) that the candidate's importance weights and rejection feedback adjust.
- **API keys stored encrypted server-side**, never in the browser.
- **Sourcing starts on free Tier A feeds**, paid feeds connected on demand (see §5).
- **Competitor portal-check (original "step 5") is a later phase.** Returns real Yes/No only for orgs on queryable ATSs (Greenhouse/Lever), "Unknown" otherwise.

---

## 3. User flows (all in-dashboard)

### 3.1 Passcode gate
On load, if no passcode is set, the candidate sets one (4+ chars); on later visits they enter it. Reset clears it so the next person sets their own. The gate is a full-screen overlay; nothing behind it is usable until unlocked.

### 3.2 Intake — Candidate Profile tab (narrative + weighted)
14 questions, answered in plain language. Each non-trivial question has:
- a **narrative** free-text answer,
- a collapsible **"What we understood"** showing the structured criteria we'll actually search on (editable), and
- an **importance slider 1–5** (1 = flexible / widen the search; 5 = firm / hold the line).

Question 1 is a **resume upload**; directly beneath it is an optional **free-text "describe yourself" box**. Either one, when submitted, is parsed by the LLM and used to **draft answers only for questions the user hasn't filled in** — it never overwrites entries the user has typed. The candidate then reviews/corrects.

The importance model is the key design principle: pay is a **target with an importance**, not a hard floor. A low weight tells the engine to widen the search around that preference; a high weight holds the line.

A **Reset for a new candidate** action lives at the bottom of this tab (red, confirm-gated): wipes profile, resume, leads, pipeline, connected keys, and passcode.

### 3.3 Leads tab — on-demand batches
The candidate enters a batch size N ("show me N leads") and builds a batch. The top-N unreviewed leads from **enabled sources**, ranked by match score, are shown. Each lead card has:
- title (links to the posting), org, location, match score (0–100), salary, source, and a **coverage tag** ("data auto-verified" vs "needs your check"),
- a short **preview** (explicitly a quick-scan to weed out obvious no's),
- a prominent **"View full job ad"** button (the candidate opens the real ad before deciding),
- **Approve → pipeline**, and **Reject** (opens a **multi-select** reason picker with common reasons **plus a custom free-text reason**; confirm to archive).

Possible duplicates (same org+title already engaged) are flagged.

### 3.4 Pipeline tab
Kanban of only approved/added leads, columns: **In Progress, App Complete, Round 1, Round 2, Round 3, Archived** (rejected leads land in Archived with their reasons). Each card has a status dropdown and a link to the full ad. "In Progress" is where the candidate resumes unfinished applications.

### 3.5 Add a Job tab
Paste a posting link → the system tries to read it automatically (works for keyless ATS boards; for sites that block reading like Indeed/LinkedIn it asks the candidate to paste the description, which the LLM parses) → confirm details → choose a stage → it's added to the pipeline. Adding an org then offers to **expand the search**: scan that org and similar organizations for more openings (feeds new leads into the Leads tab). Adding an "already applied" job also drives **dedup** and **same-org recommendations** on the dashboard.

### 3.6 Data Sources tab
Per-source on/off switches with a live monthly-cost meter. Each source shows its tier (Free/Paid), cost, description, and **connection state**. Key-required sources must be **connected** (credentials entered) before they can be enabled; saving a key connects and auto-enables the source. Keyless boards (Greenhouse/Lever) need no key. Disabling a source removes its leads from the batch queue. (See §5.)

### 3.7 Dashboard tab
Stat cards (new leads, active pipeline, applications submitted, in interviews, archived), a **same-org recommendations** panel (clickable to the full ad), a **feedback signal** panel (approval rate + rejection-reason tally), and a **search-summary narrative** — a prose profile of the candidate that blends their stated profile with what their approve/reject behavior reveals, rewritten as behavior accumulates.

---

## 4. Data model

Single-candidate, so one profile object plus collections.

- **profile** — keyed by question id; each value `{ narrative, derived, priority(1–5) }`. Question ids: `resume, name, role, location, salary, skills, exclude, industries, size, motivation, dream, auth, experience, quota`. Plus `intro` (the free-text narrative) and `passcode` (server-side, hashed, in production).
- **lead** — `{ id, title, company, location, salary, source, sourceKey, ats, portal(yes|no|unknown), score, status, reason, reasons[], url, addedManually, dateFound, datePresented }`. `status ∈ new | in_progress | app_complete | round1 | round2 | round3 | archived`.
- **source config** — per source `{ on, connected, creds{} }` (creds encrypted server-side).
- **feedback** — derivable from archived leads' `reasons[]`; persist explicitly if you want longitudinal analytics.
- **batch history** (recommended for v1.1) — which leads were shown when, to avoid repeats and measure approval trends.

---

## 5. Source adapters + credential model

Each source is a **pluggable adapter** behind a common interface (`search(profile) -> leads[]`, `needsKey`, `fields[]`, `connect(creds)`). A source only runs — and only bills — when enabled, and key-required sources can't enable without valid credentials.

| Source | Tier | Cost | Credentials | Notes |
|---|---|---|---|---|
| Adzuna | Free | $0 | App ID + App Key (free signup) | Aggregated board listings. Workhorse free feed. |
| Greenhouse boards | Free | $0 | **None (keyless)** | Public JSON per employer board. Powers Yes/No portal checks. |
| Lever boards | Free | $0 | **None (keyless)** | Public JSON, supports basic filters. |
| USAJOBS | Free | $0 | API key + contact email (User-Agent) | Government/public-sector roles. |
| Google Jobs (SerpApi) | Paid | ~$75/mo (5k searches) | SerpApi private key | LinkedIn/ZipRecruiter/Glassdoor/company sites. **Excludes Indeed.** |
| Indeed (data vendor) | Paid | ~$45/mo (usage-based) | Vendor API token (+ optional dataset id) | Indeed-exclusive postings via licensed vendor (Bright Data, etc.). |

**Sourcing strategy:** start free (Adzuna + Greenhouse + Lever). Add SerpApi for broad paid coverage. Add the Indeed vendor only if Indeed-exclusive postings matter for the candidate's field. **Critical fact:** Indeed is **not** part of Google for Jobs, so SerpApi does **not** cover Indeed — Indeed needs its own adapter. ([Indeed not in Google for Jobs](https://jobiak.ai/blog/google-for-jobs-vs-indeed-could-indeed-put-google-for-jobs-out-of-a-job/), [Indeed Publisher API deprecated](https://developer.indeed.com/docs/publisher-jobs/get-job), [SerpApi pricing](https://serpapi.com/pricing), [Bright Data job APIs](https://brightdata.com/blog/web-data/best-job-apis))

**Compliance note:** scraping Indeed (even via a vendor) is a ToS gray area; the vendor runs the scraping but does not fully indemnify a downstream consumer. Acceptable at single-candidate scale; confirm with counsel before broader use.

**Per-candidate cost model:** $0 (free only) → ~$75/mo (+ Google Jobs) → ~$120/mo (+ Indeed).

---

## 6. LLM parsing

Two entry points feed the same parser: (a) resume upload (extract text, then prompt), (b) the free-text narrative box. The LLM returns structured drafts for the 14 fields (`narrative` + `derived` per question). The app then **only fills questions the user hasn't answered** — never overwrites user input. Importance weights are always the user's to set.

- Provider: hosted LLM (Claude recommended). Send only the resume/narrative text, not unrelated PII.
- Privacy notice required: state that resume text is sent to the model provider for parsing.
- Resume text extraction: server-side (PDF/DOCX → text) before the LLM call.

---

## 7. Scoring engine (v1, transparent)

`score = keyword fit (must-have/nice-to-have) + location fit + seniority fit + salary fit + org affinity − rejection-pattern penalties`, each term weighted by the candidate's **importance** for that preference (low importance shrinks that term's influence; high importance increases it and can hard-filter). Rejection `reasons[]` accumulate penalties (e.g. repeated "pay too low" down-weights low-salary leads). Keep it readable and debuggable; revisit learned weights only if volume justifies it.

---

## 8. Architecture & recommended stack

Deliberately small (one candidate, no multi-tenant):

- **Frontend:** SPA mirroring the prototype's tabs. The prototype HTML is the UX reference.
- **Backend:** lightweight service (Python/FastAPI or Node/Express): serves the app, runs source adapters, performs LLM parsing, computes scores, exposes lead/pipeline/profile/source APIs.
- **DB:** Postgres (SQLite acceptable to start) for the §4 model.
- **Secrets:** API keys + passcode hash encrypted at rest (e.g. KMS / libsodium). Never sent to the browser.
- **Scheduler (optional v1.1):** periodic source pulls to pre-stage the batch pool.
- **Hosting:** single small instance (Render/Railway/Fly.io).

---

## 9. Security & privacy

- **Passcode** must be enforced server-side: store a hash, gate all data APIs on a valid session, rate-limit attempts. The prototype's client-side gate is illustrative only.
- **Link access** means the URL is the primary secret; the passcode is the real protection. Use an unguessable URL + the passcode.
- **PII:** the resume and contact info are sensitive. Encrypt at rest; the Reset must hard-delete them. Disclose LLM processing.
- **Keys:** encrypted server-side; never exposed to the client; cleared on Reset.

---

## 10. Build phases

1. **Phase 1 — core app:** profile (14 weighted Qs), Leads batch + approve/reject, Pipeline, Add-a-Job, Dashboard summary, passcode gate, Reset. Free Tier A adapters (Adzuna/Greenhouse/Lever) + transparent scoring + LLM parsing.
2. **Phase 2 — paid sourcing:** SerpApi and Indeed-vendor adapters with the connect/credential UI and cost meter.
3. **Phase 3 — competitor portal-check (original step 5):** competitor discovery from seed orgs; Yes/No for Greenhouse/Lever, Unknown otherwise.
4. **Phase 4 — polish:** batch history/anti-repeat, analytics on approval trends, optional scheduled pulls.

---

## 11. Reference

The prototype `job-lead-dashboard.html` is the living reference for every flow, label, and state above (light theme, six tabs, sample data for a nonprofit-communications executive candidate). Build to match its behavior; this document explains the production concerns the static prototype can't (server-side auth, real adapters, LLM calls, encryption).

*Pricing and API-availability facts checked June 2026; re-verify before committing to providers.*
