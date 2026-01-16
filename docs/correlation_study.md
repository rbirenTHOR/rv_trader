# RVTrader Correlation Study

**Date:** 2026-01-16
**Dataset:** 56 Class B listings, New condition, 60616 zip code, 50-mile radius

---

## Executive Summary

Analysis of RVTrader listing data to understand what factors correlate with merchandising score (merch_score) and search ranking. The goal is to identify actionable levers for improving listing visibility.

---

## Key Findings

### 1. Correlation Analysis (from Search API data)

| Factor | Correlation with Merch Score | Interpretation |
|--------|------------------------------|----------------|
| **length** (vehicle) | **+0.704** | Strong positive - longer RVs score higher |
| **photo_count** | **+0.658** | Strong positive - more photos = higher score |
| **has_floorplan** | **+0.502** | Moderate positive - floorplan uploads help |
| **rank** | **-0.409** | Moderate negative - higher merch = better rank |
| **has_vin** | **+0.346** | Weak positive - VIN disclosure helps |
| **has_price** | **+0.298** | Weak positive - price visibility helps |
| **description_length** | **-0.051** | No correlation (truncated at 150 chars in API) |

### 2. Group Analysis

| Group | Count | Avg Merch Score |
|-------|-------|-----------------|
| With floorplan | 28 | **117.1** |
| Without floorplan | 26 | 105.3 |
| Premium listings | 11 | 112.6 |
| Non-premium | 43 | 111.1 |

**Key Insight:** Floorplan upload provides +11.8 point merch score boost (largest controllable factor).

### 3. Merch Score Distribution

- **Range:** 72 - 125
- **Average:** 111.4
- **Top performers (122-125):** High photo counts (17-72), most have floorplans
- **Bottom performers (72-102):** Low/zero photos, no floorplans, some missing prices

---

## Data Sources

### Available from Search API (rank_listings.py)
- merch_score, relevance_score
- photo_count, floorplan_id
- price, is_premium, is_top_premium
- description (truncated to 150 chars)
- length, mileage, vin
- All 56 fields documented in CLAUDE.md

### Requires Detail Page Scraping
| Data | Source | Method |
|------|--------|--------|
| **views** | `/gettiledata/addetail_listingstats/showadviewsstats?adId={id}` | HTTP + datadome cookie |
| **saves** | `/gettiledata/addetail_listingstats/showsavedadsstats?adId={id}` | HTTP + datadome cookie |
| **full description** | `__NUXT_DATA__` script tag | Browser (Playwright) |
| **specs** (sleeping capacity, water capacity, slideouts, etc.) | `__NUXT_DATA__` script tag | Browser (Playwright) |

---

## Technical Discoveries

### API Endpoints Found

```
# Engagement stats (lazy-loaded, requires fresh datadome cookie)
GET https://www.rvtrader.com/gettiledata/addetail_listingstats/showadviewsstats?adId={ad_id}&realmId=%5Bobject%20Object%5D
Response: {"error":null,"listingViewsData":"138"}

GET https://www.rvtrader.com/gettiledata/addetail_listingstats/showsavedadsstats?adId={ad_id}&realmId=%5Bobject%20Object%5D
Response: {"error":null,"listingSavesData":1}
```

### Cookie Requirements
- `datadome` cookie required for API access
- Cookie expires quickly (~minutes)
- Can be obtained from browser session
- Full cookie string tested working in Jupyter notebook

### NUXT Data Structure
- Detail pages use Nuxt.js with `__NUXT_DATA__` script containing JSON
- Data uses reference-based format requiring recursive resolution
- Contains: specs (sleepingCapacity, waterCapacity, slideouts, etc.), full description
- **Cannot be obtained from raw HTML** - requires JavaScript execution

---

## Gaps / Data Not Yet Collected

1. **Engagement metrics (views, saves)** - API works but cookie expires; need fresh session
2. **Full description length** - Only 2 samples collected (1299-3000 chars)
3. **Spec data** - Extracted for 2 listings; need all 56
4. **Days listed** - Not yet identified API endpoint

---

## Hypotheses to Test (Pending Data)

1. **Description length vs engagement** - Does longer description = more views/saves?
2. **Spec completeness vs merch score** - Do more filled specs = higher score?
3. **Views/saves vs rank** - Does engagement drive ranking or vice versa?
4. **Photo quality vs engagement** - Does photo count correlate with views?

---

## Next Steps

### Priority 1: Get Engagement Data
```python
# Working approach (from Jupyter notebook)
# 1. Open browser, navigate to any RVTrader page
# 2. Extract datadome cookie
# 3. Use requests with cookie to hit engagement APIs
# 4. Process all 56 listings before cookie expires
```

### Priority 2: Get Spec/Description Data
- Use Playwright with non-headless browser
- Extract NUXT_DATA from each detail page
- Parse specs and full description

### Priority 3: Final Analysis
- Merge all data sources
- Run full correlation analysis including engagement
- Identify actionable recommendations

---

## Files

| File | Description |
|------|-------------|
| `output/ranked_listings_20260116_151303.json` | 56 listings with search API data |
| `src/rank_listings.py` | Search API scraper |
| `src/fast_detail_scraper.py` | Combined API + Playwright scraper (WIP) |
| `src/engagement_scraper.py` | HTTP-only engagement scraper |
| `src/spec_scraper_playwright.py` | Playwright-based spec extractor |

---

## Raw Correlation Data

```
Valid listings: 54

=== CORRELATIONS WITH MERCH SCORE ===
rank vs merch:         -0.409
photo_count vs merch:  +0.658
has_floorplan vs merch:+0.502
has_price vs merch:    +0.298
has_vin vs merch:      +0.346
length vs merch:       +0.704
desc_length vs merch:  -0.051 (truncated data)

=== TOP 10 BY MERCH SCORE ===
Rank 23: merch=125, photos=72, floorplan=N, price=Y
Rank  8: merch=124, photos=34, floorplan=Y, price=Y
Rank 11: merch=124, photos=34, floorplan=Y, price=Y
Rank 12: merch=124, photos=32, floorplan=Y, price=Y
Rank 13: merch=124, photos=17, floorplan=Y, price=Y
Rank 16: merch=124, photos=33, floorplan=Y, price=Y
Rank 21: merch=124, photos=63, floorplan=Y, price=Y
Rank 30: merch=124, photos=51, floorplan=Y, price=Y

=== BOTTOM 10 BY MERCH SCORE ===
Rank 55: merch=72, photos=1, floorplan=N, price=N
Rank 43: merch=84, photos=0, floorplan=N, price=Y
Rank 46: merch=84, photos=0, floorplan=N, price=Y
Rank 47: merch=84, photos=0, floorplan=N, price=Y
```
