"""Data model + persistence (SQLite via SQLModel for v1).

Single-candidate design: one AppState row, many Lead rows. Source config lives in
AppState.sources_json. Reset = delete all leads + clear AppState. Move to Postgres
later by changing DATABASE_URL only (SQLModel/SQLAlchemy handles the rest).
"""
from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, create_engine, Session, select
import json, os

# Default the SQLite file to the project root (next to backend/) by absolute path,
# so the database lives in a stable place regardless of the launch directory.
_DEFAULT_DB = "sqlite:///" + os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "joblead.db")
DATABASE_URL = os.getenv("DATABASE_URL") or _DEFAULT_DB
# Cloud hosts (Render/Heroku/Railway) hand out URLs starting with "postgres://";
# SQLAlchemy 2.0 needs the "postgresql://" form. Normalize so cloud Postgres just works.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
                       if DATABASE_URL.startswith("sqlite") else {})

# Profile is stored as a single JSON blob keyed by question id (see spec section 4).
class AppState(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    passcode_hash: str = ""          # bcrypt hash; empty == not set yet
    profile_json: str = "{}"         # {questionId: {narrative, derived, priority}}
    intro: str = ""                  # free-text "describe yourself" narrative
    sources_json: str = "{}"         # {sourceKey: {on, connected, creds(encrypted)}}

class Lead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    company: str
    location: str = ""
    salary: str = ""
    url: str = "#"
    description: str = ""
    source_key: str = ""             # adapter key, e.g. "adzuna"
    source: str = ""                 # display name shown in the UI, e.g. "Adzuna"
    ats: str = "unknown"             # greenhouse | lever | workday | custom | unknown
    portal: str = "unknown"          # yes | no | unknown
    score: float = 0.0
    status: str = "new"              # new|in_progress|app_complete|round1|round2|round3|archived
    reasons_json: str = "[]"         # list of rejection reasons (multi-select + custom)
    added_manually: bool = False
    date_found: str = ""             # ISO timestamp when first stored
    date_presented: str = ""         # ISO timestamp when last shown in a batch ("" = never)
    batch_id: int = 0                # number of the last batch this lead appeared in (0 = none)

def init_db():
    SQLModel.metadata.create_all(engine)
    _migrate_columns()
    with Session(engine) as s:
        if not s.get(AppState, 1):
            s.add(AppState(id=1)); s.commit()

def _migrate_columns():
    """Add any columns introduced after an existing joblead.db was created.
    SQLModel.create_all won't ALTER existing tables, so do it by hand for SQLite."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    from sqlalchemy import text
    wanted = {"source": "TEXT DEFAULT ''", "date_found": "TEXT DEFAULT ''",
              "date_presented": "TEXT DEFAULT ''", "batch_id": "INTEGER DEFAULT 0"}
    with engine.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(lead)").fetchall()}
        for name, ddl in wanted.items():
            if name not in cols:
                conn.exec_driver_sql(f"ALTER TABLE lead ADD COLUMN {name} {ddl}")
        conn.commit()

def get_state(s: Session) -> AppState:
    return s.get(AppState, 1)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# convenience JSON helpers
def jload(v, default):
    try: return json.loads(v)
    except Exception: return default
def jdump(v): return json.dumps(v)
