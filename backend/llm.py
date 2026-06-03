"""LLM parsing of resume / free-text narrative into draft profile answers, plus
single job-posting extraction for the Add-a-Job flow.

Uses the Anthropic API. Set ANTHROPIC_API_KEY in your environment (.env).

PRIVACY: this sends the resume/narrative text to Anthropic. Disclose in a privacy
notice. Send only the resume/narrative, not unrelated PII.
"""
from __future__ import annotations
import os, json, io, re, zipfile

# Question ids the model should fill (must match models/profile + spec section 4).
QUESTION_IDS = ["role", "location", "salary", "skills", "exclude", "industries",
                "size", "motivation", "dream", "auth", "experience", "quota"]

SYSTEM = (
    "You extract a job-seeker profile from a resume or self-description. "
    "Return ONLY JSON: an object keyed by these ids " + ",".join(QUESTION_IDS) +
    ". Each value is {\"narrative\": short first-person sentence, \"derived\": "
    "comma-separated structured criteria}. Do not invent facts not supported by the text."
)

JOB_SYSTEM = (
    "You extract a single job posting's key fields from pasted text. "
    "Return ONLY JSON with keys: company, title, location, salary, description. "
    "salary as a short string like '$120k-$150k' or '' if not stated. "
    "description = a 1-2 sentence summary. Do not invent facts."
)


def _client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=key)
    except Exception as e:
        print("Anthropic client init failed:", e)
        return None


def _json_from(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < 0:
        return {}
    try:
        return json.loads(raw[start:end + 1])
    except Exception:
        return {}


def parse_to_profile(text: str) -> dict:
    """Return {qid: {narrative, derived}} drafted from the text. Empty dict on failure."""
    client = _client()
    if not client or not (text or "").strip():
        return {}
    try:
        msg = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            max_tokens=1500,
            system=SYSTEM,
            messages=[{"role": "user", "content": text[:20000]}],
        )
        return _json_from(msg.content[0].text)
    except Exception as e:
        print("LLM parse failed:", e)
        return {}


def parse_job_posting(text: str) -> dict:
    """Extract one job's fields from pasted description text. Falls back to a
    regex heuristic when no LLM key is configured."""
    client = _client()
    if client and (text or "").strip():
        try:
            msg = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
                max_tokens=600,
                system=JOB_SYSTEM,
                messages=[{"role": "user", "content": text[:15000]}],
            )
            data = _json_from(msg.content[0].text)
            if data:
                return data
        except Exception as e:
            print("LLM job parse failed:", e)
    return _heuristic_job(text)


def _heuristic_job(text: str) -> dict:
    """No-LLM fallback: pull obvious fields with regex (mirrors the prototype)."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    title = (lines[0][:90] if lines else "")
    company = ""
    m = re.search(r"(?:organization|company)[:\-]\s*([A-Za-z0-9.&'\- ]{2,40})", text, re.I)
    if m:
        company = m.group(1).strip()
    else:
        m = re.search(r"\bat\s+([A-Z][A-Za-z0-9.&'\- ]{2,40})", text)
        if m:
            company = m.group(1).strip()
    loc = ""
    m = re.search(r"\b(Remote(?:\s*\(US\))?|[A-Z][a-z]+,\s?[A-Z]{2})\b", text)
    if m:
        loc = m.group(1)
    sal = ""
    m = re.search(r"\$\s?\d[\d,]*\s?[kK]?(?:\s?[–\-]\s?\$?\d[\d,]*\s?[kK]?)?", text)
    if m:
        sal = m.group(0)
    return {"company": company, "title": title, "location": loc, "salary": sal,
            "description": (text or "")[:300]}


def extract_resume_text(file_bytes: bytes, filename: str) -> str:
    """Pull plain text from an uploaded resume (PDF / DOCX / TXT)."""
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(file_bytes)).pages)
        if name.endswith(".docx"):
            return _docx_text(file_bytes)
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        print("resume extract failed:", e)
        return ""


def _docx_text(file_bytes: bytes) -> str:
    """Extract text from a .docx without extra deps: a .docx is a zip whose
    word/document.xml holds the text inside <w:t> tags."""
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
    # paragraphs end at </w:p>; turn them into newlines, then strip remaining tags.
    xml = xml.replace("</w:p>", "\n")
    text = re.sub(r"<[^>]+>", "", xml)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
