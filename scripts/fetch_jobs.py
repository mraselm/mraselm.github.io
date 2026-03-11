"""
fetch_jobs.py
Fetches full-time Data & BI job listings from Jobindex.dk and Jobbank.dk
(RSS feeds) and writes them to assets/data/jobs.json.

Strategy:
  - Jobindex: quoted phrase search via RSS; Jobbank.dk: keyword search via RSS.
  - Each category runs multiple queries (EN + DA terms) and deduplicates by URL.
  - Cross-portal deduplication: a normalised title+company fingerprint ensures
    the same job posted on both portals appears only once (Jobindex preferred).
  - A title-keyword whitelist acts as a final safety filter.

Run locally:  python scripts/fetch_jobs.py
Run via CI:   GitHub Actions (.github/workflows/fetch-jobs.yml)
"""

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_PER_TYPE     = 25    # jobs to KEEP per job-type per category after filter & dedup
FETCH_PER_QUERY  = 50    # jobs to FETCH from Jobindex per individual query

# Title words that unambiguously mark a job as a student position.
# If these appear in a title during the full-time/part-time fetch phase, skip it.
STUDENT_TITLE_INDICATORS = [
    "studentermedhjælper",
    "studiejob", "student assistant", "studentjob",
]

# Job types to fetch — keys become the 'job_type' field written to jobs.json.
# Values are the Jobindex 'arbejdstid[]' URL-parameter values.
# NOTE: Jobindex RSS honours these for regular job-type filtering.
JOB_TYPES_PARAM: dict[str, str] = {
    "full-time": "Fuldtid",
    "part-time": "Deltid",
}

# Extra queries run WITHOUT an arbejdstid filter to surface
# student-assistant (studentermedhjælper / studiejob) positions per category.
STUDENT_QUERIES: dict[str, list[str]] = {
    "data analyst": [
        "studentermedhj%C3%A6lper+%22data+analyst%22",
        "studiejob+%22data+analyst%22",
        "studentermedhj%C3%A6lper+dataanalytiker",
    ],
    "business analyst": [
        "studentermedhj%C3%A6lper+%22business+analyst%22",
        "studiejob+%22business+analyst%22",
        "studentermedhj%C3%A6lper+forretningsanalytiker",
    ],
    "business intelligence": [
        "studentermedhj%C3%A6lper+%22business+intelligence%22",
        "studiejob+%22business+intelligence%22",
        "studentermedhj%C3%A6lper+%22Power+BI%22",
        "studentermedhj%C3%A6lper+%22BI+analyst%22",
    ],
    "bi specialist": [
        "studentermedhj%C3%A6lper+%22BI+specialist%22",
        "studentermedhj%C3%A6lper+%22business+intelligence%22",
        "studiejob+%22Power+BI%22",
    ],
    "data scientist": [
        "studentermedhj%C3%A6lper+%22data+scientist%22",
        "studiejob+%22data+scientist%22",
        "studentermedhj%C3%A6lper+%22machine+learning%22",
    ],
}

# Relevance filter for student jobs: the job TITLE must contain at least one keyword.
# These are broad enough to keep genuine data/BI roles while excluding unrelated
# studentermedhjælper roles (SoMe, legal, food-export, etc.) that Jobindex full-text
# search returns because the description mentions a category term.
STUDENT_TITLE_KEYWORDS: dict[str, list[str]] = {
    "data analyst": [
        "data analyst", "dataanalytiker", "data analytiker",
        "analytiker", "analyst",
    ],
    "business analyst": [
        "business analyst", "forretningsanalytiker", "businessanalytiker",
        "business analyst", "analytiker", "analyst",
    ],
    "business intelligence": [
        "business intelligence", "bi ", " bi", "power bi",
        "data analyst", "analytiker", "analyst", "data og",
    ],
    "bi specialist": [
        "bi ", " bi", "business intelligence", "power bi",
        "data analyst", "analytiker", "analyst",
    ],
    "data scientist": [
        "data scientist", "data science", "machine learning",
        "ml engineer", "ai engineer", "analytiker",
    ],
}

# Each category maps to a list of quoted-phrase queries.
# %22…%22 = URL-encoded double-quotes, forces Jobindex phrase search.
CATEGORIES: dict[str, list[str]] = {
    "data analyst": [
        "%22data+analyst%22",
        "%22senior+data+analyst%22",
        "%22junior+data+analyst%22",
        "%22advanced+data+analyst%22",
        "dataanalytiker",
    ],
    "business analyst": [
        "%22business+analyst%22",
        "%22senior+business+analyst%22",
        "%22advanced+business+analyst%22",
        "forretningsanalytiker",
    ],
    "business intelligence": [
        "%22business+intelligence%22",
        "%22BI+analyst%22",
        "%22BI+developer%22",
        "%22BI+consultant%22",
        "%22BI+manager%22",
        "%22Power+BI%22",
    ],
    "bi specialist": [
        "%22BI+specialist%22",
        "%22BI+arkitekt%22",
        "%22BI+engineer%22",
        "%22Power+BI+specialist%22",
        "%22Power+BI+developer%22",
        "%22BI+manager%22",
        "%22business+intelligence+specialist%22",
    ],
    "data scientist": [
        "%22data+scientist%22",
        "%22senior+data+scientist%22",
        "%22junior+data+scientist%22",
        "%22machine+learning+engineer%22",
        "%22ml+engineer%22",
        "%22AI+engineer%22",
        "data+science",
    ],
}

# Graduate Program queries — searches Jobindex for BI-related graduate positions.
GRADUATE_QUERIES: list[str] = [
    "%22graduate+program%22+data",
    "%22graduate+program%22+business+intelligence",
    "%22graduate+program%22+analytics",
    "%22graduate+programme%22+data",
    "%22graduate%22+%22data+analyst%22",
    "%22graduate%22+%22business+intelligence%22",
    "%22graduate%22+%22BI%22",
    "graduate+data",
    "graduate+analytiker",
]

# Title keyword whitelist — job title must contain at least one (case-insensitive).
# Keep these tight: each list reflects the most relevant titles for that role.
TITLE_KEYWORDS: dict[str, list[str]] = {
    "data analyst": [
        "data analyst",
        "dataanalytiker",
        "data analytiker",
        "advanced data analyst",
        "senior data analyst",
        "junior data analyst",
    ],
    "business analyst": [
        "business analyst",
        "forretningsanalytiker",
        "businessanalytiker",
    ],
    "business intelligence": [
        "business intelligence",
        "bi developer",
        "bi analyst",
        "bi consultant",
        "bi manager",
        "bi lead",
        "bi arkitekt",
        "power bi",
    ],
    "bi specialist": [
        "bi specialist",
        "bi developer",
        "bi analyst",
        "bi consultant",
        "bi manager",
        "bi lead",
        "bi arkitekt",
        "bi engineer",
        "business intelligence",
        "power bi",
    ],
    "data scientist": [
        "data scientist",
        "data science",
        "machine learning engineer",
        "ml engineer",
        "ai engineer",
        "deep learning",
    ],
}

# Title keywords for graduate program — must contain at least one.
GRADUATE_TITLE_KEYWORDS: list[str] = [
    "graduate",
    "trainee",
]


def is_graduate_title(title: str) -> bool:
    """Return True when a title clearly belongs to the graduate-program flow."""
    t = (title or "").lower()
    return any(kw in t for kw in GRADUATE_TITLE_KEYWORDS)

# Jobindex XML RSS endpoint — jobsoegning.xml works; /rss returns 404
# {query}, {maxcount}, and {jobtype} are filled at runtime.
RSS_URL = (
    "https://www.jobindex.dk/jobsoegning.xml"
    "?q={query}&maxcount={maxcount}&arbejdstid%5B%5D={jobtype}"
)
# Used for student queries — no arbejdstid filter applied.
RSS_URL_NOTYPE = (
    "https://www.jobindex.dk/jobsoegning.xml"
    "?q={query}&maxcount={maxcount}"
)

# Jobbank.dk (Akademikernes Jobbank) RSS endpoint — English version.
# The /en/ path returns English descriptions and focuses on English-speaker jobs.
# Returns up to 100 items per keyword query.
JOBBANK_RSS_URL = "https://jobbank.dk/en/job/rss?key={query}"

# Jobbank.dk search queries per category (plain keywords, no quotes needed).
JOBBANK_QUERIES: dict[str, list[str]] = {
    "data analyst": [
        "data+analyst",
        "dataanalytiker",
    ],
    "business analyst": [
        "business+analyst",
        "forretningsanalytiker",
    ],
    "business intelligence": [
        "business+intelligence",
        "Power+BI",
    ],
    "bi specialist": [
        "BI+specialist",
        "BI+developer",
    ],
    "data scientist": [
        "data+scientist",
        "machine+learning",
    ],
    "graduate program": [
        "graduate+program+data",
        "graduate+program+business+intelligence",
        "graduate+analytics",
        "graduate+BI",
    ],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PortfolioJobFetcher/1.0; "
        "+https://raselmia.live)"
    ),
    "Accept-Language": "da-DK,da;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ---------------------------------------------------------------------------
# Known cities — used to validate location candidates
# ---------------------------------------------------------------------------

# Maps lowercase keywords → canonical display name
_CITY_MAP: dict[str, str] = {
    # Copenhagen region
    "københavn": "Copenhagen",
    "kobenhavn": "Copenhagen",
    "copenhagen": "Copenhagen",
    "kbh": "Copenhagen",
    "nordhavn": "Copenhagen",
    "østerbro": "Copenhagen",
    "osterbro": "Copenhagen",
    "nørrebro": "Copenhagen",
    "norrebro": "Copenhagen",
    "vesterbro": "Copenhagen",
    "valby": "Copenhagen",
    "amager": "Copenhagen",
    "sydhavn": "Copenhagen",
    "frederiksberg": "Frederiksberg",
    "hellerup": "Hellerup",
    "lyngby": "Lyngby",
    "gentofte": "Gentofte",
    "glostrup": "Glostrup",
    "ballerup": "Ballerup",
    "taastrup": "Taastrup",
    "hvidovre": "Hvidovre",
    "soeborg": "Søborg",
    "søborg": "Søborg",
    "gladsaxe": "Gladsaxe",
    "brøndby": "Brøndby",
    "brondby": "Brøndby",
    "hørsholm": "Hørsholm",
    "hoersholm": "Hørsholm",
    "horsholm": "Hørsholm",
    "hillerød": "Hillerød",
    "hillerod": "Hillerød",
    "hilleroed": "Hillerød",
    "roskilde": "Roskilde",
    "ringsted": "Ringsted",
    # Aarhus region
    "aarhus": "Aarhus",
    "arhus": "Aarhus",
    "viby j": "Aarhus",
    "viby": "Aarhus",
    "risskov": "Aarhus",
    "skanderborg": "Skanderborg",
    # Funen
    "odense": "Odense",
    "svendborg": "Svendborg",
    # Jutland
    "aalborg": "Aalborg",
    "esbjerg": "Esbjerg",
    "vejle": "Vejle",
    "kolding": "Kolding",
    "horsens": "Horsens",
    "silkeborg": "Silkeborg",
    "herning": "Herning",
    "holstebro": "Holstebro",
    "randers": "Randers",
    "fredericia": "Fredericia",
    "billund": "Billund",
    "naestved": "Næstved",
    "næstved": "Næstved",
    "viborg": "Viborg",
    # Remote / hybrid
    "remote": "Remote",
    "hjemmearbejde": "Remote",
    "anywhere": "Remote",
}


def match_city_in_text(text: str) -> str:
    """Return canonical city name if any known city keyword appears in text."""
    t = _fix_mojibake(text).lower()
    for key, canonical in _CITY_MAP.items():
        if key in t:
            return _fix_mojibake(canonical)
    return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HTML_TAG    = re.compile(r"<[^>]+>")
_WHITESPACE  = re.compile(r"[ \t]+")


def _mojibake_score(text: str) -> int:
    """Higher score means text likely contains mojibake artefacts."""
    if not text:
        return 0
    needles = ("Ã", "â€™", "â€œ", "â€", "â€“", "Â")
    return sum(text.count(n) for n in needles)


def _attempt_redecode(text: str, codec: str) -> str:
    """Try to recover UTF-8 text that was decoded with the wrong codec."""
    try:
        return text.encode(codec).decode("utf-8")
    except Exception:
        return text


def _fix_mojibake(text: str) -> str:
    """Normalize common UTF-8/cp1252 and UTF-8/latin-1 mojibake patterns."""
    if not text:
        return text
    candidates = [
        text,
        _attempt_redecode(text, "cp1252"),
        _attempt_redecode(text, "latin-1"),
    ]
    return min(candidates, key=_mojibake_score)


def _decode_entities(text: str) -> str:
    """Replace common HTML entities with their characters."""
    replacements = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&apos;": "'", "&nbsp;": " ",
    }
    for ent, char in replacements.items():
        text = text.replace(ent, char)
    return re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)


def strip_html(text: str) -> str:
    """Strip HTML tags and decode entities."""
    text = _HTML_TAG.sub("", text or "")
    text = _decode_entities(text)
    text = _fix_mojibake(text)
    return text.strip()


def parse_date(date_str: str) -> str:
    """Return YYYY-MM-DD from an RFC-2822 date string."""
    if not date_str:
        return ""
    try:
        return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
    except Exception:
        clean = (date_str or "").strip()
        return clean[:10] if len(clean) >= 10 else clean


def split_title_company(raw_title: str) -> tuple[str, str]:
    """
    Jobindex RSS titles: 'Job Title (Location), Company Name'
    Split by the LAST comma to separate job title from company.
    """
    raw_title = strip_html(raw_title)
    if "," in raw_title:
        idx = raw_title.rfind(",")
        return raw_title[:idx].strip(), raw_title[idx + 1:].strip()
    if " - " in raw_title:
        parts = raw_title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return raw_title, ""


def parse_description(raw_desc: str) -> tuple[str, str]:
    """
    Extract (location, snippet) from an RSS description field.

    Jobindex RSS descriptions follow this pattern after stripping HTML:
      Line 0: Repeated job title
      Line 1: City / location (short, e.g. "Copenhagen, Hybrid position")
      Line 2+: Actual job description text

    Returns (city_string, clean_snippet).
    """
    text = strip_html(raw_desc)
    lines = [_WHITESPACE.sub(" ", ln).strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]

    location = ""
    snippet_lines: list[str] = []

    for i, line in enumerate(lines):
        if i == 0:
            # First line is the repeated title — skip for snippet
            continue
        if i == 1:
            # Second line is typically the location block
            city = match_city_in_text(line)
            if city:
                location = city
            # Don't include location line in snippet
            continue
        snippet_lines.append(line)
        if sum(len(l) for l in snippet_lines) >= 220:
            break

    snippet = " ".join(snippet_lines)[:230].strip()
    return location or "Denmark", snippet


def detect_language(text: str) -> str:
    """Return 'da' if text reads as Danish, 'en' otherwise.

    Heuristic: Danish-specific diacritics (æ, ø, å) in the snippet are a
    near-certain signal.  If absent, count high-frequency Danish function
    words; two or more hits classify the text as Danish.
    """
    if not text:
        return "en"
    t = _fix_mojibake(text).lower()
    if any(c in t for c in "æøå"):
        return "da"
    da_markers = [
        " søger ", " studentermedhjælper", " studentermedhjælper",
        " studiejob", " hos ", " hjæl", " københavn", " forretningsanalytiker",
        " konsulent", " virksomhed", " stilling", " mulighed", " bliv ",
    ]
    if any(marker in (" " + t + " ") for marker in da_markers):
        return "da"
    # Fallback: common Danish function words (padded to avoid sub-matches)
    da_words = [
        ' du ', ' dig ', ' vi ', ' er ', ' og ', ' til ',
        ' med ', ' som ', ' det ', ' den ', ' de ', ' kan ',
        ' vil ', ' har ', ' din ', ' dit ', ' hvad ', ' ikke ',
    ]
    hits = sum(1 for w in da_words if w in ' ' + t + ' ')
    return 'da' if hits >= 2 else 'en'


def title_matches(title: str, keywords: list[str]) -> bool:
    """Return True if title contains at least one whitelisted keyword."""
    t = title.lower()
    return any(kw in t for kw in keywords)


# Danish / international corporate-name suffixes stripped for dedup.
_CORP_SUFFIX_RE = re.compile(
    r'[\s,]*\b(?:a/s|aps|a\.s\.?|i/s|k/s|p/s|ltd|inc|gmbh|se)\s*$',
    re.IGNORECASE,
)


def _normalise_for_dedup(title: str, company: str) -> tuple[str, str]:
    """Normalise title and company for cross-portal dedup.

    Handles formatting differences between Jobindex and Jobbank.dk:
      - Jobindex titles include '(Location)' at the end → stripped
      - Jobbank titles may append 'til/hos/at <Company>' → stripped
      - Company names may have parenthetical abbreviations '(AU)' → stripped
      - Company names may differ by corporate suffixes (A/S, ApS) → stripped
    Returns (normalised_title, normalised_company) — both lowercase,
    non-alphanumeric characters removed, whitespace collapsed.
    """
    t = title.strip()
    c = company.strip()

    # Strip trailing parenthetical from title (Jobindex adds location)
    t = re.sub(r'\s*\([^)]*\)\s*$', '', t)

    # Strip trailing parenthetical from company ("Aarhus Universitet (AU)" → "Aarhus Universitet")
    c = re.sub(r'\s*\([^)]*\)\s*$', '', c)

    # Strip corporate suffixes from company
    c_norm = _CORP_SUFFIX_RE.sub('', c).strip()

    # Strip trailing "til/hos/at/for <company>" from title (Jobbank pattern).
    t_low = t.lower()
    stripped = False
    for prep in ('til', 'hos', 'at', 'for'):
        if stripped:
            break
        for cv in (c.lower().strip(), c_norm.lower()):
            suf = f' {prep} {cv}'
            if cv and t_low.endswith(suf):
                t = t[:len(t) - len(suf)]
                stripped = True
                break

    # Build normalised strings
    t_out = re.sub(r"[^a-z0-9æøå ]+", "", t.lower())
    t_out = re.sub(r"\s+", " ", t_out).strip()
    c_out = re.sub(r"[^a-z0-9æøå ]+", "", c_norm.lower())
    c_out = re.sub(r"\s+", " ", c_out).strip()
    return t_out, c_out


def job_fingerprint(title: str, company: str) -> str:
    """Return a normalised key for cross-portal deduplication."""
    t, c = _normalise_for_dedup(title, company)
    return f"{t} @ {c}"


class _CrossPortalDedup:
    """Cross-portal deduplication using exact fingerprints + fuzzy fallback.

    Tier 1 (fast): exact normalised fingerprint lookup.
    Tier 2 (slow): token-overlap matching that catches company-name
    variations like 'BEC' vs 'BEC Financial Technologies'.
    """

    def __init__(self) -> None:
        self._fps: set[str] = set()
        self._pairs: list[tuple[set[str], set[str]]] = []

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(text.split()) if text else set()

    def add(self, title: str, company: str) -> None:
        fp = job_fingerprint(title, company)
        self._fps.add(fp)
        t_norm, c_norm = _normalise_for_dedup(title, company)
        self._pairs.append(
            (self._tokenize(t_norm), self._tokenize(c_norm))
        )

    def is_duplicate(self, title: str, company: str) -> bool:
        # Tier 1: exact fingerprint
        if job_fingerprint(title, company) in self._fps:
            return True
        # Tier 2: fuzzy token-overlap
        t_norm, c_norm = _normalise_for_dedup(title, company)
        new_tt = self._tokenize(t_norm)
        new_ct = self._tokenize(c_norm)
        if not new_tt:
            return False
        for ext_tt, ext_ct in self._pairs:
            if not ext_tt:
                continue
            # Company: one token set must be a subset of the other.
            # When one company is empty, require near-exact title match.
            if new_ct and ext_ct:
                if not (new_ct <= ext_ct or ext_ct <= new_ct):
                    continue
            elif new_ct or ext_ct:
                # One side empty — only allow if titles are nearly identical
                overlap = len(new_tt & ext_tt) / max(len(new_tt), len(ext_tt))
                if overlap >= 0.9:
                    return True
                continue
            else:
                # Both empty — not reliable
                continue
            # Title: ≥ 75 % token overlap
            overlap = len(new_tt & ext_tt) / max(len(new_tt), len(ext_tt))
            if overlap >= 0.75:
                return True
        return False


# ---------------------------------------------------------------------------
# Jobbank.dk helpers
# ---------------------------------------------------------------------------

_JOBBANK_DESC_RE = re.compile(
    r"^(?P<jobtype>.+?)\s+hos\s+(?P<company>.+?),\s*(?P<location>.+?)"
    r"\s*\(Ansøgningsfrist:\s*(?P<deadline>[^)]+)\)\s*$",
)

# English variant: "{JobType} at {Company}, {Location} (Apply by: {Date})"
_JOBBANK_DESC_EN_RE = re.compile(
    r"^(?P<jobtype>.+?)\s+at\s+(?P<company>.+?),\s*(?P<location>.+?)"
    r"\s*\(Apply by:\s*(?P<deadline>[^)]+)\)\s*$",
)


def parse_jobbank_description(desc: str) -> tuple[str, str, str, str]:
    """Parse a Jobbank.dk RSS description string.

    English: '{JobType} at {Company}, {Location} (Apply by: {Date})'
    Danish:  '{JobType} hos {Company}, {Location} (Ansøgningsfrist: {Date})'
    Returns (job_type, company, location, deadline).
    """
    m = _JOBBANK_DESC_EN_RE.match(desc.strip())
    if not m:
        m = _JOBBANK_DESC_RE.match(desc.strip())
    if not m:
        return "", "", "Denmark", ""
    raw_type = m.group("jobtype").strip().lower()
    company = m.group("company").strip()
    location_raw = m.group("location").strip()
    deadline = m.group("deadline").strip()

    # Map Danish/English job type labels to our standard keys
    if "studiejob" in raw_type or "studenter" in raw_type or "student" in raw_type:
        jtype = "student"
    elif "deltid" in raw_type or "part-time" in raw_type:
        jtype = "part-time"
    else:
        jtype = "full-time"

    location = match_city_in_text(location_raw) or "Denmark"
    return jtype, company, location, deadline


def fetch_jobbank_rss(query: str) -> list[ET.Element]:
    """Fetch and parse one Jobbank.dk RSS query."""
    url = JOBBANK_RSS_URL.format(query=query)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=45)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        print(f"    [{len(items):2}] {url}")
        return items
    except requests.RequestException as exc:
        print(f"    [ERR] {exc}")
        return []
    except ET.ParseError as exc:
        print(f"    [ERR] XML: {exc}")
        return []


def parse_jobbank_item(item: ET.Element) -> dict | None:
    """Convert one Jobbank.dk RSS <item> to a job dict."""
    get = lambda tag: _fix_mojibake((item.findtext(tag) or "").strip())
    title = strip_html(get("title"))
    link   = get("link")
    desc   = strip_html(get("description"))
    pub    = get("pubDate")

    if not link:
        return None

    jtype, company, location, _deadline = parse_jobbank_description(desc)
    lang = detect_language(title + " " + desc)

    return {
        "title":    title,
        "company":  company,
        "location": location,
        "url":      link,
        "posted":   parse_date(pub),
        "snippet":  desc[:230].strip(),
        "lang":     lang,
        "source":   "jobbank",
        "job_type": jtype,
    }


# ---------------------------------------------------------------------------
# Fetch & parse
# ---------------------------------------------------------------------------

def fetch_rss(query: str, job_type_param: str | None = "Fuldtid") -> list[ET.Element]:
    """Fetch and parse one RSS query. job_type_param=None omits the filter."""
    if job_type_param:
        url = RSS_URL.format(query=query, maxcount=FETCH_PER_QUERY, jobtype=job_type_param)
    else:
        url = RSS_URL_NOTYPE.format(query=query, maxcount=FETCH_PER_QUERY)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        print(f"    [{len(items):2}] {url[-90:]}")
        return items
    except requests.RequestException as exc:
        print(f"    [ERR] {exc}")
        return []
    except ET.ParseError as exc:
        print(f"    [ERR] XML: {exc}")
        return []


def parse_item(item: ET.Element) -> dict | None:
    """Convert one RSS <item> to a job dict. Returns None if no link."""
    get = lambda tag: _fix_mojibake((item.findtext(tag) or "").strip())
    raw_title = get("title")
    link      = get("link")
    desc      = get("description")
    pub_date  = get("pubDate")

    if not link:
        return None

    title, company = split_title_company(raw_title)

    # Extract clean location and actual description snippet
    location, snippet = parse_description(desc)

    # If description lines didn't yield a city, scan full description text
    if location == "Denmark":
        city = match_city_in_text(strip_html(desc))
        if city:
            location = city

    lang = detect_language(title + " " + snippet)

    return {
        "title":    title,
        "company":  company,
        "location": location,
        "url":      link,
        "posted":   parse_date(pub_date),
        "snippet":  snippet,
        "lang":     lang,
        "source":   "jobindex",
    }


def fetch_category(label: str, queries: list[str],
                   cross_seen: set[str],
                   cross_fingerprints: _CrossPortalDedup) -> list[dict]:
    """
    Fetch jobs for a category across student, full-time, and part-time types
    from both Jobindex and Jobbank.dk.

    Student queries use LOCAL dedup (per-category) because each STUDENT_QUERY
    already embeds the category keyword, so cross-contamination is minimal.
    This also prevents a student URL that fails one category's title filter
    from being permanently locked out of a more relevant category.

    Full-time / part-time use cross_seen so the same general posting does not
    appear under multiple category tabs.

    cross_fingerprints stores normalised title+company fingerprints to prevent
    the same job posted on both portals from appearing twice.
    """
    kws   = TITLE_KEYWORDS.get(label, [])
    s_kws = STUDENT_TITLE_KEYWORDS.get(label, [])
    student_result: list[dict] = []
    ft_result:      list[dict] = []

    # ── 1. Student jobs (per-category dedup, no arbejdstid filter) ───────────
    local_seen: set[str] = set()
    student_queries = STUDENT_QUERIES.get(label, [])
    student_jobs: list[dict] = []
    for q in student_queries:
        for item in fetch_rss(q, None):
            job = parse_item(item)
            if job and job["url"] not in local_seen:
                local_seen.add(job["url"])
                job["job_type"] = "student"
                student_jobs.append(job)

    raw_s = len(student_jobs)
    if s_kws:
        student_jobs = [j for j in student_jobs if title_matches(j["title"], s_kws)]
    # Only keep jobs whose titles actually signal a student position.
    # Jobindex returns full-time jobs in student query results; without this
    # guard they get mis-tagged as 'student' and block the full-time pass.
    student_jobs = [
        j for j in student_jobs
        if any(ind in j["title"].lower() for ind in STUDENT_TITLE_INDICATORS + ["studentermedarbejder", "student "])
    ]
    kept_s = student_jobs[:MAX_PER_TYPE]
    student_result.extend(kept_s)
    # Add kept student URLs to cross_seen so they don't repeat under a different category
    for j in kept_s:
        cross_seen.add(j["url"])
    print(f"  [{'student':10}]  raw={raw_s:2}  after_filter={len(student_jobs):2}  kept={len(kept_s):2}")

    # ── 2. Full-time and part-time (cross-category dedup, arbejdstid[] filter) ─
    for type_label, type_param in JOB_TYPES_PARAM.items():
        type_jobs: list[dict] = []
        for q in queries:
            for item in fetch_rss(q, type_param):
                job = parse_item(item)
                if not job or job["url"] in cross_seen:
                    continue
                if is_graduate_title(job["title"]):
                    continue
                # Cross-portal dedup: a Jobbank job from an earlier category
                # may already match this Jobindex job.
                if cross_fingerprints.is_duplicate(job["title"], job["company"]):
                    cross_seen.add(job["url"])
                    continue
                cross_seen.add(job["url"])
                job["job_type"] = type_label
                type_jobs.append(job)

        raw = len(type_jobs)
        if kws:
            type_jobs = [j for j in type_jobs if title_matches(j["title"], kws)]
        # Drop any job whose title marks it as a student position — Jobindex
        # often ignores the arbejdstid[] filter and returns student posts in
        # full-time/part-time result sets.
        type_jobs = [
            j for j in type_jobs
            if not any(ind in j["title"].lower() for ind in STUDENT_TITLE_INDICATORS)
        ]
        kept = type_jobs[:MAX_PER_TYPE]
        ft_result.extend(kept)
        print(f"  [{type_label:10}]  raw={raw:2}  after_filter={len(type_jobs):2}  kept={len(kept):2}")

    # Register fingerprints for all Jobindex results BEFORE the Jobbank fetch
    # so that cross-portal duplicates are detected.
    for j in ft_result + student_result:
        cross_fingerprints.add(j["title"], j["company"])

    # ── 3. Jobbank.dk (cross-portal dedup via fingerprint) ───────────────────
    jobbank_queries = JOBBANK_QUERIES.get(label, [])
    jobbank_jobs: list[dict] = []
    print(f"  [jobbank.dk ]")
    for q in jobbank_queries:
        for item in fetch_jobbank_rss(q):
            job = parse_jobbank_item(item)
            if not job or job["url"] in cross_seen:
                continue
            if is_graduate_title(job["title"]):
                continue
            if cross_fingerprints.is_duplicate(job["title"], job["company"]):
                continue
            cross_seen.add(job["url"])
            cross_fingerprints.add(job["title"], job["company"])
            jobbank_jobs.append(job)

    raw_jb = len(jobbank_jobs)
    if kws:
        jobbank_jobs = [j for j in jobbank_jobs if title_matches(j["title"], kws)]
    # Drop student-titled jobs from the general pass (they come from section 1)
    jobbank_jobs = [
        j for j in jobbank_jobs
        if not any(ind in j["title"].lower() for ind in STUDENT_TITLE_INDICATORS)
        or j["job_type"] == "student"
    ]
    kept_jb = jobbank_jobs[:MAX_PER_TYPE]
    # Register fingerprints for kept Jobbank jobs
    for j in kept_jb:
        cross_fingerprints.add(j["title"], j["company"])
    print(f"  [{'jobbank':10}]  raw={raw_jb:2}  after_filter={len(jobbank_jobs):2}  kept={len(kept_jb):2}")

    # Jobindex first (preferred source), then Jobbank, then student
    result = ft_result + kept_jb + student_result

    print(f"  => {len(result)} total jobs for '{label}'")
    return result


def fetch_graduate_programs(
    cross_seen: set[str],
    cross_fingerprints: _CrossPortalDedup,
) -> list[dict]:
    """Fetch BI-related graduate programmes from both portals.

    Graduate programmes are standalone: no student/full-time/part-time
    sub-passes.  Title must contain a graduate keyword AND at least one
    BI-relevance keyword.
    """
    label = "graduate program"
    print(f"\n[{label}]")

    BI_RELEVANCE = [
        "data analyst", "data engineer", "data science", "data analytics",
        "data platform", "dataplatform",
        "bi ", " bi", "business intelligence", "analytics",
        "power bi", "analyst", "analytiker", "intelligence",
        "machine learning",
    ]

    # Exclude titles that mention 'data' only in non-BI contexts.
    GRADUATE_EXCLUDE = [
        "employee master data", "master data management",
        "hr data", "payroll", "supply chain",
    ]

    def _is_bi_graduate(title: str) -> bool:
        t = title.lower()
        has_grad = is_graduate_title(title)
        has_bi   = any(kw in t for kw in BI_RELEVANCE)
        excluded = any(kw in t for kw in GRADUATE_EXCLUDE)
        return has_grad and has_bi and not excluded

    # ── Jobindex ─────────────────────────────────────────────────────────
    ji_jobs: list[dict] = []
    for q in GRADUATE_QUERIES:
        for item in fetch_rss(q, None):              # no arbejdstid filter
            job = parse_item(item)
            if not job or job["url"] in cross_seen:
                continue
            if cross_fingerprints.is_duplicate(job["title"], job["company"]):
                cross_seen.add(job["url"])
                continue
            cross_seen.add(job["url"])
            job["job_type"] = "graduate"
            ji_jobs.append(job)

    raw_ji = len(ji_jobs)
    ji_jobs = [j for j in ji_jobs if _is_bi_graduate(j["title"])]
    ji_jobs = ji_jobs[:MAX_PER_TYPE]
    for j in ji_jobs:
        cross_fingerprints.add(j["title"], j["company"])
    print(f"  [{'jobindex':10}]  raw={raw_ji:2}  after_filter={len(ji_jobs):2}")

    # ── Jobbank.dk ───────────────────────────────────────────────────────
    jb_queries = JOBBANK_QUERIES.get(label, [])
    jb_jobs: list[dict] = []
    print(f"  [jobbank.dk ]")
    for q in jb_queries:
        for item in fetch_jobbank_rss(q):
            job = parse_jobbank_item(item)
            if not job or job["url"] in cross_seen:
                continue
            if cross_fingerprints.is_duplicate(job["title"], job["company"]):
                continue
            cross_seen.add(job["url"])
            cross_fingerprints.add(job["title"], job["company"])
            job["job_type"] = "graduate"
            jb_jobs.append(job)

    raw_jb = len(jb_jobs)
    jb_jobs = [j for j in jb_jobs if _is_bi_graduate(j["title"])]
    jb_jobs = jb_jobs[:MAX_PER_TYPE]
    print(f"  [{'jobbank':10}]  raw={raw_jb:2}  after_filter={len(jb_jobs):2}")

    result = ji_jobs + jb_jobs
    print(f"  => {len(result)} total jobs for '{label}'")
    return result


def count_source_jobs(data: dict, source: str) -> int:
    total = 0
    for jobs in (data.get("categories") or {}).values():
        total += sum(1 for job in jobs if job.get("source") == source)
    return total


def merge_source_from_previous(current: dict, previous: dict, source: str) -> bool:
    """Restore source-specific jobs from previous data if the current run lost them."""
    prev_categories = previous.get("categories") or {}
    curr_categories = current.get("categories") or {}

    previous_count = count_source_jobs(previous, source)
    current_count = count_source_jobs(current, source)
    if previous_count == 0 or current_count > 0:
        return False

    restored = 0
    for label, jobs in prev_categories.items():
        target = curr_categories.setdefault(label, [])
        seen_urls = {job.get("url") for job in target}
        for job in jobs:
            if job.get("source") != source:
                continue
            url = job.get("url")
            if url and url in seen_urls:
                continue
            target.append(job)
            if url:
                seen_urls.add(url)
            restored += 1

    if restored:
        print(
            f"[WARN] Current run returned 0 {source} jobs; restored "
            f"{restored} {source} jobs from previous assets/data/jobs.json."
        )
    return restored > 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Fetching Denmark Data & BI Jobs from Jobindex + Jobbank.dk ===")
    out_path = "assets/data/jobs.json"

    previous_output: dict = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as fh:
                previous_output = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[WARN] Could not read previous jobs data for fallback: {exc}")

    output: dict = {
        "updated":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": ["https://www.jobindex.dk/", "https://jobbank.dk/"],
        "categories": {},
    }

    # Shared set across ALL categories: each job URL is stored exactly once.
    cross_seen: set[str] = set()
    # Cross-portal dedup: fingerprint + fuzzy token-overlap matching.
    cross_fingerprints = _CrossPortalDedup()

    for label, queries in CATEGORIES.items():
        print(f"\n[{label}]")
        output["categories"][label] = fetch_category(
            label, queries, cross_seen, cross_fingerprints,
        )

    # Graduate programmes — separate pass with its own logic.
    output["categories"]["graduate program"] = fetch_graduate_programs(
        cross_seen, cross_fingerprints,
    )

    merge_source_from_previous(output, previous_output, "jobbank")

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in output["categories"].values())
    print(f"\nDone: {total} jobs saved to {out_path}  (updated: {output['updated']})")


if __name__ == "__main__":
    main()
