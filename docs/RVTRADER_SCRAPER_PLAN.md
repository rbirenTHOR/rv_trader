# RVTrader.com Scraper Implementation Plan

## Executive Summary

RVTrader.com is highly scraper-friendly due to its Nuxt.js SSR architecture with embedded JSON-LD schema data. The recommended approach is **JSON-LD extraction via HTTP requests** without browser automation.

---

## Recommended Architecture

### Approach: HTTP Requests + JSON-LD Parsing

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  URL Generator  │────▶│  HTTP Fetcher    │────▶│  JSON-LD Parser │
│  (Pagination)   │     │  (requests/aiohttp)│    │  (regex + json) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────┐
                                                 │  Data Storage   │
                                                 │  (CSV/JSON/DB)  │
                                                 └─────────────────┘
```

### Why NOT Browser Automation?

1. **JSON-LD data is pre-rendered** - No JavaScript needed
2. **Faster execution** - No browser overhead
3. **Lower resource usage** - No Chromium/Firefox instances
4. **More stable** - No DOM changes or JS errors

### When Browser Automation IS Required

Browser automation (Playwright/Selenium) is needed for:
- **`window.trk` tracking object** - Contains dealerid, listingtier, length, type, etc.
- **Engagement stats (saves/hearts, days listed)** - Rendered in DOM, no API exists
- **Spec details** - GVWR, sleeping capacity, slide-outs, etc.

**Note:** There is NO separate API endpoint for saves/views/hearts. This data is server-rendered directly into the HTML page.

---

## Implementation Phases

### Phase 1: Core Scraper (List Pages)

**Goal:** Extract all listings from search results

**Steps:**
1. Fetch search page HTML via HTTP GET
2. Parse JSON-LD from `<script type="application/ld+json">`
3. Extract offer array from parsed JSON
4. Handle pagination (36 items per page)

**Python Implementation:**

```python
import re
import json
import time
import requests
from typing import List, Dict, Optional

class RVTraderScraper:
    BASE_URL = "https://www.rvtrader.com/rvs-for-sale"
    RESULTS_PER_PAGE = 36

    def __init__(self, delay: float = 1.5):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.delay = delay

    def extract_jsonld(self, html: str) -> Optional[Dict]:
        """Extract JSON-LD data from HTML."""
        pattern = r'<script type="application/ld\+json">(.*?)</script>'
        matches = re.findall(pattern, html, re.DOTALL)
        if matches:
            return json.loads(matches[0])
        return None

    def fetch_page(self, page: int = 1, zip_code: str = None, **filters) -> List[Dict]:
        """Fetch a single page of listings."""
        params = {'page': page}
        if zip_code:
            params['zip'] = zip_code
        params.update(filters)

        response = self.session.get(self.BASE_URL, params=params)
        response.raise_for_status()

        jsonld = self.extract_jsonld(response.text)
        if not jsonld:
            return []

        offers = jsonld.get('offers', {}).get('offers', [])

        listings = []
        for offer in offers:
            item = offer.get('itemOffered', {})
            listings.append({
                'url': offer.get('url'),
                'name': item.get('name'),
                'condition': item.get('itemCondition'),
                'price': item.get('price'),
                'currency': item.get('priceCurrency', 'USD')
            })

        time.sleep(self.delay)
        return listings

    def scrape_all(self, max_pages: int = 100, **filters) -> List[Dict]:
        """Scrape multiple pages of listings."""
        all_listings = []

        for page in range(1, max_pages + 1):
            print(f"Fetching page {page}...")
            listings = self.fetch_page(page=page, **filters)

            if not listings:
                print(f"No listings found on page {page}, stopping.")
                break

            all_listings.extend(listings)
            print(f"  Found {len(listings)} listings (total: {len(all_listings)})")

        return all_listings

# Usage
scraper = RVTraderScraper(delay=2.0)
listings = scraper.scrape_all(max_pages=10, zip_code='60616')
```

### Phase 2: Detail Page Enrichment

**Goal:** Get full details for each listing

**Additional Data from Detail Pages:**
- Full description (HTML)
- Image URLs
- Manufacturer/Brand
- Model
- SKU/Listing ID

```python
def fetch_detail(self, url: str) -> Optional[Dict]:
    """Fetch full details for a single listing."""
    response = self.session.get(url)
    response.raise_for_status()

    jsonld = self.extract_jsonld(response.text)
    if not jsonld:
        return None

    return {
        'sku': jsonld.get('sku'),
        'name': jsonld.get('name'),
        'url': jsonld.get('url'),
        'image': jsonld.get('image'),
        'brand': jsonld.get('brand', {}).get('name'),
        'manufacturer': jsonld.get('manufacturer'),
        'model': jsonld.get('model'),
        'description': jsonld.get('description'),
        'price': jsonld.get('offers', {}).get('price'),
        'condition': jsonld.get('offers', {}).get('itemCondition'),
        'availability': jsonld.get('offers', {}).get('availability')
    }
```

### Phase 3: Tracking Object & Engagement Stats (Requires Browser)

**Goal:** Extract comprehensive metadata from `window.trk` and engagement stats (saves, days listed)

**Important:** There is NO separate API for saves/views - this data is rendered server-side and must be extracted from the DOM.

**Data Available:**
- `window.trk` object: dealerid, custid, listingtier, length, type, dma, and 25+ other fields
- DOM stats: days listed, saves/hearts count

```python
from playwright.sync_api import sync_playwright
from typing import Dict, Optional

def fetch_tracking_data(url: str) -> Dict:
    """Extract window.trk tracking object and DOM stats."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_load_state('networkidle')

        # Extract window.trk tracking object
        trk = page.evaluate('() => window.trk || {}')

        # Extract engagement stats from DOM text
        stats = page.evaluate('''() => {
            const text = document.body.innerText;
            const daysMatch = text.match(/(\\d+)\\s*days?\\s*listed/i);
            const savesMatch = text.match(/(\\d+)\\s*saves?/i);
            return {
                daysListed: daysMatch ? daysMatch[1] : null,
                saves: savesMatch ? savesMatch[1] : null
            };
        }''')

        browser.close()

        return {
            'tracking': trk,
            'engagement': stats
        }

# Example extracted tracking data:
# {
#     'tracking': {
#         'adid': '5037070155',
#         'custid': '11287114',
#         'dealerid': '3054198',
#         'make': 'forest river rv',
#         'model': 'cherokee timberwolf 39al',
#         'type': 'destination trailer',
#         'length': '45 ft',
#         'condition': 'new',
#         'prodprice': '51495',
#         'year': '2026',
#         'listingtier': 'premium_select',
#         'dma': '602-chicago',
#         ...
#     },
#     'engagement': {
#         'daysListed': '190',
#         'saves': '0'
#     }
# }
```

### Phase 4: Additional HTML Data (Optional)

For specs and dealer info not in tracking object:

```python
from playwright.sync_api import sync_playwright

def fetch_html_details(url: str) -> Dict:
    """Extract additional data from HTML DOM."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_load_state('networkidle')

        details = {}

        # Extract specs
        specs = page.query_selector_all('[class*="spec"]')
        for spec in specs:
            label = spec.query_selector('[class*="label"]')
            value = spec.query_selector('[class*="value"]')
            if label and value:
                details[label.inner_text()] = value.inner_text()

        # Extract dealer info
        dealer = page.query_selector('[class*="dealer"]')
        if dealer:
            details['dealer'] = dealer.inner_text()

        browser.close()
        return details
```

---

## Data Storage Options

### Option 1: CSV (Simple)
```python
import csv

def save_to_csv(listings: List[Dict], filename: str):
    if not listings:
        return

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=listings[0].keys())
        writer.writeheader()
        writer.writerows(listings)
```

### Option 2: JSON Lines (Flexible)
```python
import json

def save_to_jsonl(listings: List[Dict], filename: str):
    with open(filename, 'w', encoding='utf-8') as f:
        for listing in listings:
            f.write(json.dumps(listing) + '\n')
```

### Option 3: SQLite (Queryable)
```python
import sqlite3

def save_to_sqlite(listings: List[Dict], db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS listings (
            sku TEXT PRIMARY KEY,
            name TEXT,
            url TEXT,
            condition TEXT,
            price REAL,
            brand TEXT,
            model TEXT,
            description TEXT,
            image TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    for listing in listings:
        cursor.execute('''
            INSERT OR REPLACE INTO listings
            (sku, name, url, condition, price, brand, model, description, image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            listing.get('sku'),
            listing.get('name'),
            listing.get('url'),
            listing.get('condition'),
            listing.get('price'),
            listing.get('brand'),
            listing.get('model'),
            listing.get('description'),
            listing.get('image')
        ))

    conn.commit()
    conn.close()
```

---

## Filter Examples

### By Location
```python
listings = scraper.scrape_all(zip_code='60616', max_pages=50)
```

### By RV Type
```python
# Class A motorhomes
listings = scraper.scrape_all(type='Class%20A%7C198067')
```

### By Condition
```python
# Used only
listings = scraper.scrape_all(condition='U')

# New only
listings = scraper.scrape_all(condition='N')
```

### By Make
```python
# Forest River
listings = scraper.scrape_all(make='Forest%20River%7C440465')
```

### Combined Filters
```python
listings = scraper.scrape_all(
    zip_code='60616',
    type='Class%20A%7C198067',
    condition='U',
    max_pages=20
)
```

---

## Rate Limiting & Politeness

```python
import time
import random

class PoliteRVTraderScraper(RVTraderScraper):
    def __init__(self, min_delay: float = 1.0, max_delay: float = 3.0):
        super().__init__()
        self.min_delay = min_delay
        self.max_delay = max_delay

    def random_delay(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)

    def fetch_page(self, *args, **kwargs):
        result = super().fetch_page(*args, **kwargs)
        self.random_delay()
        return result
```

---

## Error Handling

```python
import logging
from requests.exceptions import RequestException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RobustRVTraderScraper(RVTraderScraper):
    def fetch_page(self, page: int = 1, retries: int = 3, **filters):
        for attempt in range(retries):
            try:
                return super().fetch_page(page, **filters)
            except RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(5 * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"All {retries} attempts failed for page {page}")
                    return []
```

---

## Estimated Scrape Times

| Scope | Pages | Listings | Time (1.5s delay) |
|-------|-------|----------|-------------------|
| 10 pages | 10 | ~360 | ~15 seconds |
| 100 pages | 100 | ~3,600 | ~2.5 minutes |
| 1,000 pages | 1,000 | ~36,000 | ~25 minutes |
| All (~6,266) | 6,266 | ~225,571 | ~2.6 hours |

**With detail pages:** Multiply by 2x-3x depending on how many details you need.

---

## Quick Start Command

```bash
# Install dependencies
pip install requests

# Run basic scrape (first 10 pages)
python -c "
from rvtrader_scraper import RVTraderScraper
scraper = RVTraderScraper()
listings = scraper.scrape_all(max_pages=10, zip_code='60616')
print(f'Scraped {len(listings)} listings')
"
```

---

## API Endpoints

### Available APIs

| Endpoint | Purpose | Method |
|----------|---------|--------|
| `/rvs-for-sale` | Search/listing pages | GET (with query params) |
| `/listing/{slug}` | Detail pages | GET |
| `/search-results-data/similar-listings-contact` | Related listings | GET |

### What Does NOT Exist (Must Use DOM Extraction)

| Data | Extraction Method |
|------|-------------------|
| Saves/Hearts count | Parse DOM text: `(\d+)\s*saves?` |
| Days listed | Parse DOM text: `(\d+)\s*days?\s*listed` |
| Listing tier | Extract from `window.trk.listingtier` |
| Dealer ID | Extract from `window.trk.dealerid` |
| RV length | Extract from `window.trk.length` |

---

## Files Created

| File | Description |
|------|-------------|
| `RVTRADER_DOCUMENTATION.md` | URL patterns, parameters, infrastructure |
| `RVTRADER_DATA_SCHEMA.json` | Complete JSON schemas for all data |
| `RVTRADER_SCRAPER_PLAN.md` | This implementation guide |
