# Rasel Mia Portfolio

Static personal portfolio site for `raselmia.live`, built with HTML/CSS/JavaScript and deployed on GitHub Pages.

Live site: https://raselmia.live

## What is in this repo

- Portfolio landing page with projects, skills, and contact (`/home/`)
- Data Story hub and six case-study pages (`/datastory/`)
- BI jobs board for Denmark powered by auto-refreshed JSON data (`/bi-jobs/`)
- Portfolio analytics dashboard (GA4 + Looker Studio embed) (`/analytics/`)
- AI cover-letter generator tool (`/cover-letter/`)
- Resume page and redirect helpers (`/resume/`, `resume.html`, `blog.html`)

## Main routes

- `/` redirects to `/home/`
- `/home/`
- `/datastory/`
- `/datastory/churn-prediction/`
- `/datastory/parking-prediction/`
- `/datastory/mobile-pricing/`
- `/datastory/stock-prediction/`
- `/datastory/chart-guide/`
- `/datastory/jordan-brand-analysis/`
- `/bi-jobs/`
- `/analytics/`
- `/cover-letter/`
- `/resume/`
- `/blog.html` redirects to `/datastory/`
- `/resume.html` redirects to `/resume/`

## Key features

- Responsive UI with light/dark theme support
- English/Danish content toggle on core portfolio pages
- Unified discovery search (`assets/data/discovery-index.json`) for projects and stories
- Dynamic BI jobs feed with filters (category, city, job type, language)
- Formspree contact forms and Tawk.to chat
- GA4 event tracking and public Looker Studio analytics page
- AI cover-letter generator with PDF resume upload, rewrite options, and PDF/DOCX export

## Data and automation

- `assets/data/discovery-index.json`: search index for project and story cards
- `assets/data/jobs.json`: BI job dataset used by `/home/` and `/bi-jobs/`
- `scripts/fetch_jobs.py`: pulls Jobindex RSS results, filters/deduplicates, writes `jobs.json`
- `.github/workflows/fetch-jobs.yml`: runs daily at `06:00 UTC` and on manual dispatch

Manual job refresh:

```sh
python -m pip install requests
python scripts/fetch_jobs.py
```

## Tech stack and services

- HTML5, CSS3, JavaScript (no build step required)
- GitHub Pages + Jekyll config (`_config.yml`) + custom domain (`CNAME`)
- Font Awesome and Google Fonts
- Google Analytics 4 and Looker Studio
- Formspree, Tawk.to, CountAPI
- Cover-letter API endpoint hosted externally (Cloudflare Worker URL configured in `cover-letter/index.html`)

## Local development

Run a static server from the repo root:

```sh
python -m http.server 8000
```

Then open `http://localhost:8000/home/`.

## Repository layout

- `home/`: main portfolio page
- `datastory/`: story index and individual case-study pages
- `bi-jobs/`: BI jobs board UI
- `analytics/`: GA4/Looker dashboard page
- `cover-letter/`: AI cover-letter web app
- `resume/`: resume page
- `assets/css`, `assets/js`, `assets/data`: styles, shared scripts, data files
- `scripts/`: maintenance scripts (job data fetcher)
- `.github/workflows/`: scheduled automation
