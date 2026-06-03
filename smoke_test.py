"""Backend smoke test. Run:  .venv\\Scripts\\python.exe smoke_test.py
Exercises auth gate, profile, sources (connect+encrypt), scoring, leads, reset.
Safe to delete; it uses a throwaway test DB."""
import os
os.environ["DATABASE_URL"] = "sqlite:///./_smoke.db"
if os.path.exists("_smoke.db"):
    os.remove("_smoke.db")

from fastapi.testclient import TestClient
import backend.main as m
from backend import scoring

m.init_db()                      # startup event doesn't fire without the context manager
c = TestClient(m.app)

# unauthenticated protected route -> 401
assert c.get("/api/profile").status_code == 401
print("gate: protected route returns 401 OK")

assert c.get("/api/auth/status").json() == {"passcode_set": False}

tok = c.post("/api/auth/set", json={"passcode": "test1234"}).json()["token"]
assert tok
H = {"Authorization": f"Bearer {tok}"}
print("auth: passcode set, token issued OK")

assert c.get("/api/profile", headers={"Authorization": "Bearer bogus"}).status_code == 401
print("auth: bogus token rejected OK")

prof = {
    "role": {"narrative": "VP comms", "derived": "VP of Communications, Director", "priority": 5},
    "salary": {"narrative": "~140k", "derived": "$140k", "priority": 2},
    "skills": {"narrative": "", "derived": "media relations, messaging", "priority": 4},
    "dream": {"narrative": "", "derived": "United Way, Red Cross", "priority": 3},
    "location": {"narrative": "", "derived": "Denver, CO; Remote", "priority": 3},
}
assert c.put("/api/profile", json={"profile": prof, "intro": "hi"}, headers=H).json()["ok"]
assert c.get("/api/profile", headers=H).json()["profile"]["role"]["priority"] == 5
print("profile: save/read OK")

src = {s["key"]: s for s in c.get("/api/sources", headers=H).json()["sources"]}
assert set(src) == {"adzuna", "greenhouse", "lever", "usajobs", "googlejobs", "indeed"}
assert src["greenhouse"]["on"] and src["greenhouse"]["connected"]
assert not src["adzuna"]["connected"]
print("sources: list + keyless defaults OK")

assert c.post("/api/sources/adzuna/connect", json={"app_id": "abc123", "app_key": "secretkey9999"}, headers=H).json()["ok"]
src2 = {s["key"]: s for s in c.get("/api/sources", headers=H).json()["sources"]}
assert src2["adzuna"]["connected"] and src2["adzuna"]["on"]
print("sources: connect+encrypt+enable OK, hint =", src2["adzuna"]["cred_hint"])

# verify creds are actually encrypted at rest in the DB
from sqlmodel import Session
from backend.models import engine, get_state, jload
with Session(engine) as s:
    raw = jload(get_state(s).sources_json, {})["adzuna"]["creds"]
assert raw.startswith("enc:"), f"creds not encrypted: {raw[:12]}"
assert "secretkey9999" not in raw
print("sources: creds encrypted at rest OK")

hi = scoring.score_lead({"title": "VP of Communications", "company": "United Way", "location": "Remote (US)", "salary": "$160k-$190k", "description": "media relations messaging"}, prof)
lo = scoring.score_lead({"title": "Communications Intern", "company": "Random Co", "location": "Tulsa, OK", "salary": "$40k", "description": "entry level"}, prof)
print(f"scoring: senior/dream lead {hi} vs junior lead {lo}")
assert hi > lo

add = c.post("/api/leads/add", json={"company": "Habitat", "title": "Executive Director", "status": "in_progress"}, headers=H).json()
assert add["ok"]
lid = add["lead"]["id"]
leads = c.get("/api/leads", headers=H).json()["leads"]
assert any(l["id"] == lid and l["addedManually"] for l in leads)
print("leads: manual add OK")

assert c.post(f"/api/leads/{lid}/status", json={"status": "archived", "reasons": ["Pay too low"]}, headers=H).json()["ok"]
arch = [l for l in c.get("/api/leads?status=archived", headers=H).json()["leads"] if l["id"] == lid][0]
assert arch["reasons"] == ["Pay too low"]
print("leads: status + reject reasons OK")

det = c.post("/api/jobs/extract", json={"text": "Director of Communications at United Way\nRemote (US)\n$130k-$165k"}, headers=H).json()["details"]
print("extract (heuristic):", det.get("title"), "|", det.get("salary"))

rr = c.post("/api/leads/refresh", headers=H).json()
print("refresh:", {k: rr[k] for k in ("found", "added")}, "errors:", rr["errors"][:1])

assert c.post("/api/reset", headers=H).json()["ok"]
assert c.get("/api/auth/status").json()["passcode_set"] is False
assert c.get("/api/leads", headers=H).json()["leads"] == []
print("reset: wiped OK")

print("\nALL BACKEND CHECKS PASSED")
