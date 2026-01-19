# RVTrader Competitive Intelligence Platform

A comprehensive data extraction and analysis toolkit for monitoring RV listing performance on RVTrader.com, designed to help **Thor Industries brands** (Jayco, Airstream, Thor Motor Coach, Keystone, Heartland, Tiffin, Entegra Coach, Cruiser RV, Dutchmen RV) improve their search rankings and optimize listing quality.

## Overview

This platform provides:
- **Data Collection** - Automated extraction of listing data, engagement metrics, and detail page content
- **Ranking Analysis** - Understanding of RVTrader's search ranking algorithm
- **Competitive Benchmarking** - Thor vs competitor performance comparison
- **Actionable Reports** - Dealer scorecards, manufacturer reports, and weekly tracking

## Quick Start

```bash
# 1. Install dependencies
pip install aiohttp playwright requests
playwright install chromium

# 2. Extract search rankings (fast, no auth needed)
python src/complete/rank_listings.py --zip 60616

# 3. Generate Thor brand analysis
python src/complete/thor_brand_analysis_v2.py

# 4. Generate dealer scorecards (HTML reports)
python src/complete/dealer_scorecard.py

# 5. Generate manufacturer regional reports
python src/complete/regional_summary.py
```

## Architecture

```
rv_trader/
├── src/complete/              # Production scripts
│   ├── rank_listings.py       # Search results extraction (62 fields)
│   ├── description_scraper.py # Detail page content extraction
│   ├── engagement_scraper.py  # Views/saves API scraper
│   ├── thor_brand_analysis_v2.py  # Comprehensive analysis engine
│   ├── dealer_scorecard.py    # HTML scorecard generator
│   ├── regional_summary.py    # Manufacturer + region reports
│   └── weekly_tracker.py      # Week-over-week tracking
├── docs/                      # Technical documentation
│   ├── RANKING_ALGORITHM.md   # Complete ranking formula
│   └── MERCH_SCORE.md         # Merchandising score analysis
├── output/                    # Generated data and reports
│   ├── reports/               # HTML/text reports
│   ├── scorecards/            # Dealer HTML scorecards
│   └── history/               # Weekly tracking data
└── zip_codes.txt              # Target markets (one per line)
```

## Data Collection Scripts

### rank_listings.py

Fast bulk extraction of search results using async HTTP. Extracts 62 fields per listing including ranking signals, pricing, photos, dealer info, and quality scores.

```bash
python src/complete/rank_listings.py                     # All zips in zip_codes.txt
python src/complete/rank_listings.py --zip 60616         # Single zip code
python src/complete/rank_listings.py --type "Class B"    # Single RV type
python src/complete/rank_listings.py --condition U       # Used inventory (default: New)
python src/complete/rank_listings.py --radius 100        # Custom radius (default: 50mi)
```

**Key Features:**
- 50 concurrent async requests (~5 seconds per zip code)
- Auto price-chunking for markets with >360 listings
- Outputs CSV and JSON to `output/ranked_listings_{timestamp}.*`

**Fields Extracted:**
| Category | Fields |
|----------|--------|
| Ranking | rank, relevance_score, merch_score, ad_listing_position |
| Premium | is_premium, is_top_premium, badge_status, scheme_code |
| Vehicle | year, make, model, trim, class, condition, length, mileage |
| Pricing | price, msrp, rebate, price_drop_date |
| Quality | photo_count, floorplan_id, vin, description (truncated) |
| Dealer | dealer_name, dealer_group, dealer_phone, dealer_website |
| Location | city, state, zip_code, latitude, longitude |

### description_scraper.py

Extracts full descriptions and vehicle specs from individual listing detail pages.

```bash
python src/complete/description_scraper.py               # All listings from latest extraction
python src/complete/description_scraper.py --limit 50    # Limit to 50 listings
python src/complete/description_scraper.py --delay 0.5   # Custom delay between requests
```

**Requires:** Cookies from `.cookie_cache.json` (run `engagement_scraper.py --refresh-cookies` first)

**Extracts:**
- Full description text (HTML stripped, typically 1000-3000+ characters)
- Vehicle specs: sleepingCapacity, slideouts, waterCapacity, fuelType, length, etc.

### engagement_scraper.py

Fetches view and save counts from RVTrader's internal APIs.

```bash
python src/complete/engagement_scraper.py                    # Uses cached cookies
python src/complete/engagement_scraper.py --limit 20         # Limit listings
python src/complete/engagement_scraper.py --refresh-cookies  # Force cookie refresh
```

**Cookie Management:**
- Cookies cached in `.cookie_cache.json` with 48-hour expiry
- Auto-refresh via Playwright browser when expired
- Browser opens, user browses RVTrader, navigates to `rvtrader.com/done` to complete

## Analysis & Reporting

### thor_brand_analysis_v2.py

Comprehensive Thor brand analysis with tier-constrained ranking improvements and per-manufacturer reports.

```bash
python src/complete/thor_brand_analysis_v2.py               # Analyze latest data
python src/complete/thor_brand_analysis_v2.py -i data.csv   # Specific input file
python src/complete/thor_brand_analysis_v2.py --print-report # Print to stdout
```

**Outputs:**
| File | Description |
|------|-------------|
| `thor_actions_{timestamp}.csv` | 70-column CSV with all listing data and actions |
| `thor_report_v2_{timestamp}.txt` | Executive summary report |
| `manufacturer_report_{brand}_{timestamp}.txt` | Per-brand reports for manufacturers |

**Key Features:**
- **Tier Ceiling Constraint:** Standard listings can't outrank premium without purchasing premium
- **Correlation-Weighted Priority:** Actions prioritized by actual rank correlation strength
- **Outperforming Detection:** Identifies listings beating their tier ceiling
- **Dealer-Level Breakdown:** Performance vs market average

### dealer_scorecard.py

Generates beautiful HTML scorecards for each Thor dealer with comprehensive benchmarking.

```bash
python src/complete/dealer_scorecard.py                    # All dealers
python src/complete/dealer_scorecard.py --brand Jayco      # Filter by brand
python src/complete/dealer_scorecard.py --dealer "Name"    # Single dealer
```

**Scorecard Includes:**
- Overall grade (A-F) based on quality metrics
- Benchmark comparisons vs market average
- Progress bars for data completeness
- Quick quality checks (price, VIN, photos, floorplan)
- Listing age distribution
- Top improvement opportunities
- Full listing table with status indicators

### regional_summary.py

Generates hierarchical reports organized by manufacturer and US region.

```bash
python src/complete/regional_summary.py                    # All brands, all regions
python src/complete/regional_summary.py --brand Jayco      # Single manufacturer
python src/complete/regional_summary.py --region Midwest   # Single region
```

**Report Hierarchy:**
```
Manufacturer (Jayco, Keystone, etc.)
└── Region (Midwest, Southeast, etc.)
    └── Dealer
        └── Individual Listings
```

### weekly_tracker.py

Tracks listing changes over time for week-over-week performance analysis.

```bash
python src/complete/weekly_tracker.py                      # Update history + generate report
python src/complete/weekly_tracker.py --report             # Report only (no data update)
python src/complete/weekly_tracker.py --brand Jayco        # Filter by brand
```

**Tracks:**
- Rank changes (improved/declined/unchanged)
- Quality score changes
- Actions completed (added price, VIN, photos, etc.)
- New listings / Sold listings

**Storage:** JSON history file in `output/history/listing_history.json` (keeps 52 weeks)

### dealer_premium_audit.py (Monthly)

Detects which dealers have Premium Tier A vs Tier B placement. Run monthly to maintain a reference file.

```bash
python src/complete/dealer_premium_audit.py                # Default: 60616, all RV types
python src/complete/dealer_premium_audit.py --zip 90210    # Different market
```

**Output:** `output/dealer_premium_tiers.csv` - Reference file for other scripts

**Status:** ⚠️ NEEDS DEBUG - API returning 0 results (URL encoding issue suspected)

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

### Key Finding: Premium Sub-Tiers (2026-01-18)

Analysis revealed that **premium listings cluster into TWO distinct groups** based on relevance score:

| Sub-Tier | Relevance Score | Evidence |
|----------|-----------------|----------|
| **Tier A** | 520-560 | Higher-paying premium package |
| **Tier B** | 465-468 | Basic premium package |

**Within premium, listing quality has ZERO correlation with rank:**
- Price correlation: 0.000
- Photo correlation: 0.008
- The ONLY factor is relevance score (r = -0.913)

**Critical Insight:** A Tier B premium listing cannot outrank a Tier A listing regardless of photos, price, or other quality factors. To improve, dealers must upgrade their premium package.

### Ranking Factors (Correlation Strength)

| Factor | Rank Correlation | Relevance Points | Merch Points |
|--------|------------------|------------------|--------------|
| has_price | **-0.840** | +194 | +5 |
| has_vin | **-0.689** | +165 | +6 |
| photo_count (35+) | **-0.611** | +195 | +30 |
| has_floorplan | **-0.300** | +50 | +12 |
| has_length | **-0.125** | +0 | +8 |

*Negative correlation = higher value = better (lower) rank number*

### Improvement Calculation

```
~15 relevance points ≈ 1 rank position improvement

Example: Listing at rank 40 missing price and VIN
- Add price:  +194 points → ~13 positions
- Add VIN:    +165 points → ~11 positions
- Total:      ~24 positions → New rank ~16

But if tier ceiling is 16, improvement stops there.
```

## Thor Industries Brands

The platform tracks these Thor Industries brands:

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

## Configuration

### zip_codes.txt

List of zip codes to analyze (one per line):

```
60616
33139
90210
```

### Cookie Cache

Cookies are stored in `src/.cookie_cache.json`:

```json
{
  "timestamp": "2026-01-18T10:00:00",
  "cookie_string": "datadome=...; other=..."
}
```

Expires after 48 hours. Refresh with:
```bash
python src/complete/engagement_scraper.py --refresh-cookies
```

## API Reference

### Search API

```
GET https://www.rvtrader.com/ssr-api/search-results
    ?type={Type}|{TypeCode}
    &page={N}
    &zip={Zip}
    &radius={Miles}
    &condition={N|U}
    &price={Min}:{Max}
```

- 36 results per page, max 10 pages (360 cap)
- No authentication required

### Engagement APIs (require cookies)

```
# Views
GET /gettiledata/addetail_listingstats/showadviewsstats?adId={id}
Response: {"error":null,"listingViewsData":"138"}

# Saves
GET /gettiledata/addetail_listingstats/showsavedadsstats?adId={id}
Response: {"error":null,"listingSavesData":1}
```

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

## Output Files

| File Pattern | Script | Description |
|--------------|--------|-------------|
| `ranked_listings_{ts}.csv/json` | rank_listings.py | Raw search data |
| `detail_data_{ts}.json` | description_scraper.py | Full descriptions + specs |
| `engagement_stats_{ts}.json` | engagement_scraper.py | Views and saves |
| `thor_actions_{ts}.csv` | thor_brand_analysis_v2.py | Analysis with actions |
| `thor_report_v2_{ts}.txt` | thor_brand_analysis_v2.py | Summary report |
| `manufacturer_report_{brand}_{ts}.txt` | thor_brand_analysis_v2.py | Per-brand reports |
| `scorecard_{dealer}_{ts}.html` | dealer_scorecard.py | Dealer HTML scorecards |
| `index_{ts}.html` | dealer_scorecard.py | Scorecard dashboard |
| `{Brand}_regional_{ts}.html` | regional_summary.py | Regional HTML reports |
| `wow_report_{ts}.html` | weekly_tracker.py | Week-over-week report |
| `dealer_premium_tiers.csv` | dealer_premium_audit.py | Monthly dealer tier reference |

## Typical Workflow

1. **Weekly Data Collection**
   ```bash
   python src/complete/rank_listings.py
   ```

2. **Update Weekly Tracking**
   ```bash
   python src/complete/weekly_tracker.py
   ```

3. **Generate Analysis**
   ```bash
   python src/complete/thor_brand_analysis_v2.py
   python src/complete/dealer_scorecard.py
   python src/complete/regional_summary.py
   ```

4. **Optional: Enrich with Detail Data**
   ```bash
   python src/complete/engagement_scraper.py --refresh-cookies  # if needed
   python src/complete/description_scraper.py --limit 100
   python src/complete/engagement_scraper.py --limit 100
   ```

## Key Findings

1. **Premium tier is dominant** - Paid placement overrides all other ranking factors
2. **Premium has TWO sub-tiers** - Tier A (rel 520-560) vs Tier B (rel 465-468)
3. **Within premium, quality doesn't matter** - Photos, price, age have ZERO correlation
4. **Distance is NOT a factor** - Premium at 47mi beats standard at 5mi
5. **For STANDARD listings only:** Price (r=-0.840), VIN (r=-0.689), Photos (r=-0.611) matter
6. **Tier ceiling is critical** - Standard listings max out at the lowest premium position
7. **Same dealer can have both tiers** - General RV has Tier A and Tier B listings

## Documentation

- [RANKING_ALGORITHM.md](docs/RANKING_ALGORITHM.md) - Complete ranking formula with correlation matrix
- [MERCH_SCORE.md](docs/MERCH_SCORE.md) - Deep dive on merchandising score components

## License

Internal use only - Thor Industries
