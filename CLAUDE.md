# RVTrader Scraper

## Project Goal
Extract RV listing data from RVTrader.com to help **Thor Industries brands** (Thor Motor Coach, Jayco, Airstream, Tiffin, Entegra Coach, Heartland, Keystone, Cruiser, Dutchmen) improve their listing rankings.

## Quick Start
```bash
# RECOMMENDED: Interactive Dashboard (3 steps)
# 1. Extract search rankings
python src/complete/rank_listings.py --zip 60616 --type "Class B"

# 2. Fetch engagement data (views/saves)
python src/complete/engagement_scraper.py

# 3. Consolidate and view dashboard
python src/complete/consolidate_data.py
# Open output/reports/rv_dashboard.html in browser

# ─────────────────────────────────────────────────────────────
# ALTERNATIVE: Full workflow with all reports
# ─────────────────────────────────────────────────────────────

# 1. Extract search rankings (single zip)
python src/complete/rank_listings.py --zip 60616 --type "Class B"

# 1b. OR extract NATIONAL coverage (53 zips @ 100mi - RV buyer markets)
python src/complete/rank_listings.py --zip-file zip_codes_national.txt --radius 100 --type "Class A"

# 2. Fetch engagement data (views/saves) - ~2 sec for 60 listings
python src/complete/engagement_scraper.py

# 3. Generate interactive dashboard (NEW - with filtering/sorting)
python src/complete/consolidate_data.py
# Open: output/reports/rv_dashboard.html

# 4. Update weekly tracking
python src/complete/weekly_tracker.py

# 5. Generate Thor analysis
python src/complete/thor_brand_analysis_v2.py

# 6. Generate dealer scorecards
python src/complete/dealer_scorecard.py

# 7. Generate regional reports
python src/complete/regional_summary.py

# 8. Generate static HTML report (legacy)
python src/complete/thor_report_html.py

# 9. Export flat file for data warehouse/BI (77 columns)
python src/complete/export_flat_file.py
python src/complete/export_flat_file.py --append  # Also update master historical file
```

## Project Structure
```
rv_trader_2/
├── CLAUDE.md                    # THIS FILE - Project context
├── README.md                    # Comprehensive documentation
├── zip_codes.txt                # Custom zip codes (one per line)
├── zip_codes_national.txt       # 53 zips targeting RV buyer markets @ 100mi
├── src/
│   └── complete/                # Production scripts
│       ├── rank_listings.py           # Search results extraction (62 fields)
│       ├── thor_brand_analysis_v2.py  # Comprehensive analysis with tier ceilings
│       ├── dealer_scorecard.py        # HTML dealer scorecards
│       ├── regional_summary.py        # Manufacturer + region reports
│       ├── weekly_tracker.py          # Week-over-week tracking
│       ├── dealer_premium_audit.py    # Monthly premium tier detection
│       ├── thor_report_html.py        # Interactive HTML report with image preview
│       ├── consolidate_data.py        # NEW: Merge data for dashboard
│       ├── spec_scraper.py            # Detail page spec extraction (Playwright)
│       ├── engagement_scraper.py      # Views/saves extraction
│       ├── export_flat_file.py        # Flat CSV export for data warehouse/BI
│       └── description_scraper.py     # Full descriptions from detail pages
├── output/
│   ├── ranked_listings_*.csv/json     # Raw extraction data
│   ├── engagement_stats_*.json        # Engagement data (views/saves)
│   ├── thor_actions_*.csv             # Analysis with actions
│   ├── thor_report_v2_*.txt           # Summary report
│   ├── manufacturer_report_*.txt      # Per-brand reports
│   ├── dealer_premium_tiers.csv       # Dealer tier reference (monthly)
│   ├── rvtrader_export_*.csv          # Flat file export (77 columns)
│   ├── rvtrader_export_master.csv     # Historical master file (all exports)
│   ├── reports/
│   │   ├── rv_dashboard.html          # NEW: Interactive dashboard with filters
│   │   ├── rv_data.json               # NEW: Consolidated data for dashboard
│   │   ├── thor_interactive_*.html    # Interactive HTML reports (legacy)
│   │   └── {Brand}_regional_*.html    # Per-manufacturer regional reports
│   ├── scorecards/                    # Dealer HTML scorecards
│   └── history/                       # Weekly tracking data
└── docs/
    ├── RANKING_ALGORITHM.md           # Complete ranking formula
    └── MERCH_SCORE.md                 # Merch score components
```

---

## Current Status (2026-01-19)

### Scripts Complete
| Script | Purpose | Status |
|--------|---------|--------|
| `rank_listings.py` | Search results extraction (64 fields) | ✅ UPDATED |
| `consolidate_data.py` | Merge data sources into unified JSON for dashboard | ✅ NEW |
| `thor_brand_analysis_v2.py` | Comprehensive analysis with tier ceilings | ✅ COMPLETE |
| `dealer_scorecard.py` | HTML scorecards with grades A-F | ✅ COMPLETE |
| `regional_summary.py` | Manufacturer + region HTML reports with dealer cards | ✅ UPDATED |
| `weekly_tracker.py` | Week-over-week tracking | ✅ COMPLETE |
| `engagement_scraper.py` | Views/saves API extraction (30 concurrent) | ✅ COMPLETE |
| `description_scraper.py` | Full descriptions from detail pages | ✅ COMPLETE |
| `thor_report_html.py` | Interactive HTML report with Competitive Position | ✅ LEGACY |
| `spec_scraper.py` | Detail page spec extraction (Playwright) | ⚠️ TIMEOUT ISSUES |
| `dealer_premium_audit.py` | Premium tier detection from rank data | ✅ COMPLETE |
| `export_flat_file.py` | Flat CSV export for data warehouse/BI (77 cols) | ✅ COMPLETE |

### Interactive Dashboard (NEW - 2026-01-19)

The unified dashboard (`rv_dashboard.html`) replaces the static HTML reports with a client-side interactive experience:

| Feature | Description |
|---------|-------------|
| **Data Loading** | Loads `rv_data.json` via fetch() - no server required |
| **Filter: Brand** | Dropdown to filter by any make (Jayco, Thor, Winnebago, etc.) |
| **Filter: Tier** | Top Premium / Premium / Standard checkboxes |
| **Filter: Year** | Dropdown for model year (2026, 2025, older) |
| **Filter: Position** | Competitive position (Dominant, Strong, Competitive, etc.) |
| **Filter: Search Zip** | Filter by query zip code (for multi-zip searches) |
| **Filter: Region** | Geographic region (Midwest, Southeast, Southwest, etc.) |
| **Filter: Dealer Search** | Text search for dealer name |
| **Filter: Thor Only** | Toggle to show only Thor Industries brands |
| **Location Column** | Shows City, State for each listing |
| **Days Color Coding** | Green (<30), Yellow (30-90), Red (>90 days) |
| **Click to Open** | Click any row to open listing on RVTrader |
| **Sortable Table** | Click any column header to sort asc/desc |
| **Image Preview** | Hover over any row to see the RV's main image |
| **Live Stats** | Summary cards update when filters change |
| **Export CSV** | Export filtered data to CSV file |

```bash
# Generate dashboard
python src/complete/consolidate_data.py

# View in browser (requires local server for fetch to work)
cd output/reports
python -m http.server 8080
# Open: http://localhost:8080/rv_dashboard.html
```

**Architecture:**
```
rank_listings.py → ranked_listings_*.json
engagement_scraper.py → engagement_stats_*.json
         ↓
    consolidate_data.py
         ↓
    rv_data.json (single consolidated file)
         ↓
    rv_dashboard.html (loads via fetch)
```

### Legacy: Interactive HTML Report (thor_report_html.py)

`thor_report_html.py` generates an interactive HTML report with:

| Feature | Description |
|---------|-------------|
| **Competitive Position** | Combines year + tier into actionable positions (Dominant/Strong/Competitive/Neutral/At Risk/Disadvantaged) |
| **Tier Column** | Shows TP (Top Premium), P (Premium), or S (Standard) |
| **Year-Aware Actions** | Recommendations factor in model year penalty |
| **Search Metadata** | Shows zip code, RV type, and radius in header |
| **Length & Mileage** | Shows available specs from search API |
| **Views & Saves** | Engagement metrics from RVTrader (requires running engagement_scraper.py first) |
| **Days Listed** | Shows how long each listing has been posted |
| **Price Drop Date** | Shows when last price reduction occurred |
| **Image Preview** | Hover over any row to see the RV's main image |
| **Hyperlinked Listings** | Click model name to open on RVTrader |
| **Color-Coded Status** | Green/Yellow/Red indicators for photos, views, age |
| **Summary Stats** | Top Premium/Premium/Standard counts + Year breakdown (2026/2025/Older) |

```bash
# Generate interactive report (run engagement_scraper.py first for views/saves)
python src/complete/engagement_scraper.py  # ~2 sec for 60 listings
python src/complete/thor_report_html.py

# Output: output/reports/thor_interactive_YYYYMMDD_HHMMSS.html
```

### New Feature: Flat File Export (Updated 2026-01-19)

`export_flat_file.py` generates a consolidated 77-column CSV suitable for data warehouse/BI loading:

| Category | Columns |
|----------|---------|
| **Metadata** | run_id, extraction_timestamp, source files, version |
| **Search Context** | zip, type, radius, condition, price range |
| **Identifiers** | listing_id, dealer_id, stock_number, vin |
| **Vehicle** | year, make, model, trim, class, condition, length, mileage |
| **Pricing** | price, msrp, rebate, price_vs_msrp_pct |
| **Location** | city, state, zip_code, region (computed), lat/lon, distance |
| **Dealer** | name, group, phone, website, seller_type |
| **Ranking** | rank, relevance_score, merch_score |
| **Premium Status** | is_premium, is_top_premium, badge_status |
| **Quality** | photo_count, has_floorplan, has_price, has_vin, has_length |
| **Engagement** | views, saves (from engagement_scraper) |
| **Dates** | create_date, days_listed, price_drop_date |
| **Tier Analysis** | tier, tier_ceiling, is_controllable, outperforming_tier |
| **Thor Brand** | is_thor_brand, thor_brand_name, thor_parent_company |
| **Improvements** | estimated_merch, relevance/merch available, realistic improvement |

```bash
# Basic export (latest single file only)
python src/complete/export_flat_file.py

# COMBINE ALL TYPE SEARCHES into one file (last 24 hours)
python src/complete/export_flat_file.py --combine-session

# Combine with custom time window
python src/complete/export_flat_file.py --combine-session --hours 48

# Combine and append to master historical file
python src/complete/export_flat_file.py --combine-session --append

# Append single file to master (legacy behavior)
python src/complete/export_flat_file.py --append

# Output: output/rvtrader_export_{zip}_{N}types_{timestamp}.csv
# Master: output/rvtrader_export_master.csv
```

**Note:** `--combine-session` calculates tier ceilings **per search type** since rankings don't cross types. Each row preserves its `search_type` column for filtering in BI tools.

### Regional Summary Reports (Updated 2026-01-19)

`regional_summary.py` generates per-manufacturer HTML reports with:

**Header Summary Cards (vs Competitors):**
- Total Listings, Avg Rank, Avg Views/Unit, Avg Saves/Unit, Avg Photos
- Premium %, Quality Score - all with +/- comparison vs non-Thor competitors
- Competitive position breakdown (Strong/Dominant, Competitive/Neutral, At Risk)

**Dealer Cards (vs Brand Average):**
Each dealer shown as a card with metrics compared to brand average:
- Units, Rank (+/-), Quality (+/-), Views/unit (+/-), Saves/unit (+/-), Photos (+/-), Premium % (+/-)
- Color-coded: green = better than avg, red = worse than avg

**Listing Table Columns:**
Rank, Year, Model (hyperlinked), Price, VIN (Y/N), Pics, Floorplan (Y/N), Length, Views, Saves, Merch, Days Listed, Price Drop, Tier (TP/P/S), Position, Actions

```bash
python src/complete/regional_summary.py
# Output: output/reports/{Brand}_regional_{timestamp}.html
```

### Spec Data Availability

**Search API only provides 2 spec fields:**
- `length` - Vehicle length in feet
- `mileage` - Odometer reading

**NOT available from search API** (would require detail page scraping):
- sleepingCapacity, slideouts, fuelType
- freshWaterCapacity, grayWaterCapacity, blackWaterCapacity
- grossVehicleWeight, dryWeight, hitchWeight
- numAirConditioners, awnings, levelingJacks

A `spec_scraper.py` was created to extract full specs from detail pages using Playwright, but currently experiences timeout issues connecting to RVTrader.

### Recent Fixes (2026-01-18)

**1. `rank_listings.py`** - Added `search_radius` and `search_condition` columns:
- Now captures all search parameters in output CSV (64 fields total)
- Fields flow through to `export_flat_file.py` for complete data lineage

**2. `thor_brand_analysis_v2.py`** - Fixed None merch_score format error (lines 814, 842):
```python
merch = listing.get('merch_score') or 0
```

**3. `dealer_premium_audit.py`** - Complete rewrite with comparable-pairs algorithm:
- **Old approach**: Called API directly (returned 0 results due to session issues)
- **New approach**: Compares IDENTICAL listings (same make/model/year) across dealers
- Algorithm: Dealer with higher relevance for same-spec unit = Tier A
- Win rate >= 70% with 5+ comparisons = confirmed Tier A
- Win rate <= 30% with 5+ comparisons = confirmed Tier B
- Outputs: `dealer_premium_tiers.csv`, `comparable_pairs_*.csv` (evidence)

**Key Finding (2026-01-18):**
- Same Jayco Precept 34G: Rick's RV (rel=467) vs Pete's RV (rel=267) → **200 point gap!**
- Same Thor ARIA: General RV (rel=465) vs Campers Inn (rel=267) → **198 point gap!**
- This ~200 point gap for identical listings proves premium tier difference

---

## KEY FINDING: Premium Sub-Tiers

### Discovery (2026-01-18)
Analysis revealed that premium listings cluster into TWO distinct groups:

| Tier | Relevance Score | Typical Ranks | Description |
|------|-----------------|---------------|-------------|
| **Premium Tier A** | 520-560 | 1-6 | Higher premium package |
| **Premium Tier B** | 465-468 | 19-42 | Basic premium package |

### Evidence
Same dealer (General RV Center - Huntley IL) has listings in BOTH tiers:
- Tier A: Coachmen NOVA (Rank 1, rel=557), Thor SCOPE (Rank 4, rel=524)
- Tier B: Thor SANCTUARY (Rank 41, rel=465), Entegra LAUNCH (Rank 42, rel=465)

### Key Insight
**Within premium tier, listing quality (photos, floorplan, etc.) has ZERO correlation with rank.**
- Price correlation: 0.000
- Photo correlation: 0.008
- Age correlation: -0.103
- **Relevance score correlation: -0.913** (THE ONLY FACTOR)

### Implications
1. Optimizing photos/floorplan won't help a Tier B listing beat a Tier A listing
2. To improve from Tier B to Tier A, dealer must upgrade their premium package
3. The `dealer_premium_audit.py` script (once debugged) will identify which dealers have which tier

---

## KEY FINDING: Model Year Impact (2026-01-19)

### Discovery
Model year has a **massive impact** on ranking - approximately **+24 relevance points per year newer**.

### Evidence: Ben Davis TRAVATO 59K
Same dealer, same photo count, same VIN status, different model years:

| Year | Rank | Relevance | Merch | Net (Rel-Merch) |
|------|------|-----------|-------|-----------------|
| 2026 | 6 | 511.6 | 293.3 | 218.3 |
| 2025 | 138 | 453.3 | 286.2 | 167.1 |
| **Difference** | **132 ranks** | **+58.3 pts** | +7.1 | **+51.3 pts** |

After controlling for merch score differences, the pure year impact is **~51 points** for one year.

### Key Insight
**2026 Standard ≈ 2025 Premium**

The year bonus (~24-51 pts) roughly equals the premium tier boost (~20-60 pts), meaning:
- A 2026 Standard listing can outrank a 2025 Premium listing
- Example: Winnebago Rangeline RGN - 2026 Standard (Rank 53) beat 2025 Premium (Rank 63) at same dealer

### Competitive Positions
The HTML report now shows competitive position combining year + tier:

| Position | Criteria | Description |
|----------|----------|-------------|
| **Dominant** | Top Premium + 2026 | Best possible position |
| **Strong** | Premium + 2026 OR Top Premium + 2025 | Well-positioned |
| **Competitive** | Standard + 2026 | Current year cancels tier disadvantage |
| **Neutral** | Premium + 2025 | Year penalty cancels premium boost |
| **At Risk** | Standard + 2025 | One year old, no premium |
| **Disadvantaged** | 2+ years old OR Standard + old | Needs upgrade or clearance |

### Implications
1. **Prioritize current model year inventory** - Year matters as much as premium tier
2. **Top Premium needed for dominance** - Regular Premium + current year = Strong, not Dominant
3. **Clear older inventory quickly** - Each year adds ~24 pt penalty
4. **Year-aware action recommendations** - Report now suggests Top Premium for older units

---

## Ranking Algorithm

### The Formula
```
FINAL_RANK = SORT_BY(
    1. TIER           [top_premium > premium > standard]
    2. PREMIUM_LEVEL  [Tier A > Tier B within premium]  <-- NEW FINDING
    3. relevance_score [within tier/level]
    4. AGE_PENALTY    [older listings demoted]
)
```

### Tier System
| Tier | Positions | Requirement |
|------|-----------|-------------|
| Top Premium | 1-3 | Paid ($$$$) |
| Premium Tier A | 4-10 | Paid ($$$) - higher package |
| Premium Tier B | 11-42 | Paid ($$) - basic package |
| Standard | 43+ | Free |

### Ranking Factors (for STANDARD tier only)
These factors matter for standard listings but NOT for premium:

| Factor | Relevance Pts | Rank Correlation |
|--------|---------------|------------------|
| has_price | +194 | -0.840 (strong) |
| has_vin | +165 | -0.689 (strong) |
| 35+ photos | +195 | -0.611 (moderate) |
| has_floorplan | +50 | -0.300 (weak) |

**~15 relevance points ≈ 1 rank position**

---

## National Coverage (53 Zip Codes @ 100mi)

Use `zip_codes_national.txt` for comprehensive US RV market coverage.

**Focus areas:** RV manufacturing corridor, retirement/snowbird destinations, camping areas, suburban markets
**Avoids:** Dense urban cores (NYC, Boston, SF) where RV ownership is minimal

```bash
# Extract national data for a single RV type
python src/complete/rank_listings.py --zip-file zip_codes_national.txt --radius 100 --type "Class A"

# Extract all types nationally (will take longer)
python src/complete/rank_listings.py --zip-file zip_codes_national.txt --radius 100
```

### Coverage Map

| Region | Zips | Key Markets |
|--------|------|-------------|
| **Midwest Manufacturing** | 7 | Elkhart IN (RV Capital), Fort Wayne, Toledo, Grand Rapids, Peoria |
| **Florida** | 7 | Ocala, Fort Myers, Lakeland, Daytona, Pensacola, Bradenton, Sanford |
| **Texas** | 7 | Fort Worth, Katy, McKinney, Schertz, Abilene, Del Rio, Killeen |
| **Arizona (Snowbird)** | 5 | Mesa, Yuma, Flagstaff, Sierra Vista, Kingman |
| **California (Inland)** | 5 | Temecula, Bakersfield, Fresno, Redding, Folsom |
| **Pacific NW & Mountain** | 5 | Spokane, Boise, Medford, Sumner, Billings |
| **Mountain West & Plains** | 5 | Aurora CO, Colorado Springs, Provo, Cheyenne, Rapid City |
| **Southeast Camping** | 5 | Myrtle Beach, Pigeon Forge, Huntsville, Dahlonega, Hendersonville |
| **Mid-South & Ozarks** | 4 | Branson, Fayetteville AR, Franklin TN, Gulfport |
| **Midwest Recreation** | 3 | Wisconsin Dells, Brainerd MN, Traverse City |

### Zip File Format
```
# Comments start with #
46514,Elkhart IN - RV Capital of the World
85201,Mesa AZ - Massive RV retirement
```

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

## TODO: Next Steps

### Completed (2026-01-19)
- ✅ Interactive HTML report with image preview on hover (`thor_report_html.py`)
- ✅ Length and Mileage columns (only specs available from search API)
- ✅ Age info (days listed, last price drop)
- ✅ Properly aligned tables with hyperlinked listings
- ✅ Search metadata (zip, type, radius) in report header
- ✅ **Views & Saves columns** - engagement_scraper.py (30 concurrent, ~2s for 60 listings) merged into HTML report
- ✅ **Flat file export** - `export_flat_file.py` (77 columns, master file append, engagement merge)
- ✅ **Competitive Position** - Combines year + tier into actionable positions (Dominant/Strong/Competitive/etc.)
- ✅ **Year Impact Analysis** - Discovered ~24 pts/year impact; "2026 Standard = 2025 Premium"
- ✅ **Tier Column** - Shows TP/P/S in interactive report
- ✅ **Year-Aware Actions** - Recommendations factor in model year penalty
- ✅ **Combined session export** - `--combine-session` merges all type searches into one file for BI
- ✅ **National zip coverage** - 53 zips @ 100mi targeting actual RV buyer markets (`zip_codes_national.txt`)
- ✅ **Regional summary UI overhaul** - Dealer cards with all metrics vs brand average comparisons
- ✅ **Unified Dashboard** - Single `rv_dashboard.html` with client-side filtering, sorting, search
- ✅ **Consolidated Data** - `consolidate_data.py` merges ranked listings + engagement into `rv_data.json`
- ✅ **Filter/sort functionality** - Brand, tier, year, position, region filters + sortable columns
- ✅ **Search Zip Filter** - Filter by query zip for multi-market analysis
- ✅ **Location Column** - City, State shown for each listing
- ✅ **Days Color Coding** - Visual indicator for listing age (green/yellow/red)
- ✅ **Click-to-Open Rows** - Click any row to open listing on RVTrader

### High Priority
1. **Fix spec_scraper.py** - Debug Playwright timeouts to get full specs from detail pages
2. **Multi-zip consolidation** - Enhance consolidate_data.py to merge multiple search results

### Medium Priority
1. Historical trend charts (line graphs over weeks)
2. Dealer group analysis (same group, different locations)

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
- Cookies cached in `.cookie_cache.json` (48h expiry)
- Refresh: `python src/complete/engagement_scraper.py --refresh-cookies`
- **NOTE:** Requires `datadome` cookie which is IP-bound (generated by JavaScript)

---

## ScraperAPI Integration

**API Key:** `ef66e965591986214ea474407eb0adc8`
**Account:** 1.2M+ credits remaining, 100 concurrent limit

### Compatibility

| Script | ScraperAPI | Flag | Notes |
|--------|------------|------|-------|
| `rank_listings.py` | ✅ Works | `--use-proxy` | Search API doesn't need cookies |
| `engagement_scraper.py` | ❌ No | N/A | Needs datadome cookie (IP-bound) |

### Usage
```bash
# Search with IP rotation (for large national extractions)
python src/complete/rank_listings.py --zip 60616 --type "Class B" --radius 50 --use-proxy

# Engagement - direct only (proxy breaks cookie auth)
python src/complete/engagement_scraper.py
```

### Why Engagement Can't Use ScraperAPI
1. Engagement API requires `datadome` cookie (bot detection)
2. This cookie is generated by JavaScript and tied to your IP
3. ScraperAPI rotates IPs, invalidating the cookie
4. ScraperAPI's `render=true` (JS execution) times out on RVTrader
5. ScraperAPI's proxy mode also times out

### If You Get Blocked on Engagement
Use a VPN with static/dedicated IP:
1. Connect to VPN
2. Run `python engagement_scraper.py --refresh-cookies` (generates cookies for VPN IP)
3. Run `python engagement_scraper.py` (uses same VPN IP)
