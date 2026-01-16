# RVTrader.com Complete Query Plan

## Overview

This document provides the complete URL structure and query sequence to extract all RV listings and their full metadata from RVTrader.com.

---

## Phase 1: List Page Scraping (Get All Listing URLs)

### Base URL
```
https://www.rvtrader.com/rvs-for-sale
```

### Pagination Pattern
```
https://www.rvtrader.com/rvs-for-sale?page={page_number}
```

| Parameter | Description | Example |
|-----------|-------------|---------|
| `page` | Page number (1-indexed) | `page=1`, `page=2`, ... `page=6266` |
| Results per page | Fixed at 36 | N/A |

### Full Dataset URLs

```
# Page 1 (first 36 listings)
https://www.rvtrader.com/rvs-for-sale?page=1

# Page 2 (listings 37-72)
https://www.rvtrader.com/rvs-for-sale?page=2

# Page 100 (listings 3565-3600)
https://www.rvtrader.com/rvs-for-sale?page=100

# Last page (~6266)
https://www.rvtrader.com/rvs-for-sale?page=6266
```

### With Location Filter (Recommended)
```
https://www.rvtrader.com/rvs-for-sale?zip={zip_code}&page={page_number}
```

**Example:**
```
https://www.rvtrader.com/rvs-for-sale?zip=60616&page=1
https://www.rvtrader.com/rvs-for-sale?zip=60616&page=2
```

### Data Extraction (JSON-LD)

**Location in HTML:**
```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "RVs",
  "offers": {
    "@type": "AggregateOffer",
    "offers": [
      {
        "@type": "Offer",
        "url": "https://www.rvtrader.com/listing/2026-Forest+River+Rv-Cherokee+Timberwolf+39AL-5037070155",
        "itemOffered": {
          "name": "2026 Forest River Rv Cherokee Timberwolf 39AL",
          "itemCondition": "New",
          "price": "51495.00"
        }
      },
      // ... 35 more offers
    ]
  }
}
</script>
```

**Regex Pattern:**
```python
pattern = r'<script type="application/ld\+json">(.*?)</script>'
```

---

## Phase 2: Detail Page Scraping (Full Asset Info)

### URL Pattern
```
https://www.rvtrader.com/listing/{year}-{make}-{model}-{listing_id}
```

### URL Examples
```
https://www.rvtrader.com/listing/2026-Forest+River+Rv-Cherokee+Timberwolf+39AL-5037070155
https://www.rvtrader.com/listing/2017-Forest+River+Rv-Rockwood+Roo+233S-5038800792
https://www.rvtrader.com/listing/2025-Airstream-Globetrotter+25FB-5038791341
https://www.rvtrader.com/listing/2027-Luxe-48FLB-5038865990
https://www.rvtrader.com/listing/2018-Jayco-Jay+Flight+SLX+195RB-5038144169
```

### Data Sources on Detail Page

#### Source 1: JSON-LD (HTTP Request - No JS Required)
```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Vehicle",
  "sku": "5037070155",
  "name": "2026 Forest River Rv Destination Trailer",
  "url": "https://www.rvtrader.com/listing/2026-Forest-River-Rv-Cherokee-Timberwolf-39AL-5037070155",
  "image": "https://cdn-media.tilabs.io/v1/media/6916e5a189fd1e894b0aa31a.jpg?width=1200&height=1200",
  "brand": { "@type": "Brand", "name": "Forest River Rv" },
  "manufacturer": "Forest River Rv",
  "model": "Cherokee Timberwolf 39AL",
  "description": "2026 Forest River RV Cherokee Timberwolf 39AL...",
  "offers": {
    "@type": "Offer",
    "availability": "InStock",
    "priceCurrency": "USD",
    "price": "51495.00",
    "itemCondition": "NewCondition"
  }
}
</script>
```

#### Source 2: window.trk Object (Requires JS/Browser)
```javascript
// Access via: window.trk
{
  "adid": "5037070155",
  "custid": "11287114",
  "dealerid": "3054198",
  "make": "forest river rv",
  "model": "cherokee timberwolf 39al",
  "type": "destination trailer",
  "length": "45 ft",
  "condition": "new",
  "prodprice": "51495",
  "year": "2026",
  "listingtier": "premium_select",
  "dma": "602-chicago",
  "listingsellertype": "dealer",
  "searchzip": "60616",
  "statename": "illinois",
  "city": "chicago"
}
```

#### Source 3: DOM Stats (Requires JS/Browser)
```javascript
// Extract from page text
const text = document.body.innerText;
const daysListed = text.match(/(\d+)\s*days?\s*listed/i)?.[1];  // "190"
const saves = text.match(/(\d+)\s*saves?/i)?.[1];                // "0"
```

---

## Phase 3: Filtered Queries

### By RV Type
| Type | URL Parameter | Full URL |
|------|---------------|----------|
| All Types | (none) | `https://www.rvtrader.com/rvs-for-sale` |
| Class A | `type=Class%20A%7C198067` | `https://www.rvtrader.com/rvs-for-sale?type=Class%20A%7C198067` |
| Class B | `type=Class%20B%7C198068` | `https://www.rvtrader.com/rvs-for-sale?type=Class%20B%7C198068` |
| Class C | `type=Class%20C%7C198069` | `https://www.rvtrader.com/rvs-for-sale?type=Class%20C%7C198069` |
| Travel Trailer | `type=Travel%20Trailer%7C198073` | `https://www.rvtrader.com/rvs-for-sale?type=Travel%20Trailer%7C198073` |
| Fifth Wheel | `type=Fifth%20Wheel%7C198071` | `https://www.rvtrader.com/rvs-for-sale?type=Fifth%20Wheel%7C198071` |
| Toy Hauler | `type=Toy%20Hauler%7C198072` | `https://www.rvtrader.com/rvs-for-sale?type=Toy%20Hauler%7C198072` |
| Pop-Up Camper | `type=Pop%20Up%20Camper%7C198070` | `https://www.rvtrader.com/rvs-for-sale?type=Pop%20Up%20Camper%7C198070` |

### By Condition
| Condition | URL Parameter | Full URL |
|-----------|---------------|----------|
| New | `condition=N` | `https://www.rvtrader.com/rvs-for-sale?condition=N` |
| Used | `condition=U` | `https://www.rvtrader.com/rvs-for-sale?condition=U` |

### By Price Range
```
https://www.rvtrader.com/rvs-for-sale?price=10000-50000
https://www.rvtrader.com/rvs-for-sale?price=50000-100000
https://www.rvtrader.com/rvs-for-sale?price=100000-*
```

### By Year Range
```
https://www.rvtrader.com/rvs-for-sale?year=2020-2026
https://www.rvtrader.com/rvs-for-sale?year=2015-2020
```

### Combined Filters
```
https://www.rvtrader.com/rvs-for-sale?zip=60616&type=Class%20A%7C198067&condition=U&price=50000-150000&page=1
```

---

## Complete Scraping Workflow

### Step 1: Generate List Page URLs
```python
def generate_list_urls(max_pages=6266, zip_code=None, **filters):
    base = "https://www.rvtrader.com/rvs-for-sale"
    urls = []
    for page in range(1, max_pages + 1):
        params = {'page': page}
        if zip_code:
            params['zip'] = zip_code
        params.update(filters)
        query = '&'.join(f"{k}={v}" for k, v in params.items())
        urls.append(f"{base}?{query}")
    return urls

# Generate all URLs
urls = generate_list_urls(max_pages=6266)
# Returns: ['https://www.rvtrader.com/rvs-for-sale?page=1', ...]
```

### Step 2: Extract Listing URLs from Each Page
```python
import re
import json
import requests

def extract_listing_urls(page_url):
    response = requests.get(page_url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    # Extract JSON-LD
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', response.text, re.DOTALL)
    if not match:
        return []

    data = json.loads(match.group(1))
    offers = data.get('offers', {}).get('offers', [])

    return [offer.get('url') for offer in offers if offer.get('url')]

# Extract from page 1
listing_urls = extract_listing_urls('https://www.rvtrader.com/rvs-for-sale?page=1')
# Returns: ['https://www.rvtrader.com/listing/2026-Forest+River+Rv-...', ...]
```

### Step 3: Fetch Detail Page Data
```python
def fetch_detail_jsonld(listing_url):
    """HTTP-only extraction (no browser needed)"""
    response = requests.get(listing_url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', response.text, re.DOTALL)
    if not match:
        return None

    return json.loads(match.group(1))

# Fetch detail
detail = fetch_detail_jsonld('https://www.rvtrader.com/listing/2026-Forest+River+Rv-Cherokee+Timberwolf+39AL-5037070155')
```

### Step 4: Fetch Full Data (Browser Required)
```python
from playwright.sync_api import sync_playwright

def fetch_full_detail(listing_url):
    """Complete extraction including tracking object and stats"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(listing_url)
        page.wait_for_load_state('networkidle')

        # Get JSON-LD from page
        jsonld = page.evaluate('''() => {
            const script = document.querySelector('script[type="application/ld+json"]');
            return script ? JSON.parse(script.textContent) : null;
        }''')

        # Get tracking object
        trk = page.evaluate('() => window.trk || {}')

        # Get engagement stats
        stats = page.evaluate('''() => {
            const text = document.body.innerText;
            return {
                daysListed: (text.match(/(\\d+)\\s*days?\\s*listed/i) || [])[1] || null,
                saves: (text.match(/(\\d+)\\s*saves?/i) || [])[1] || null
            };
        }''')

        browser.close()

        return {
            'jsonld': jsonld,
            'tracking': trk,
            'engagement': stats
        }
```

---

## Output Data Structure

### Per-Listing Complete Record
```json
{
  "listing_id": "5037070155",
  "url": "https://www.rvtrader.com/listing/2026-Forest+River+Rv-Cherokee+Timberwolf+39AL-5037070155",

  "basic": {
    "name": "2026 Forest River Rv Cherokee Timberwolf 39AL",
    "year": "2026",
    "make": "Forest River Rv",
    "model": "Cherokee Timberwolf 39AL",
    "condition": "New",
    "price": "51495.00",
    "currency": "USD"
  },

  "details": {
    "type": "destination trailer",
    "length": "45 ft",
    "description": "2026 Forest River RV Cherokee Timberwolf 39AL...",
    "image": "https://cdn-media.tilabs.io/v1/media/6916e5a189fd1e894b0aa31a.jpg?width=1200&height=1200",
    "availability": "InStock"
  },

  "dealer": {
    "dealer_id": "3054198",
    "customer_id": "11287114",
    "seller_type": "dealer",
    "listing_tier": "premium_select"
  },

  "location": {
    "dma": "602-chicago",
    "search_zip": "60616"
  },

  "engagement": {
    "days_listed": "190",
    "saves": "0"
  },

  "metadata": {
    "scraped_at": "2026-01-16T12:00:00Z",
    "source_page": 1
  }
}
```

---

## Rate Limiting Recommendations

| Scrape Type | Delay | Requests/Hour | Full Dataset Time |
|-------------|-------|---------------|-------------------|
| List pages only | 1.5s | 2,400 | ~2.6 hours |
| List + Details (HTTP) | 1.5s | 2,400 | ~5-6 hours |
| List + Full Details (Browser) | 3.0s | 1,200 | ~12-15 hours |

---

## Quick Reference: All URL Patterns

```
# List pages
https://www.rvtrader.com/rvs-for-sale
https://www.rvtrader.com/rvs-for-sale?page={1-6266}
https://www.rvtrader.com/rvs-for-sale?zip={zipcode}&page={n}
https://www.rvtrader.com/rvs-for-sale?type={type}&condition={N|U}&price={min}-{max}&year={min}-{max}&page={n}

# Detail pages
https://www.rvtrader.com/listing/{year}-{make}-{model}-{listing_id}

# Images
https://cdn-media.tilabs.io/v1/media/{image_id}.jpg?width={w}&height={h}

# Similar listings API
https://www.rvtrader.com/search-results-data/similar-listings-contact?ad_id={listing_id}&make={make}&model={model}
```
