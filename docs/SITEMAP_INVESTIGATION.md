# RVTrader Sitemap Investigation

## Summary

**Issue**: Website shows ~225,693 listings but sitemaps only contain ~166,445 listings (26% gap).

**Root Cause**: Sitemaps have not been updated since **January 26, 2024** - nearly 2 years stale.

---

## Evidence

### Listing Counts Comparison

| Source | Count | Notes |
|--------|-------|-------|
| Website (rvtrader.com) | 225,693 | Live count from search results |
| Sitemaps (S3 + official) | 166,445 | Frozen since Jan 2024 |
| **Gap** | **~59,000** | 26% of listings missing |

### Sitemap Details

**S3 Sitemaps** (used by our scraper):
```
https://s3.amazonaws.com/rec-sitemaps/rv/sitemap_rv_listings_0.xml  → 50,000 listings
https://s3.amazonaws.com/rec-sitemaps/rv/sitemap_rv_listings_1.xml  → 50,000 listings
https://s3.amazonaws.com/rec-sitemaps/rv/sitemap_rv_listings_2.xml  → 50,000 listings
https://s3.amazonaws.com/rec-sitemaps/rv/sitemap_rv_listings_3.xml  → 16,445 listings
                                                            Total:   166,445 listings
```

**Official Sitemaps** (from robots.txt):
- Root: `https://www.rvtrader.com/sitemaps/rv-sitemap-root.xml`
- Contains same 4 listing sitemaps with identical data
- Last modified date in index: `2024-01-26`

### Listing ID Analysis

**Sitemap ID Range**:
```
Smallest ID: 5000825673
Largest ID:  5030357010
```

**Current Website ID Range**:
```
Sample IDs: 5037585715, 5038308226, 5039045394, etc.
```

**Prefix Distribution in Sitemap**:
```
500x:     227 listings
501x:   1,811 listings
502x: 137,695 listings
503x:  26,679 listings (only up to 5030357010)
```

### Verification Test

Tested 10 listing IDs from current website against sitemap:

| Listing ID | In Sitemap? |
|------------|-------------|
| 5039045394 | NO |
| 5039031922 | NO |
| 5037585715 | NO |
| 5037916050 | NO |
| 5038308226 | NO |
| 5038935123 | NO |
| 5038403214 | NO |
| 5039047227 | NO |
| 5038222874 | NO |
| 5039044424 | NO |

**Result**: 0/10 current listings found in sitemap - confirms sitemaps are stale.

### Date Distribution in Sitemap

Sample from `sitemap_rv_listings_0.xml`:
```
2023-04:     5 listings
2023-05:     1 listing
2023-08:     1 listing
2023-09:    16 listings
2023-10:    91 listings
2023-11:   778 listings
2023-12: 1,572 listings
2024-01: 47,536 listings  ← bulk of listings, then stops
```

---

## Implications

1. **Sitemap extraction is incomplete** - only captures ~74% of listings
2. **No new listings since Jan 2024** - missing ~59K newer listings
3. **Sitemap data is historical** - useful for older listings only

---

## SOLUTION: `__NUXT_DATA__` Extraction (Recommended)

### Discovery

Search result pages contain a `<script id="__NUXT_DATA__">` tag with **complete listing data** for all listings on the page (~72 per page). This is far richer than sitemap data!

### Data Available from `__NUXT_DATA__`

**Per Listing (72 fields+):**
```
Core IDs:
- id                    → Listing ID (e.g., "5036655023")
- vehicle.adId          → Same as id
- vehicle.dealerId      → Dealer ID
- vehicle.customerId    → Customer ID

Vehicle Info:
- vehicle.makeName      → ["Winnebago"]
- vehicle.modelName     → ["Revel 44E 4x4"]
- vehicle.trimName      → ["44E"]
- vehicle.className     → "Class B"
- vehicle.condition     → "Used"
- vehicle.price         → "$144,500"
- mileage               → 14264
- mfrSerialNum          → VIN! (e.g., "W1W4EBVY9NP470480")

Location:
- zipCode               → "44481"
- vehicle.city          → "warren"
- vehicle.stateCode     → "OH"
- latitude              → "41.17600"
- longitude             → "-80.86960"

Dealer:
- companyName           → "Pop RVs"
- vehicle.dealerGroupName
- vehicle.dealerWebsiteUrl
- vehicle.phone
- vehicle.dealerPhone   → Array of phone numbers

Media:
- vehicle.photoIds      → Array of 85+ photo IDs
- vehicle.floorplanMediaid
- photoCount

Dates & Pricing:
- createDate            → "2025-06-07T10:11:07Z"
- createDateFormatted   → "Jun 7 2025"
- msrp
- priceHistory          → {"2025-07-21 06:34:23": "150000"}
- datePriceDrop

Metadata:
- stockNumber
- sellerType            → "Dealer"
- badgeStatus           → ["willing_to_negotiate", "history_report"]
- trustedPartner        → "5 year trusted partner"
- adFeatures            → {premium, topPremium, buyNow, etc.}
- dealerFeatures        → 60+ dealer capability flags
- vehicle.adDetailUrl   → Full listing URL
- vehicle.description   → HTML description text
```

### Extraction Method

```javascript
// In browser console or Playwright
const nuxtScript = document.querySelector('script#__NUXT_DATA__');
const data = JSON.parse(nuxtScript.textContent);

// Resolver for Nuxt's reference-based format
function resolve(val, depth = 0) {
  if (depth > 10) return val;
  if (typeof val === 'number' && Number.isInteger(val) && val >= 0 && val < data.length) {
    return resolve(data[val], depth + 1);
  }
  if (Array.isArray(val)) return val.map(v => resolve(v, depth + 1));
  if (val && typeof val === 'object') {
    const resolved = {};
    for (const [k, v] of Object.entries(val)) resolved[k] = resolve(v, depth + 1);
    return resolved;
  }
  return val;
}

// Find and resolve listings
const listings = [];
for (let i = 0; i < data.length; i++) {
  const item = data[i];
  if (item && typeof item === 'object' && item.classId && item.vehicle) {
    listings.push(resolve(item));
  }
}
```

### Coverage Strategy

**By RV Type (tested counts):**
| Type | Listings | Pages Needed |
|------|----------|--------------|
| Travel Trailer | 122,982 | 1,708 |
| Fifth Wheel | 36,261 | 504 |
| Class C | 19,600 | 273 |
| Class A | 15,347 | 214 |
| Toy Hauler | 14,017 | 195 |
| Class B | 8,540 | 119 |
| Truck Camper | 2,606 | 37 |
| Destination Trailer | 2,257 | 32 |
| Pop-Up Camper | 1,989 | 28 |
| Park Model | 1,100 | 16 |
| Teardrop Trailer | 730 | 11 |

**URL Pattern:**
```
https://www.rvtrader.com/rvs-for-sale?type=Travel%20Trailer%7C198073&page=1
https://www.rvtrader.com/rvs-for-sale?type=Class%20B%7C198068&page=1
```

**Total: ~3,137 pages to scrape all 225K listings**

### `trk` Object (Metadata Only)

Also available on search pages - useful for verification:
```javascript
window.trk = {
  pagename: "search/results",
  numresults: "8540",
  pagenumber: "2",
  statename: "illinois",
  zipcode: "60616",
  dma: "602-chicago",
  // ...
}
```

---

## Recommendations (Updated)

1. **Use `__NUXT_DATA__` extraction** - richest data source, includes VIN!
2. **Scrape by RV type** - natural segmentation, ~3,137 pages total
3. **Use Playwright** - required for JavaScript execution
4. **Implement rate limiting** - respect the site, ~1 req/sec
5. **Keep sitemap data** - still useful for historical reference

---

## Alternative Methods (Backup)

### 1. Search Results Pagination
- URL: `https://www.rvtrader.com/rvs-for-sale?page=N`
- Pagination works up to ~9,027 pages (tested)
- 25 listings per page × 9,027 = 225K (matches!)

### 2. Filtered Search Queries
- Break down by: make, year, state, price range, RV type
- Combine filters to get under pagination limits
- Useful if type-based approach hits limits

### 3. Dealer Inventory Pages
- URL pattern: `https://www.rvtrader.com/dealer/{dealer-slug}`
- Scrape all dealer pages to get their inventory
- May avoid pagination limits

### 4. New Listing Monitoring
- Sort by "newly listed" and scrape regularly
- Build incremental database over time

---

## Technical Notes

### robots.txt Location
```
https://www.rvtrader.com/robots.txt
Sitemap: https://www.rvtrader.com/sitemaps/rv-sitemap-root.xml
```

### No Additional Sitemaps
- Checked sitemaps 4-9: all return 301 redirects (not found)
- Only 4 listing sitemaps exist

### Bot Protection
- Site uses DataDome + reCAPTCHA
- HTTP requests work but may return partial data
- Playwright recommended for full data extraction

---

*Investigation completed: January 16, 2026*
