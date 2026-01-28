# RVTrader Competitive Intelligence Platform

A data extraction and analysis toolkit for monitoring RV listing performance on RVTrader.com, designed to help **Thor Industries brands** (Jayco, Airstream, Thor Motor Coach, Keystone, Heartland, Tiffin, Entegra Coach, Cruiser RV, Dutchmen RV) improve their search rankings and optimize listing quality.

## Overview

This platform provides:
- **Data Collection** - Automated extraction of listing data and engagement metrics
- **Ranking Analysis** - Understanding of RVTrader's search ranking algorithm
- **Competitive Benchmarking** - Thor vs competitor performance comparison
- **Interactive Dashboard** - Single standalone HTML file with filtering and sorting

## Quick Start (3 Commands)

```bash
# 1. Install dependencies
pip install aiohttp playwright requests
playwright install chromium

# 2. Extract search rankings
python src/complete/rank_listings.py --zip 60616 --type "Class B"

# 3. Fetch engagement data (views/saves)
python src/complete/engagement_scraper.py

# 4. Build standalone dashboard
python src/complete/build_dashboard.py

# Output: output/reports/rv_dashboard_standalone.html
# Just open in any browser - works offline!
```

### Multi-Market Extraction

```bash
# National coverage (53 zip codes × all RV types)
python src/complete/rank_listings.py --zip-file zip_codes_national.txt --radius 100

# Fetch engagement and build dashboard
python src/complete/engagement_scraper.py
python src/complete/build_dashboard.py
```

## Architecture

```
rv_trader_2/
├── src/complete/                 # Production scripts
│   ├── rank_listings.py          # Core: Search extraction (JSON only)
│   ├── engagement_scraper.py     # Core: Views/saves extraction
│   ├── build_dashboard.py        # Core: Standalone HTML dashboard
│   ├── export_flat_file.py       # Optional: BI/data warehouse CSV
│   ├── weekly_tracker.py         # Optional: Historical tracking
│   ├── dealer_premium_audit.py   # Optional: Premium tier detection
│   ├── description_scraper.py    # Optional: Full descriptions
│   └── archive/                  # Legacy scripts (not used)
├── docs/                         # Technical documentation
│   ├── RANKING_ALGORITHM.md      # Complete ranking formula
│   └── MERCH_SCORE.md            # Merchandising score analysis
├── output/
│   ├── ranked_listings_*.json    # Search extraction data
│   ├── engagement_stats_*.json   # Engagement data
│   └── reports/
│       └── rv_dashboard_standalone.html  # THE OUTPUT
└── zip_codes_national.txt        # 53 RV buyer markets
```

## Core Scripts

### rank_listings.py

Fast bulk extraction of search results using async HTTP. Extracts 64 fields per listing.

```bash
python src/complete/rank_listings.py                     # All zips in zip_codes.txt
python src/complete/rank_listings.py --zip 60616         # Single zip code
python src/complete/rank_listings.py --type "Class B"    # Single RV type
python src/complete/rank_listings.py --condition U       # Used inventory (default: New)
python src/complete/rank_listings.py --radius 100        # Custom radius (default: 50mi)
python src/complete/rank_listings.py --use-proxy         # ScraperAPI IP rotation
python src/complete/rank_listings.py --zip-file zip_codes_national.txt  # Multi-zip
```

**Performance:** ~350 listings/second with 50 concurrent requests

**Fields Extracted:**
| Category | Fields |
|----------|--------|
| Ranking | rank, relevance_score, merch_score, ad_listing_position |
| Premium | is_premium, is_top_premium, badge_status, scheme_code |
| Vehicle | year, make, model, trim, class, condition, length, mileage |
| Pricing | price, msrp, rebate, price_drop_date |
| Quality | photo_count, floorplan_id, vin, description |
| Dealer | dealer_name, dealer_group, dealer_phone, dealer_website |
| Location | city, state, zip_code, latitude, longitude, region |

### engagement_scraper.py

Fetches view and save counts from RVTrader's internal APIs.

```bash
python src/complete/engagement_scraper.py                    # Auto-tests cookies first
python src/complete/engagement_scraper.py --refresh-cookies  # Force cookie refresh
python src/complete/engagement_scraper.py --input file.json  # Specific input file
```

**Performance:** ~111 listings/second with 30 concurrent requests

**Cookie Management:**
- Cookies cached in `src/.cookie_cache.json` (14-day expiry)
- Auto-tests cookies before batch; auto-refreshes if they fail
- Browser opens for manual refresh when needed

### build_dashboard.py

Generates a standalone HTML dashboard with all data embedded.

```bash
python src/complete/build_dashboard.py                    # Uses latest data files
python src/complete/build_dashboard.py --input file.json  # Specific input
python src/complete/build_dashboard.py --keep-data        # Don't auto-clean old files
```

**Dashboard Features:**
| Feature | Description |
|---------|-------------|
| **Standalone** | Works offline - just open the file |
| **Embedded Data** | JSON data embedded in HTML |
| **Filters** | Brand, Tier, Year, Position, Region, RV Type, Search Zip |
| **Thor Filter** | Toggle to show only Thor brands |
| **Sortable** | Click any column to sort |
| **Image Preview** | Hover to see RV image |
| **Click to Open** | Click row to open on RVTrader |
| **Export CSV** | Export filtered data |
| **Auto-Clean** | Removes old data files |

## Optional Scripts

### export_flat_file.py

Generates 77-column CSV for data warehouse/BI tools.

```bash
python src/complete/export_flat_file.py                   # Latest file
python src/complete/export_flat_file.py --combine-session # Combine recent extractions
python src/complete/export_flat_file.py --append          # Append to master file
```

### weekly_tracker.py

Tracks listing changes over time for week-over-week analysis.

```bash
python src/complete/weekly_tracker.py                     # Update + report
python src/complete/weekly_tracker.py --report            # Report only
```

## Ranking Algorithm

RVTrader uses a **tiered ranking system** where paid placement dominates:

```
FINAL_RANK = SORT_BY(
    1. TIER           [top_premium > premium > standard]
    2. PREMIUM_LEVEL  [Tier A > Tier B within premium]
    3. relevance_score [within tier/level, descending]
    4. AGE_PENALTY    [older listings demoted]
)
```

### Tier System

| Tier | Positions | Requirement |
|------|-----------|-------------|
| Top Premium | 1-3 | Paid placement ($$$$) |
| Premium Tier A | 4-10 | Higher premium package ($$$) |
| Premium Tier B | 11-42 | Basic premium package ($$) |
| Standard | 43+ | Free listing |

### Ranking Factors (Standard Tier Only)

| Factor | Relevance Pts | Rank Correlation |
|--------|---------------|------------------|
| has_price | +194 | -0.840 (strong) |
| has_vin | +165 | -0.689 (strong) |
| 35+ photos | +195 | -0.611 (moderate) |
| has_floorplan | +50 | -0.300 (weak) |
| Model year | +24/year | strong |

**~15 relevance points ≈ 1 rank position improvement**

### Key Finding: Model Year Impact

**2026 Standard ≈ 2025 Premium** - The year bonus (~24-51 pts) roughly equals the premium tier boost.

### Competitive Positions

| Position | Criteria |
|----------|----------|
| **Dominant** | Top Premium + 2026 |
| **Strong** | Premium + 2026 OR Top Premium + 2025 |
| **Competitive** | Standard + 2026 |
| **Neutral** | Premium + 2025 |
| **At Risk** | Standard + 2025 |
| **Disadvantaged** | 2+ years old |

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

## RV Type Codes

| Type | Code |
|------|------|
| Class A | 198066 |
| Class B | 198068 |
| Class C | 198067 |
| Fifth Wheel | 198069 |
| Travel Trailer | 198073 |
| Toy Hauler | 198074 |
| Truck Camper | 198072 |
| Pop-Up Camper | 198071 |
| Park Model | 198070 |
| Destination Trailer | 671069 |
| Teardrop Trailer | 764498 |

## National Coverage (53 Zip Codes)

Use `zip_codes_national.txt` for comprehensive US RV market coverage:

| Region | Zips | Key Markets |
|--------|------|-------------|
| **Midwest Manufacturing** | 7 | Elkhart IN (RV Capital), Fort Wayne, Toledo |
| **Florida** | 7 | Ocala, Fort Myers, Lakeland, Daytona |
| **Texas** | 7 | Fort Worth, Katy, McKinney |
| **Arizona (Snowbird)** | 5 | Mesa, Yuma, Flagstaff |
| **California (Inland)** | 5 | Temecula, Bakersfield, Fresno |

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
# Views
GET /gettiledata/addetail_listingstats/showadviewsstats?adId={id}

# Saves
GET /gettiledata/addetail_listingstats/showsavedadsstats?adId={id}
```

## Performance Benchmarks

| Operation | 2 zips × 11 types | Rate |
|-----------|-------------------|------|
| Search extraction | ~10 sec | ~350/sec |
| Engagement scraper | ~32 sec | ~111/sec |
| **Total** | **~42 sec** | 3,497 listings |

### Scaling Estimate (National)

- 53 zips × 11 types: ~10-20 minutes total

## Dependencies

```bash
pip install aiohttp playwright requests
playwright install chromium
```

| Package | Purpose |
|---------|---------|
| aiohttp | Async HTTP for fast bulk extraction |
| playwright | Browser automation for cookie refresh |
| requests | Sync HTTP for detail page scraping |

## Key Findings

1. **Premium tier is dominant** - Paid placement overrides all other ranking factors
2. **Premium has TWO sub-tiers** - Tier A (rel 520-560) vs Tier B (rel 465-468)
3. **Within premium, quality doesn't matter** - Photos, price, age have ZERO correlation
4. **Model year matters** - 2026 Standard ≈ 2025 Premium in ranking power
5. **For STANDARD listings:** Price, VIN, Photos are the key improvement factors
6. **Tier ceiling is critical** - Standard listings max out at the lowest premium position

## Documentation

- [RANKING_ALGORITHM.md](docs/RANKING_ALGORITHM.md) - Complete ranking formula
- [MERCH_SCORE.md](docs/MERCH_SCORE.md) - Merchandising score components

## License

Internal use only - Thor Industries
