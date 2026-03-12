"""
send_digest.py
Sends a weekly BI & Data Jobs digest email to all subscribers via Resend API.

Reads:
  - assets/data/jobs.json     → current job listings
  - assets/data/subscribers.json → subscriber email list

Requires:
  - RESEND_API_KEY environment variable
  - RESEND_FROM environment variable (default: onboarding@resend.dev)

Run locally:
  RESEND_API_KEY=re_xxx python scripts/send_digest.py

Run via CI:
  GitHub Actions (.github/workflows/send-digest.yml)
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_AUDIENCE_ID = os.environ.get("RESEND_AUDIENCE_ID", "")
RESEND_FROM = os.environ.get("RESEND_FROM", "BI Jobs <onboarding@resend.dev>")
RESEND_ENDPOINT = "https://api.resend.com/emails"

JOBS_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "data", "jobs.json")
SUBS_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "data", "subscribers.json")

SITE_URL = "https://raselmia.live/bi-jobs/"
DAYS_LOOKBACK = 7  # include jobs posted within the last N days

CATEGORY_LABELS = {
    "data analyst": "📊 Data Analyst",
    "business analyst": "💼 Business Analyst",
    "business intelligence": "🧠 Business Intelligence",
    "bi specialist": "⚙️ BI Specialist",
    "data scientist": "🔬 Data Scientist",
    "graduate program": "🎓 Graduate Program",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_subscribers() -> list[str]:
    """Fetch subscriber emails from Resend Audiences API or fallback to local file."""
    if RESEND_AUDIENCE_ID:
        print(f"Fetching contacts from Resend audience {RESEND_AUDIENCE_ID}...")
        try:
            resp = requests.get(
                f"https://api.resend.com/audiences/{RESEND_AUDIENCE_ID}/contacts",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                contacts = data.get("data", [])
                emails = [
                    c["email"] for c in contacts
                    if not c.get("unsubscribed", False) and c.get("email")
                ]
                print(f"  Found {len(emails)} active subscriber(s) in Resend audience.")
                return emails
            else:
                print(f"  WARNING: Resend API returned {resp.status_code}: {resp.text[:200]}")
                print("  Falling back to local subscribers.json...")
        except Exception as exc:
            print(f"  WARNING: Failed to fetch from Resend: {exc}")
            print("  Falling back to local subscribers.json...")

    # Fallback to local file
    subs_path = os.path.normpath(SUBS_PATH)
    if os.path.exists(subs_path):
        subs_data = load_json(subs_path)
        return subs_data.get("subscribers", [])
    return []


def is_recent(posted: str, cutoff: datetime) -> bool:
    """Return True if the posted date is on or after the cutoff."""
    if not posted:
        return False
    try:
        dt = datetime.strptime(posted, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt >= cutoff
    except ValueError:
        return False


def esc(text: str) -> str:
    """HTML-escape a string."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Email HTML template
# ---------------------------------------------------------------------------

def build_email_html(new_jobs_by_cat: dict, total_new: int, week_label: str) -> str:
    """Build a styled HTML email for the weekly digest."""

    # Job cards grouped by category
    sections = ""
    for cat_key, jobs in new_jobs_by_cat.items():
        if not jobs:
            continue
        label = CATEGORY_LABELS.get(cat_key, cat_key.title())
        cards = ""
        for job in jobs[:8]:  # max 8 per category to keep email concise
            title = esc(job.get("title", "Position"))
            company = esc(job.get("company", ""))
            location = esc(job.get("location", "Denmark"))
            url = esc(job.get("url", "#"))
            posted = job.get("posted", "")
            source = job.get("source", "jobindex").capitalize()

            cards += f"""
            <tr>
              <td style="padding:12px 16px;border-bottom:1px solid #f1f5f9;">
                <a href="{url}" style="color:#1e293b;text-decoration:none;font-weight:700;font-size:15px;line-height:1.4;">{title}</a>
                <div style="margin-top:4px;font-size:13px;color:#64748b;">
                  {f'<span>{company}</span> · ' if company else ''}<span>{location}</span> · <span style="font-size:12px;opacity:0.7;">{source}</span>
                </div>
              </td>
              <td style="padding:12px 16px;border-bottom:1px solid #f1f5f9;text-align:right;vertical-align:middle;">
                <a href="{url}" style="display:inline-block;padding:6px 14px;border-radius:20px;background:#6366f1;color:#fff;text-decoration:none;font-size:12px;font-weight:700;">Apply →</a>
              </td>
            </tr>"""

        remaining = len(jobs) - 8
        more_note = ""
        if remaining > 0:
            more_note = f'<tr><td colspan="2" style="padding:10px 16px;font-size:13px;color:#6366f1;font-weight:600;">+ {remaining} more on the site →</td></tr>'

        sections += f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
          <tr>
            <td colspan="2" style="padding:10px 16px;background:#f8fafc;border-radius:8px 8px 0 0;font-weight:700;font-size:14px;color:#334155;border-bottom:2px solid #e2e8f0;">
              {label} <span style="font-weight:400;color:#94a3b8;">({len(jobs)} new)</span>
            </td>
          </tr>
          {cards}
          {more_note}
        </table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background:#f1f5f9;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06);">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);padding:32px 24px;text-align:center;">
              <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">🔍 BI & Data Jobs — Weekly Digest</h1>
              <p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">{week_label}</p>
            </td>
          </tr>

          <!-- Stats -->
          <tr>
            <td style="padding:24px 24px 8px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;text-align:center;">
                    <span style="font-size:28px;font-weight:700;color:#1e293b;">{total_new}</span>
                    <br>
                    <span style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;font-weight:600;">New Jobs This Week</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Job listings -->
          <tr>
            <td style="padding:16px 24px 24px;">
              {sections}
            </td>
          </tr>

          <!-- CTA -->
          <tr>
            <td style="padding:0 24px 32px;text-align:center;">
              <a href="{SITE_URL}" style="display:inline-block;padding:12px 32px;border-radius:999px;background:#6366f1;color:#fff;text-decoration:none;font-weight:700;font-size:14px;">
                View All Jobs on raselmia.live →
              </a>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 24px;background:#f8fafc;border-top:1px solid #e2e8f0;text-align:center;font-size:12px;color:#94a3b8;line-height:1.6;">
              You're receiving this because you subscribed to<br>BI & Data job alerts on <a href="{SITE_URL}" style="color:#6366f1;">raselmia.live</a>.<br>
              To unsubscribe, reply to this email with "unsubscribe".
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Send emails via Resend
# ---------------------------------------------------------------------------

def send_email(to: str, subject: str, html: str) -> bool:
    """Send one email via Resend API. Returns True on success."""
    resp = requests.post(
        RESEND_ENDPOINT,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": RESEND_FROM,
            "to": [to],
            "subject": subject,
            "html": html,
        },
        timeout=30,
    )
    if resp.status_code in (200, 201):
        print(f"  ✓ Sent to {to}")
        return True
    else:
        print(f"  ✗ Failed for {to}: {resp.status_code} {resp.text[:200]}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not RESEND_API_KEY:
        print("ERROR: RESEND_API_KEY environment variable is not set.")
        sys.exit(1)

    # Load jobs data
    jobs_path = os.path.normpath(JOBS_PATH)
    if not os.path.exists(jobs_path):
        print(f"ERROR: Jobs data not found at {jobs_path}")
        sys.exit(1)

    jobs_data = load_json(jobs_path)

    # Fetch subscribers from Resend Audiences API (or fallback)
    subscribers = fetch_subscribers()

    if not subscribers:
        print("No subscribers found. Skipping digest.")
        return

    # Filter jobs posted in the last N days
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DAYS_LOOKBACK)
    categories = jobs_data.get("categories", {})

    new_jobs_by_cat = {}
    total_new = 0
    seen_urls = set()

    for cat_key in ["data analyst", "business analyst", "business intelligence",
                    "bi specialist", "data scientist", "graduate program"]:
        cat_jobs = categories.get(cat_key, [])
        recent = []
        for job in cat_jobs:
            url = job.get("url", "")
            if url in seen_urls:
                continue
            if is_recent(job.get("posted", ""), cutoff):
                recent.append(job)
                seen_urls.add(url)
        if recent:
            # Sort newest first
            recent.sort(key=lambda j: j.get("posted", ""), reverse=True)
            new_jobs_by_cat[cat_key] = recent
            total_new += len(recent)

    if total_new == 0:
        print("No new jobs posted in the last 7 days. Skipping digest.")
        return

    # Build email
    week_label = f"Week of {now.strftime('%d %b %Y')}"
    subject = f"🔍 {total_new} New BI & Data Jobs in Denmark — {week_label}"
    html = build_email_html(new_jobs_by_cat, total_new, week_label)

    print(f"\n📧 Sending weekly digest: {total_new} new jobs to {len(subscribers)} subscriber(s)\n")

    success = 0
    for email in subscribers:
        email = email.strip()
        if email and "@" in email:
            if send_email(email, subject, html):
                success += 1

    print(f"\n✅ Done: {success}/{len(subscribers)} emails sent successfully.")


if __name__ == "__main__":
    main()
