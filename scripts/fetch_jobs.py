"""
fetch_jobs.py
Fetches full-time Data & BI job listings from Jobindex.dk (RSS feed)
and writes them to assets/data/jobs.json.
Run locally: python scripts/fetch_jobs.py
Run via GitHub Actions: automatically on schedule.
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

CATEGORIES = {
    "data analyst": "data+analyst",
    "business analyst": "business+analyst",
    "business intelligence": "business+intelligence",
    "bi specialist": "BI+specialist",
}

MAX_PER_CATEGORY = 15

# Jobindex XML RSS — working endpoint (jobsoegning.xml, not /rss)
# arbedjstid[] filter included for full-time jobs
RSS_URL = (
    "https://www.jobindex.dk/jobsoegning.xml"
    "?q={query}&maxcount={max}&arbejdstid%5B%5D=Fuldtid"
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


def strip_html(text: str) -> str:
    return _HTML_TAG.sub("", text or "").strip()


def parse_date(date_str: str) -> str:
    """Return ISO-8601 date string (YYYY-MM-DD) from an RFC-2822 date."""
    if not date_str:
        return ""
    try:
        return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
    except Exception:
        # Fallback: grab first 10 chars if it looks like a date already
        clean = (date_str or "").strip()
        return clean[:10] if len(clean) >= 10 else clean


def split_title_company(raw_title: str) -> tuple[str, str]:
    """
    Jobindex RSS titles are in the format:
      'Job Title (Location), Company Name'
    or sometimes:
      'Job Title, Company Name'
    Split by the LAST comma to separate job title from company.
    """
    raw_title = strip_html(raw_title)
    if "," in raw_title:
        idx = raw_title.rfind(",")
        return raw_title[:idx].strip(), raw_title[idx + 1:].strip()
    # Fallback: try ' - ' separator
    if " - " in raw_title:
        parts = raw_title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return raw_title, ""


_PAREN = re.compile(r"\(([^)]+)\)")


def extract_location_from_title(title: str) -> str:
    """
    Jobindex often embeds the location in parentheses in the job title:
      'Data Analyst (Copenhagen)' -> 'Copenhagen'
      'BI Developer (Remote/Danmark)' -> 'Remote/Danmark'
    Returns the last parenthetical match, or empty string.
    """
    matches = _PAREN.findall(title)
    return matches[-1].strip() if matches else ""


def extract_location(description: str) -> str:
    """
    Try to pull a city/region from the description text.
    Falls back to 'Denmark'.
    """
    text = strip_html(description)
    # Look for common Danish city keywords in the description
    danish_cities = [
        "København", "Copenhagen", "Aarhus", "Odense", "Aalborg",
        "Esbjerg", "Randers", "Kolding", "Horsens", "Vejle",
        "Fredericia", "Helsingør", "Roskilde", "Herning", "Silkeborg",
        "Næstved", "Frederiksberg", "Viborg", "Køge", "Holstebro",
    ]
    for city in danish_cities:
        if city.lower() in text.lower():
            return city
    return "Denmark"


# ---------------------------------------------------------------------------
# Fetch & parse
# ---------------------------------------------------------------------------

def fetch_category(label: str, query: str) -> list[dict]:
    url = RSS_URL.format(query=query, max=MAX_PER_CATEGORY)
    print(f"  Fetching: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  ✗ Request failed for '{label}': {exc}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as exc:
        print(f"  ✗ XML parse error for '{label}': {exc}")
        return []

    jobs = []
    for item in root.findall(".//item"):
        get = lambda tag: (item.findtext(tag) or "").strip()

        raw_title = get("title")
        link      = get("link")
        desc      = get("description")
        pub_date  = get("pubDate")

        if not link:
            continue

        title, company = split_title_company(raw_title)

        # Try to get location from parentheses in the raw title first,
        # then fall back to scanning the description text.
        location = extract_location_from_title(raw_title)
        if not location:
            location = extract_location(desc) or "Denmark"
        posted   = parse_date(pub_date)
        snippet  = strip_html(desc)[:160].strip()

        jobs.append(
            {
                "title":    title,
                "company":  company,
                "location": location,
                "url":      link,
                "posted":   posted,
                "snippet":  snippet,
                "source":   "jobindex",
            }
        )

    print(f"  ✓ {len(jobs)} jobs for '{label}'")
    return jobs[:MAX_PER_CATEGORY]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Fetching Denmark Data & BI Jobs from Jobindex ===")

    result: dict = {
        "updated":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_url": "https://www.jobindex.dk/",
        "categories": {},
    }

    for label, query in CATEGORIES.items():
        result["categories"][label] = fetch_category(label, query)

    out_path = "assets/data/jobs.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in result["categories"].values())
    print(f"\n✓ Saved {total} jobs to {out_path}  (updated: {result['updated']})")


if __name__ == "__main__":
    main()
