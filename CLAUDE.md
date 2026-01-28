# RVTrader Scraper

## Project Goal
Extract RV listing data from RVTrader.com to help **Thor Industries brands** (Thor Motor Coach, Jayco, Airstream, Tiffin, Entegra Coach, Heartland, Keystone, Cruiser, Dutchmen) improve their listing rankings.

## Quick Start (3 Commands)
```bash
# 1. Extract search rankings (JSON only)
python src/complete/rank_listings.py --zip 60616 --type "Class B"

# 2. Fetch engagement data (views/saves) - auto-tests cookies
python src/complete/engagement_scraper.py

# 3. Build standalone dashboard (single HTML file with embedded data)
python src/complete/build_dashboard.py
# Output: output/reports/rv_dashboard_standalone.html
# Just open the file in any browser - works offline!
```

### Multi-Zip / Multi-Type Workflow
```bash
# Extract data for multiple zips and types
python src/complete/rank_listings.py --zip-file zip_codes_national.txt --radius 100 --type "Class A"
python src/complete/rank_listings.py --zip-file zip_codes_national.txt --radius 100 --type "Class B"

# Fetch engagement for latest extraction
python src/complete/engagement_scraper.py

# Build standalone dashboard
python src/complete/build_dashboard.py
```

## Project Structure
```
rv_trader_2/
├── CLAUDE.md                    # THIS FILE - Project context
├── zip_codes.txt                # Custom zip codes (one per line)
├── zip_codes_national.txt       # 53 zips targeting RV buyer markets @ 100mi
├── src/
│   └── complete/
│       ├── rank_listings.py           # Core: Search extraction (JSON only)
│       ├── engagement_scraper.py      # Core: Views/saves extraction (30 concurrent)
│       ├── build_dashboard.py         # Core: Standalone HTML dashboard generator
│       ├── export_flat_file.py        # Optional: BI/data warehouse CSV export
│       ├── weekly_tracker.py          # Optional: Historical tracking
│       ├── dealer_premium_audit.py    # Optional: Premium tier detection
│       ├── description_scraper.py     # Optional: Full descriptions
│       └── archive/                   # Legacy scripts (not used)
│           ├── consolidate_data.py
│           ├── thor_brand_analysis.py
│           ├── thor_brand_analysis_v2.py
│           ├── thor_report_html.py
│           ├── regional_summary.py
│           ├── dealer_scorecard.py
│           └── spec_scraper.py
├── output/
│   ├── ranked_listings_*.json         # Search extraction data
│   ├── engagement_stats_*.json        # Engagement data (views/saves)
│   ├── reports/
│   │   └── rv_dashboard_standalone.html  # THE OUTPUT (single file)
│   └── history/                       # Weekly tracking data (optional)
└── docs/
    ├── RANKING_ALGORITHM.md           # Complete ranking formula
    └── MERCH_SCORE.md                 # Merch score components
```

---

## Current Status (2026-01-28)

### Core Scripts (Active)
| Script | Purpose | Status |
|--------|---------|--------|
| `rank_listings.py` | Search results extraction (64 fields, JSON only) | ✅ UPDATED |
| `engagement_scraper.py` | Views/saves API extraction (30 concurrent, auto-test) | ✅ UPDATED |
| `build_dashboard.py` | Standalone HTML dashboard with embedded data | ✅ NEW |

### Optional Scripts
| Script | Purpose | Status |
|--------|---------|--------|
| `export_flat_file.py` | Flat CSV export for data warehouse/BI (77 cols) | ✅ Available |
| `weekly_tracker.py` | Week-over-week tracking | ✅ Available |
| `dealer_premium_audit.py` | Premium tier detection from rank data | ✅ Available |
| `description_scraper.py` | Full descriptions from detail pages | ✅ Available |

### Archived Scripts (Legacy)
Moved to `src/complete/archive/`:
- consolidate_data.py (replaced by build_dashboard.py)
- thor_brand_analysis.py, thor_brand_analysis_v2.py
- thor_report_html.py, regional_summary.py, dealer_scorecard.py
- spec_scraper.py (timeout issues)

---

## Standalone Dashboard

The output is a **single HTML file** with all data embedded:

| Feature | Description |
|---------|-------------|
| **Standalone** | Works offline - just open the file, no server needed |
| **Embedded Data** | JSON data embedded in HTML - single file distribution |
| **Filter: Brand** | Dropdown to filter by any make |
| **Filter: Tier** | Top Premium / Premium / Standard checkboxes |
| **Filter: Year** | Model year (2026, 2025, older) |
| **Filter: Position** | Competitive position (Dominant, Strong, etc.) |
| **Filter: Search Zip** | Filter by query zip code |
| **Filter: RV Type** | Filter by Class A, Class B, etc. |
| **Filter: Region** | Geographic region |
| **Filter: Thor Only** | Toggle to show only Thor brands |
| **Sortable Table** | Click any column to sort |
| **Image Preview** | Hover to see RV image |
| **Click to Open** | Click row to open on RVTrader |
| **Export CSV** | Export filtered data |
| **Auto-Clean** | Old data files auto-removed |

### Architecture
```
rank_listings.py → ranked_listings_*.json
         ↓
engagement_scraper.py → engagement_stats_*.json
         ↓
    build_dashboard.py
         ↓
    rv_dashboard_standalone.html (THE OUTPUT)
```

---

## Performance (2026-01-27)

### Benchmark: 2 zips × 11 types × 50mi × NEW
| Step | Duration | Listings | Rate |
|------|----------|----------|------|
| Search extraction | ~10 sec | 3,497 | ~350/sec |
| Engagement scraper | 31.6 sec | 3,497 | 110.8/sec |
| **TOTAL** | **~42 sec** | **3,497** | - |

### Scaling Estimate (National - 53 zips × 11 types)
- Search: ~5-10 minutes
- Engagement: ~5-10 minutes
- Total: **~10-20 minutes** for full national dataset

---

## Ranking Algorithm

### The Formula
```
FINAL_RANK = SORT_BY(
    1. TIER           [top_premium > premium > standard]
    2. PREMIUM_LEVEL  [Tier A > Tier B within premium]
    3. relevance_score [within tier/level]
    4. AGE_PENALTY    [older listings demoted]
)
```

### Tier System
| Tier | Positions | Requirement |
|------|-----------|-------------|
| Top Premium | 1-3 | Paid ($$$$) |
| Premium Tier A | 4-10 | Paid ($$$) |
| Premium Tier B | 11-42 | Paid ($$) |
| Standard | 43+ | Free |

### Ranking Factors (Standard tier only)
| Factor | Relevance Pts | Impact |
|--------|---------------|--------|
| has_price | +194 | Strong |
| has_vin | +165 | Strong |
| 35+ photos | +195 | Moderate |
| has_floorplan | +50 | Weak |
| Model year | +24/year | Strong |

**~15 relevance points ≈ 1 rank position**

### Key Finding: Model Year Impact
**2026 Standard ≈ 2025 Premium** - Year bonus (~24-51 pts) roughly equals premium tier boost.

### Competitive Positions
| Position | Criteria |
|----------|----------|
| **Dominant** | Top Premium + 2026 |
| **Strong** | Premium + 2026 OR Top Premium + 2025 |
| **Competitive** | Standard + 2026 |
| **Neutral** | Premium + 2025 |
| **At Risk** | Standard + 2025 |
| **Disadvantaged** | 2+ years old |

---

## Thor Industries Brands

| Brand | Make Patterns |
|-------|---------------|
| Thor Motor Coach | thor, thor motor coach |
| Jayco | jayco |
| Airstream | airstream |
| Tiffin Motorhomes | tiffin, tiffin motorhomes |
| Entegra Coach | entegra, entegra coach |
| Heartland RV | heartland |
| Keystone RV | keystone |
| Cruiser RV | cruiser |
| Dutchmen RV | dutchmen |

---

## National Coverage (53 Zip Codes @ 100mi)

Use `zip_codes_national.txt` for comprehensive US RV market coverage.

| Region | Zips | Key Markets |
|--------|------|-------------|
| **Midwest Manufacturing** | 7 | Elkhart IN (RV Capital), Fort Wayne, Toledo |
| **Florida** | 7 | Ocala, Fort Myers, Lakeland, Daytona |
| **Texas** | 7 | Fort Worth, Katy, McKinney |
| **Arizona (Snowbird)** | 5 | Mesa, Yuma, Flagstaff |
| **California (Inland)** | 5 | Temecula, Bakersfield, Fresno |

---

## Environment
```bash
# Python path
C:\Users\rbiren\AppData\Local\anaconda3\python.exe

# Dependencies
pip install aiohttp playwright requests
playwright install chromium
```

---

## API Reference

### Search API (no auth)
```
GET https://www.rvtrader.com/ssr-api/search-results
    ?type={Type}|{TypeCode}
    &page={N}
    &zip={Zip}
    &radius={Miles}
    &condition={N|U}
```
- 36 results per page, max 10 pages (360 cap)

### Engagement APIs (require cookies)
```
Views: /gettiledata/addetail_listingstats/showadviewsstats?adId={id}
Saves: /gettiledata/addetail_listingstats/showsavedadsstats?adId={id}
```
- Cookies cached in `src/.cookie_cache.json` (14 day expiry)
- **Auto-test:** Script tests one request before batch; auto-refreshes if needed
- **NOTE:** Requires `datadome` cookie which is IP-bound

---

## ScraperAPI Integration

**API Key:** `ef66e965591986214ea474407eb0adc8`

| Script | ScraperAPI | Flag | Notes |
|--------|------------|------|-------|
| `rank_listings.py` | ✅ Works | `--use-proxy` | Search API doesn't need cookies |
| `engagement_scraper.py` | ❌ No | N/A | Needs datadome cookie (IP-bound) |

```bash
# Search with IP rotation (for large national extractions)
python src/complete/rank_listings.py --zip 60616 --type "Class B" --use-proxy
```
