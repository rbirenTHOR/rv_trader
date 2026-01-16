# RVTrader.com Scraper Documentation

## Overview

RVTrader.com is a marketplace for recreational vehicles (RVs) powered by Nuxt.js SSR (Server-Side Rendering) hosted on `tilabs.io` infrastructure. The site provides structured data via JSON-LD schema embedded in HTML pages, making it suitable for scraping without JavaScript execution.

**Base URL:** `https://www.rvtrader.com`

---

## URL Structure & Patterns

### Search/Listing Pages

**Base Search URL:**
```
https://www.rvtrader.com/rvs-for-sale
```

**With Location Filter:**
```
https://www.rvtrader.com/rvs-for-sale?zip={zipcode}
```

### Pagination

- **Parameter:** `page=N` (1-indexed)
- **Results per page:** 36 listings
- **Total listings:** ~225,571 (as of analysis date)
- **Max pages:** ~6,266

**Example:**
```
https://www.rvtrader.com/rvs-for-sale?zip=60616&page=2
https://www.rvtrader.com/rvs-for-sale?zip=60616&page=100
```

### Filter Parameters

Filters use a special format with pipe-separated IDs:
```
parameter=Value|ID
```

| Parameter | Description | Example |
|-----------|-------------|---------|
| `zip` | Zip code for location-based search | `zip=60616` |
| `page` | Page number (1-indexed) | `page=2` |
| `make` | Manufacturer filter | `make=Forest%20River%7C440465` |
| `type` | RV type filter | `type=Class%20A%7C198067` |
| `condition` | New/Used condition | `condition=U` (Used), `condition=N` (New) |
| `price` | Price range | `price=10000-50000` |
| `year` | Year range | `year=2020-2024` |

**Combined Filter Example:**
```
https://www.rvtrader.com/rvs-for-sale?zip=60616&type=Class%20A%7C198067&make=Forest%20River%7C440465&condition=U&page=1
```

**Note:** The URL gets rewritten to include filter IDs after the pipe character. These IDs are RVTrader's internal identifiers.

### Detail Page URLs

**Pattern:**
```
https://www.rvtrader.com/listing/{year}-{make}-{model}-{listing_id}
```

**URL Encoding:**
- Spaces in make/model are encoded as `+`
- The listing ID is a 10-digit number

**Examples:**
```
https://www.rvtrader.com/listing/2026-Forest+River+Rv-Cherokee+Timberwolf+39AL-5037070155
https://www.rvtrader.com/listing/2017-Forest+River+Rv-Rockwood+Roo+233S-5038800792
https://www.rvtrader.com/listing/2025-Airstream-Globetrotter+25FB-5038791341
```

---

## Data Extraction Methods

### Method 1: JSON-LD Schema (Recommended)

The site embeds structured data in `<script type="application/ld+json">` tags. This is the most reliable extraction method.

**Location in HTML:**
```html
<script type="application/ld+json">
{...JSON data...}
</script>
```

**Extraction (Python):**
```python
import re
import json
import requests

def extract_jsonld(html):
    pattern = r'<script type="application/ld\+json">(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL)
    return [json.loads(m) for m in matches]

response = requests.get(url)
jsonld_data = extract_jsonld(response.text)
```

**Extraction (JavaScript/Node.js):**
```javascript
const regex = /<script type="application\/ld\+json">([\s\S]*?)<\/script>/g;
let match;
const results = [];
while ((match = regex.exec(html)) !== null) {
    results.push(JSON.parse(match[1]));
}
```

### Method 2: Browser Automation (Fallback)

For dynamic content or additional data not in JSON-LD, use Playwright/Puppeteer.

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(url)
    page.wait_for_load_state('networkidle')
    # Extract data from DOM
    specs = page.query_selector_all('.spec-item')
```

---

## Site Infrastructure

- **Framework:** Nuxt.js (Vue.js SSR)
- **CDN:** `cdn-static.tilabs.io/marketplace/ssr/rv`
- **Media CDN:** `cdn-media.tilabs.io`
- **Image URL Pattern:** `https://cdn-media.tilabs.io/v1/media/{image_id}.jpg?width={w}&height={h}`

---

## Rate Limiting & Best Practices

1. **Add delays between requests** (1-3 seconds recommended)
2. **Use proper User-Agent header**
3. **Respect robots.txt**
4. **Cache responses to avoid duplicate requests**
5. **Use JSON-LD extraction over DOM parsing when possible**

---

## Common RV Types

| Type | ID |
|------|-----|
| Class A | 198067 |
| Class B | 198068 |
| Class C | 198069 |
| Travel Trailer | 198070 |
| Fifth Wheel | 198071 |
| Pop-Up Camper | 198072 |
| Toy Hauler | 198073 |
| Destination Trailer | 198074 |

---

## Common Makes (Manufacturers)

| Make | ID |
|------|-----|
| Forest River | 440465 |
| Thor | 440466 |
| Keystone | 440467 |
| Jayco | 440468 |
| Winnebago | 440469 |
| Coachmen | 440470 |
| Grand Design | 440471 |
| Airstream | 440472 |
