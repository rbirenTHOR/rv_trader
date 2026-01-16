# RV Trader Project Status

**Date:** 2026-01-16
**Project Goal:** Help Thor Industries brands improve RVTrader.com listing rankings

---

## What's Been Built

### Core Scrapers (Working)

| Script | Purpose | Status |
|--------|---------|--------|
| `rank_listings.py` | Bulk search extraction (62 fields, ~5s/zip) | **COMPLETE** |
| `nuxt_extractor.py` | Single page extraction via Playwright | **COMPLETE** |

### Experimental Scrapers (In Progress)

| Script | Purpose | Status |
|--------|---------|--------|
| `detail_extractor.py` | Detail page specs extraction | Partial |
| `engagement_scraper.py` | Views/saves/days listed extraction | **Blocked** |
| `spec_scraper.py` | Spec field extraction | Partial |
| `fast_detail_scraper.py` | Batch detail extraction | Partial |

---

## What's Been Discovered

### Ranking Algorithm (Reverse-Engineered)

```
FINAL_RANK = sort_by(
    1. TIER: top_premium > premium > standard
    2. relevance_score (within tier)
    3. AGE_PENALTY (older listings penalized)
    4. freshness boost (badge_status: newly_listed)
)
```

### Key Ranking Factors

**See full documentation: `docs/RANKING_ALGORITHM.md`**

| Factor | Relevance Impact | Merch Impact |
|--------|-----------------|--------------|
| **Premium placement** | Tier override | None |
| **has_price** | +194 points | +5 points |
| **has_vin** | +165 points | +6 points |
| **photo_count (35+)** | +195 points | +30 points |
| **has_floorplan** | +50 points | **+12 points** |
| **description_length** | Indirect | **+45 points** (2000+ chars) |

### Merch Score Components

**See full documentation: `docs/MERCH_SCORE.md`**

| Factor | Correlation | Estimated Points |
|--------|-------------|------------------|
| description_length | 0.899 | +45 (2000+ chars) |
| has_length | 0.702 | +8 |
| photo_count | 0.658 | +30 (35+ photos) |
| has_floorplan | 0.554 | **+12 (Easy Win!)** |
| has_vin | 0.412 | +6 |

### Key Finding: Description Length

- Search API truncates ALL descriptions to 150 chars
- **Full description length DOES matter** for merch_score (r=0.899!)
- Must fetch detail pages to get real description length
- Recommendation: 1500+ characters for optimal score

---

## Where We Got Stuck

### Engagement Data (Views/Saves/Days Listed)

**Problem:** The engagement stats API endpoints were discovered:
```
/gettiledata/addetail_listingstats/showadviewsstats?adId={id}
/gettiledata/addetail_listingstats/showsavedadsstats?adId={id}
```

**Status:** API returns HTML, needs proper session/cookies. User had working Jupyter notebook code but session crashed before integrating.

### Detail Page Batch Scraping

**Problem:** Need to fetch ~1,600+ detail pages to get:
- Full description length
- All spec fields
- Engagement data (views, saves, days listed)

**Status:** HTTP requests get 401 blocked. Playwright works but is slow.

---

## Planned Analytics Pipeline (Not Started)

The original plan was to build 4 modules:

| Module | Purpose | Status |
|--------|---------|--------|
| 1. `process_listings.py` | Tag Thor brands, calc quality scores | NOT STARTED |
| 2. `brand_report.py` | Thor vs competitor aggregations | NOT STARTED |
| 3. `listing_recommendations.py` | Per-listing improvement actions | NOT STARTED |
| 4. `dealer_scorecard.py` | Dealer-level performance cards | NOT STARTED |

---

## Next Steps (Recommended Priority)

### Phase 1: Complete Data Collection

1. **Fix engagement scraper** - Integrate the working API code from Jupyter
   - Views: `/gettiledata/addetail_listingstats/showadviewsstats`
   - Saves: `/gettiledata/addetail_listingstats/showsavedadsstats`

2. **Create batch detail scraper** - Get full description + specs
   - Use ScraperAPI to avoid blocks
   - Extract: description_length, all specs, engagement data

3. **Merge data** - Combine search results + detail data into unified dataset

### Phase 2: Build Analytics

4. **Process listings** - Tag Thor brands, calculate quality gaps

5. **Build brand report** - Compare Thor brands vs competitors:
   - Avg rank by brand
   - % in top 10
   - Photo count gaps
   - Description length gaps
   - Premium tier usage

6. **Generate recommendations** - Per-listing action items:
   - "Add 15 more photos"
   - "Add floorplan"
   - "Request premium placement"
   - "Improve description"

### Phase 3: Operationalize

7. **Multi-zip extraction** - Run across multiple markets
8. **Tracking over time** - Compare week-over-week improvements
9. **Dealer scorecards** - Aggregate by dealer for Thor sales team

---

## Thor Industries Brands to Track

| Brand | Make IDs to Match |
|-------|-------------------|
| Thor Motor Coach | thor, thor motor coach |
| Jayco | jayco |
| Airstream | airstream |
| Tiffin | tiffin |
| Entegra Coach | entegra, entegra coach |
| Heartland | heartland |
| Cruiser RV | cruiser |
| Keystone | keystone |
| Dutchmen | dutchmen |

---

## Files to Clean Up

The following scripts may be redundant or incomplete:
- `src/spec_scraper.py`
- `src/spec_scraper_playwright.py`
- `src/detail_extractor.py`
- `src/fast_detail_scraper.py`
- `src/engagement_scraper.py`

**Recommendation:** Consolidate into a single `detail_batch_scraper.py` that handles specs + engagement.

---

## Output Files

| File | Contents | Rows |
|------|----------|------|
| `ranked_listings_20260116_151303.csv` | Search results with 62 fields | 1,600+ |
| `engagement_stats_20260116_165224.json` | Partial engagement data | ~50 |
| `full_detail_data_*.json` | Detail page extracts | ~50 |

---

## Technical Blockers Resolved

- **360 listing cap** - Solved with price chunking ($5k increments)
- **Bot protection** - Solved with ScraperAPI
- **Slow extraction** - Optimized from 55s to 5s with async HTTP

## Technical Blockers Remaining

- **Engagement API auth** - Need proper session cookies
- **Detail page scale** - Playwright too slow, HTTP gets blocked
