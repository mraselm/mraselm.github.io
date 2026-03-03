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

MAX_PER_CATEGORY = 15    # jobs to KEEP per category after filter & dedup
FETCH_PER_QUERY  = 30    # jobs to FETCH from Jobindex per individual query

# Each category maps to a list of quoted-phrase queries.
# %22…%22 = URL-encoded double-quotes, forces Jobindex phrase search.
CATEGORIES: dict[str, list[str]] = {
    "data analyst": [
        "%22data+analyst%22",
        "dataanalytiker",
    ],
    "business analyst": [
        "%22business+analyst%22",
        "forretningsanalytiker",
    ],
    "business intelligence": [
        "%22business+intelligence%22",
        "%22BI+analyst%22",
        "%22BI+developer%22",
        "%22BI+consultant%22",
        "%22BI+developer%22",
    ],
    "bi specialist": [
        "%22BI+specialist%22",
        "%22BI+arkitekt%22",
        "%22business+intelligence+specialist%22",
    ],
}

# Title keyword whitelist — job title must contain at least one (case-insensitive).
TITLE_KEYWORDS: dict[str, list[str]] = {
    "data analyst": [
        "data analyst",
        "dataanalytiker",
        "data analytiker",
        "analytics",
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
        "bi specialist",
        "bi lead",
        "bi arkitekt",
        "power bi",
        "data engineer",
    ],
    "bi specialist": [
        "bi specialist",
        "bi developer",
        "bi analyst",
        "bi consultant",
        "bi manager",
        "bi lead",
        "bi arkitekt",
        "business intelligence",
        "power bi",
    ],
}

# Jobindex XML RSS endpoint — jobsoegning.xml works; /rss returns 404
RSS_URL = (
    "https://www.jobindex.dk/jobsoegning.xml"
    f"?q={{query}}&maxcount={FETCH_PER_QUERY}&arbejdstid%5B%5D=Fuldtid"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PortfolioJobFetcher/1.0; "
        "+https://raselmia.live)"
    ),
    "Accept-Language": "da-DK,da;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HTML_TAG = re.compile(r"<[^>]+>")
_PAREN    = re.compile(r"\(([^)]+)\)")


def strip_html(text: str) -> str:
    return _HTML_TAG.sub("", text or "").strip()


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


def extract_location_from_title(raw_title: str) -> str:
    """
    Jobindex embeds location in parens: 'Data Analyst (Copenhagen), Acme'
    Returns the last parenthetical value, or empty string.
    """
    matches = _PAREN.findall(raw_title)
    return matches[-1].strip() if matches else ""


def extract_location(description: str) -> str:
    """Scan description for a known Danish city; fall back to 'Denmark'."""
    text = strip_html(description)
    cities = [
        "Koebenhavn", "Copenhagen", "Aarhus", "Odense", "Aalborg",
        "Esbjerg", "Randers", "Kolding", "Horsens", "Vejle",
        "Fredericia", "Roskilde", "Herning", "Silkeborg",
        "Naestved", "Frederiksberg", "Viborg", "Koege", "Holstebro",
        "Lyngby", "Hellerup", "Glostrup", "Ballerup", "Taastrup",
        "Ringsted", "Svendborg", "Hilleroed", "Hvidovre", "Soeborg",
    ]
    for city in cities:
        if city.lower() in text.lower():
            return city
    return "Denmark"


def title_matches(title: str, keywords: list[str]) -> bool:
    """Return True if title contains at least one whitelisted keyword."""
    t = title.lower()
    return any(kw in t for kw in keywords)


# ---------------------------------------------------------------------------
# Fetch & parse
# ---------------------------------------------------------------------------

def fetch_rss(query: str) -> list[ET.Element]:
    """Fetch and parse one RSS query. Returns list of <item> elements."""
    url = RSS_URL.format(query=query)
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
    location = extract_location_from_title(raw_title) or extract_location(desc) or "Denmark"
    return {
        "title":    title,
        "company":  company,
        "location": location,
        "url":      link,
        "posted":   parse_date(pub_date),
        "snippet":  strip_html(desc)[:160].strip(),
        "source":   "jobindex",
    }


def fetch_category(label: str, queries: list[str]) -> list[dict]:
    """
    Run all queries for a category, merge, deduplicate by URL,
    apply title keyword filter, return up to MAX_PER_CATEGORY jobs.
    """
    seen: set[str] = set()
    all_jobs: list[dict] = []

    for q in queries:
        for item in fetch_rss(q):
            job = parse_item(item)
            if job and job["url"] not in seen:
                seen.add(job["url"])
                all_jobs.append(job)

    print(f"  {len(all_jobs)} unique jobs fetched from {len(queries)} queries")

    # Title whitelist filter
    kws = TITLE_KEYWORDS.get(label, [])
    if kws:
        before = len(all_jobs)
        all_jobs = [j for j in all_jobs if title_matches(j["title"], kws)]
        print(f"  {before} -> {len(all_jobs)} after title filter")

    result = all_jobs[:MAX_PER_CATEGORY]
    print(f"  => {len(result)} jobs saved for '{label}'")
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

    for label, queries in CATEGORIES.items():
        print(f"\n[{label}]")
        output["categories"][label] = fetch_category(label, queries)

    out_path = "assets/data/jobs.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in output["categories"].values())
    print(f"\nDone: {total} jobs saved to {out_path}  (updated: {output['updated']})")


if __name__ == "__main__":
    main()
