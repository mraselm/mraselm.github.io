"""
fetch_jobs.py
Fetches full-time Data & BI job listings from Jobindex.dk (RSS feed)
and writes them to assets/data/jobs.json.

Strategy:
  - Uses quoted phrase search (%22...%22) so Jobindex matches the exact phrase,
    not just individual words scattered across the description.
  - Each category runs multiple queries (EN + DA terms) and deduplicates by URL.
  - A title-keyword whitelist acts as a final safety filter.

Run locally:  python scripts/fetch_jobs.py
Run via CI:   GitHub Actions (.github/workflows/fetch-jobs.yml)
"""

import json
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
    t = text.lower()
    for key, canonical in _CITY_MAP.items():
        if key in t:
            return canonical
    return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HTML_TAG    = re.compile(r"<[^>]+>")
_WHITESPACE  = re.compile(r"[ \t]+")


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
    t = text.lower()
    # Danish diacritics are a very strong signal
    if any(c in t for c in 'æøå'):
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
    get = lambda tag: (item.findtext(tag) or "").strip()
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

    lang = detect_language(snippet)

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
                   cross_seen: set[str]) -> list[dict]:
    """
    Fetch jobs for a category across student, full-time, and part-time types.

    Student queries use LOCAL dedup (per-category) because each STUDENT_QUERY
    already embeds the category keyword, so cross-contamination is minimal.
    This also prevents a student URL that fails one category's title filter
    from being permanently locked out of a more relevant category.

    Full-time / part-time use cross_seen so the same general posting does not
    appear under multiple category tabs.
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
                if job and job["url"] not in cross_seen:
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

    # Full-time/part-time first, then student cards
    result = ft_result + student_result

    print(f"  => {len(result)} total jobs for '{label}'")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Fetching Denmark Data & BI Jobs from Jobindex ===")

    output: dict = {
        "updated":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_url": "https://www.jobindex.dk/",
        "categories": {},
    }

    # Shared set across ALL categories: each job URL is stored exactly once.
    cross_seen: set[str] = set()

    for label, queries in CATEGORIES.items():
        print(f"\n[{label}]")
        output["categories"][label] = fetch_category(label, queries, cross_seen)

    out_path = "assets/data/jobs.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in output["categories"].values())
    print(f"\nDone: {total} jobs saved to {out_path}  (updated: {output['updated']})")


if __name__ == "__main__":
    main()
