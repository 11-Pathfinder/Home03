# Property Finder

## Architecture
- **CLI entry point**: `main.py` with commands: `scrape`, `digest`, `scrape+digest`, `inspect`
- **Pluggable scrapers**: `scrapers/base.py` (ABC) → `scrapers/foxtons.py` (Playwright)
- **Agent registry**: `scrapers/__init__.py` maps agent names to scraper classes
- **State**: `data/seen.json` (committed to repo, tracks all seen properties + emailed flag)
- **Email**: `emailer.py` renders Jinja2 template → Gmail SMTP (falls back to file if no password)

## Data pipeline
```
config.yaml → scraper → [Property list] → dedup (seen.json) → scorer → emailer → Gmail
```

## Key decisions
- Playwright (not requests/BS4) because Foxtons is a Next.js app — listings render via JS
- Async/await for all scrapers (Playwright async API)
- JSON files for state (no database) — simple, git-trackable
- Property ID = MD5 of `"{agent}:{url}"` (first 12 chars)
- `from __future__ import annotations` required — system Python is 3.9
- Config-driven searches — add areas/filters in `config.yaml` without code changes

## Adding a new estate agent
1. Create `scrapers/newagent.py` with class inheriting `BaseScraper`
2. Implement `scrape(search_config) -> list[Property]` and `inspect(search_config)`
3. Register in `scrapers/__init__.py`: `AGENT_REGISTRY["newagent"] = NewAgentScraper`
4. Add entries in `config.yaml` with `agent: newagent`

## Foxtons scraper details
- URL pattern: `https://www.foxtons.co.uk/properties-for-sale/{area}/?bedrooms_from=N&price_to=N&price_from=N`
- Primary selector: `a[href*="/chpk"]` (property card links)
- Parses: address (line with comma), price (£regex), beds/baths (Nbed/Nbath regex), images (assets.foxtons.co.uk)
- 2s courtesy delay between area requests
- `inspect` command dumps rendered HTML to `data/inspect_dump.html` for debugging selectors

## GitHub Actions
- **Scrape**: every 4 hours, commits `data/seen.json` back to repo
- **Digest**: daily at 7 AM UTC, sends email, marks properties as emailed
- Concurrency group `scraper` prevents overlapping runs
- Secret: `GMAIL_APP_PASSWORD`

## Config format (`config.yaml`)
```yaml
searches:
  - name: "description"
    agent: foxtons          # must match AGENT_REGISTRY key
    areas: [area1, area2]   # Foxtons URL path segments
    min_price: 500000
    max_price: 800000
    min_bedrooms: 4
    property_types: [house]
email:
  to: "you@gmail.com"
  from: "you@gmail.com"
```

## Dependencies
- `playwright` — headless Chrome for JS-rendered pages
- `pyyaml` — config parsing
- `jinja2` — email template rendering
- Everything else is stdlib (smtplib, hashlib, dataclasses, argparse, json)

## Scoring + feedback (v2, not yet implemented)
- `data/feedback.json` exists for future liked/disliked tracking
- Currently sorted by price ascending; scoring/ranking planned for later
