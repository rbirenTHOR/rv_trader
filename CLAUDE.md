# RVTrader Scraper

## Project Goal
Extract RV listing data from RVTrader.com to help **Thor Industries brands** (Thor Motor Coach, Jayco, Airstream, Tiffin, Entegra Coach) improve their listing rankings.

## Quick Start
```bash
# 1. Get search rankings (fast, no cookies needed)
python src/complete/rank_listings.py --zip 60616

# 2. Generate visual dealer scorecards (SHAREABLE HTML!)
python src/complete/dealer_scorecard.py

# 3. Generate Thor brand analysis v2 (comprehensive CSV + manufacturer reports)
python src/complete/thor_brand_analysis_v2.py

# Optional: Additional data collection
# 4. Refresh cookies if needed (opens browser)
python src/complete/engagement_scraper.py --refresh-cookies

# 5. Get full descriptions from detail pages
python src/complete/description_scraper.py --limit 50

# 6. Get engagement stats (views/saves)
python src/complete/engagement_scraper.py --limit 50
```

## Project Structure
```
rv_trader/
├── CLAUDE.md                # THIS FILE - Project context
├── zip_codes.txt            # Zip codes to search (one per line)
├── .cookie_cache.json       # Cached cookies for scraping (gitignored)
├── src/
│   └── complete/            # Production-ready scripts
│       ├── rank_listings.py         # Bulk ranked extraction (62 fields, ~5s/zip)
│       ├── description_scraper.py   # Full description + specs extraction (~2s/listing)
│       ├── engagement_scraper.py    # Views/saves extraction (auto cookie refresh)
│       ├── thor_brand_analysis.py   # Thor brand analysis v1 (basic report)
│       ├── thor_brand_analysis_v2.py # Comprehensive analysis with tier ceilings
│       └── dealer_scorecard.py      # **NEW** Visual HTML scorecards (shareable!)
├── output/                  # Extracted data (CSV/JSON)
│   ├── scorecards/                            # **SHAREABLE** Visual dealer scorecards
│   │   ├── index_{timestamp}.html             # Summary page with all dealers
│   │   └── scorecard_{dealer}_{ts}.html       # Per-dealer visual scorecard
│   ├── thor_actions_{timestamp}.csv           # Comprehensive CSV with all actions
│   ├── thor_report_v2_{timestamp}.txt         # Summary report
│   └── manufacturer_report_{brand}_{ts}.txt   # Per-manufacturer reports
├── docs/
│   ├── RANKING_ALGORITHM.md # **IMPORTANT: Complete ranking formula**
│   ├── MERCH_SCORE.md       # **IMPORTANT: Merch score deep dive**
│   ├── PROJECT_STATUS.md    # Current status and next steps
│   ├── correlation_study.md # Original correlation analysis
│   └── CONVERSATION_HISTORY.md # Past session logs
└── samples/                 # Sample HTML files
```

---

## Current Status (2026-01-16)

### What Works
| Script | Purpose | Status |
|--------|---------|--------|
| `rank_listings.py` | Search results extraction (62 fields) | **COMPLETE** |
| `description_scraper.py` | Full description + specs from detail pages | **COMPLETE** |
| `engagement_scraper.py` | Views/saves extraction (auto cookie refresh) | **COMPLETE** |
| `thor_brand_analysis.py` | Thor brand analysis v1 (basic report) | **COMPLETE** |
| `thor_brand_analysis_v2.py` | **Comprehensive analysis with tier ceilings + manufacturer reports** | **COMPLETE** |
| `dealer_scorecard.py` | **Visual HTML scorecards for dealers - easy to share!** | **NEW** |

### What Needs Work
| Task | Status | Notes |
|------|--------|-------|
| Merge all data sources | **NOT STARTED** | Combine search + detail + engagement |
| Multi-zip analysis | **NOT STARTED** | Run analysis across multiple markets |
| Historical tracking | **NOT STARTED** | Track ranking changes over time |

### Next Priority
1. Run analysis across multiple zip codes for broader market view
2. Merge description_scraper + engagement_scraper data into analysis
3. Build historical tracking to measure improvement impact

---

## Ranking & Scoring Documentation

**For comprehensive ranking algorithm documentation, see:**

| Document | Purpose |
|----------|---------|
| `docs/RANKING_ALGORITHM.md` | **Complete ranking formula, correlation matrix, point values** |
| `docs/MERCH_SCORE.md` | **Deep dive on merchandising score components** |
| `docs/correlation_study.md` | Original correlation analysis |

### Quick Reference: Ranking Formula

```
FINAL_RANK = sort_by(
    1. TIER: top_premium > premium > standard
    2. relevance_score (within tier)
    3. AGE_PENALTY (older listings demoted)
    4. FRESHNESS_BOOST (badge_status: newly_listed)
)
```

### Quick Reference: Key Factors

| Factor | Relevance Impact | Merch Impact |
|--------|-----------------|--------------|
| **Premium placement** | Tier override | None |
| **has_price** | +194 points | +5 points |
| **has_vin** | +165 points | +6 points |
| **photo_count (35+)** | +195 points | +30 points |
| **has_floorplan** | +50 points | +12 points |
| **description_length** | Indirect | **+45 points** (2000+ chars) |

### Quick Reference: Merch Score

| Component | Correlation | Controllable? |
|-----------|-------------|---------------|
| description_length | 0.899 | Yes |
| has_length | 0.702 | Yes |
| photo_count | 0.658 | Yes |
| has_floorplan | 0.554 | Yes - **Easy Win (+12 pts)** |

---

## rank_listings.py

Fast bulk extraction using async HTTP (direct API). Extracts all listings for each RV type in a zip code with search position ranks.

### Usage
```bash
python src/complete/rank_listings.py                              # All zips in zip_codes.txt
python src/complete/rank_listings.py --zip 60616                  # Single zip
python src/complete/rank_listings.py --zip 60616 --type "Class B" # Single type
python src/complete/rank_listings.py --zip 60616 --condition U    # Used (default=New)
python src/complete/rank_listings.py --zip 60616 --radius 100     # Custom radius (default=50)
```

### Output
- `output/ranked_listings_{timestamp}.csv`
- `output/ranked_listings_{timestamp}.json`

### Fields Extracted (62 total)

**Search Context:** rank, search_zip, search_type, price_chunk_min, price_chunk_max

**Identifiers:** id, dealer_id, customer_id, vin, stock_number

**Vehicle:** year, make, make_id, model, model_group_id, model_group_name, trim, class, class_id, condition, length, mileage, description

**Pricing:** price, msrp, rebate, price_drop_date

**Location:** city, state, zip_code, latitude, longitude

**Dealer:** dealer_name, dealer_group_id, dealer_group, dealer_website, dealer_phone, dealer_phone_all, seller_type, trusted_partner

**Photos:** photo_count, photo_ids, floorplan_id

**Dates:** create_date, create_date_formatted

**Ranking:** ad_listing_position, relevance_score, merch_score

**Premium:** is_premium, is_top_premium, badge_status, scheme_code

**Features:** has_vhr, buy_now, featured_homepage, featured_search, hide_floor_plans

**Attributes:** attribs_msrp, attribs_item_url

**Dealer Features:** dealer_has_video, dealer_contact_deactivated

**URLs:** listing_url

### Technical Details
- API: `https://www.rvtrader.com/ssr-api/search-results?type={Type}|{Code}&page={N}&zip={Zip}&radius={R}&condition={N|U}`
- 36 results per page, max 10 pages (360 cap)
- Auto price chunking when >360 results ($5k increments)
- 50 concurrent requests (direct API, ~2s per zip)

---

## description_scraper.py

Extracts full descriptions and specs from detail pages. **Requires cookies from `.cookie_cache.json`.**

### Usage
```bash
python src/complete/description_scraper.py                  # All listings from latest ranked_listings
python src/complete/description_scraper.py --limit 20       # Limit to 20 listings
python src/complete/description_scraper.py --delay 0.5      # 0.5s delay between requests (default: 0.3)
```

### Output
- `output/detail_data_{timestamp}.json`

### Fields Extracted
- **description**: Full description text (HTML stripped, 1000-3000+ chars typical)
- **description_length**: Character count
- **specs**: sleepingCapacity, hasFloorplan, slideouts, waterCapacity, fuelType, length, etc.

### Technical Details
- Uses cookies from `.cookie_cache.json` (shared with engagement_scraper)
- Sequential requests (no session - sessions interfere with DataDome cookies)
- ~2s per listing (mostly network time for 400KB pages)
- NUXT_DATA extraction from page HTML

---

## engagement_scraper.py

Extracts views/saves from detail pages via API endpoints. **Cookies auto-refresh every 48 hours via browser.**

### Usage
```bash
python src/complete/engagement_scraper.py                    # Uses cached cookies (auto-refresh if >48h)
python src/complete/engagement_scraper.py --limit 10         # Limit to 10 listings
python src/complete/engagement_scraper.py --refresh-cookies  # Force cookie refresh via browser
```

### Cookie System
- Cookies stored in `.cookie_cache.json` (gitignored)
- Auto-refresh via Playwright browser when >48 hours old
- Browser opens, user browses RVTrader, then navigates to `rvtrader.com/done` to signal completion
- Captures `datadome` and other required cookies automatically

### API Endpoints
```
Views: /gettiledata/addetail_listingstats/showadviewsstats?adId={id}
Saves: /gettiledata/addetail_listingstats/showsavedadsstats?adId={id}
```

### Response Format
```json
{"error": null, "listingViewsData": "138"}
{"error": null, "listingSavesData": 1}
```

---

## thor_brand_analysis.py

Analyzes Thor brand performance vs competitors and calculates estimated rank improvements based on the ranking algorithm point values.

### Usage
```bash
python src/complete/thor_brand_analysis.py                    # Analyze latest ranked_listings CSV
python src/complete/thor_brand_analysis.py -i output/file.csv # Specific input file
python src/complete/thor_brand_analysis.py -o report.txt      # Save to file (default: stdout)
```

### Output
- `output/thor_brand_report.txt` (when using -o flag)

### Report Sections
1. **Executive Summary** - Market share, avg rankings, total improvement potential
2. **Thor Brand Performance** - Breakdown by brand (Jayco, Airstream, Thor Motor Coach, etc.)
3. **Top Competitors** - Non-Thor brands ranked by listing count
4. **Top Performing Thor Listings** - Best ranked Thor units
5. **Ranking Improvement Opportunities** - Listings with estimated rank gains
6. **Quick Wins** - Easy fixes (add VIN, price, floorplan)
7. **Key Recommendations** - Prioritized action items with point values

### Rank Improvement Calculation
Uses ranking algorithm point values to estimate position gains:
```
~15 relevance points = 1 rank position improvement

Actions and their impact:
- Add price:     +194 relevance → ~13 positions
- Add VIN:       +165 relevance → ~11 positions
- 35+ photos:    +195 relevance → ~13 positions
- Add floorplan: +50 relevance  → ~3 positions
```

### Thor Brands Tracked
| Brand | Make Patterns Matched |
|-------|----------------------|
| Thor Motor Coach | thor, thor motor coach |
| Jayco | jayco |
| Airstream | airstream |
| Tiffin Motorhomes | tiffin, tiffin motorhomes |
| Entegra Coach | entegra, entegra coach |
| Heartland RV | heartland |
| Cruiser RV | cruiser |
| Keystone RV | keystone |
| Dutchmen RV | dutchmen |

---

## thor_brand_analysis_v2.py

**Comprehensive Thor brand analysis with tier ceiling constraints and per-manufacturer reports.** This is the recommended analysis tool for generating actionable recommendations.

### Key Improvements Over v1
- **Tier Ceiling Constraint**: Accounts for premium/standard tier system - standard listings can't outrank premium without purchasing premium
- **Correlation-Weighted Priority**: Actions prioritized by actual rank correlation strength
- **Outperforming Detection**: Identifies listings already beating their tier ceiling (low competition)
- **Manufacturer Reports**: Generates separate reports for each Thor brand to send to manufacturers
- **Dealer-Level Breakdown**: Shows each dealer's performance vs market average

### Usage
```bash
python src/complete/thor_brand_analysis_v2.py                    # Analyze latest ranked_listings CSV
python src/complete/thor_brand_analysis_v2.py -i output/file.csv # Specific input file
```

### Output Files
| File | Purpose |
|------|---------|
| `thor_actions_{timestamp}.csv` | **70-column CSV** with all listing data, actions, and improvement estimates |
| `thor_report_v2_{timestamp}.txt` | Executive summary report |
| `manufacturer_report_{brand}_{timestamp}.txt` | Per-brand reports for manufacturers |

### Tier System Explained
```
TIER HIERARCHY:
  top_premium (rank 1-3)   → Paid placement, highest visibility
  premium (rank 4-15)      → Paid placement
  standard (rank 16+)      → Free listings

TIER CEILING:
  Standard listings CANNOT outrank premium listings without purchasing premium.
  tier_ceiling = lowest premium rank in that search

  Example: If premium listings occupy ranks 1-15, standard tier ceiling = 16
  A standard listing at rank 20 can improve to rank 16, but NOT rank 15.
```

### Improvement Calculation
```
~15 relevance points ≈ 1 rank position improvement

Actions by correlation strength (highest impact first):
| Action          | Relevance | Merch | Rank Correlation |
|-----------------|-----------|-------|------------------|
| Add price       | +194 pts  | +5    | r = -0.840       |
| Add VIN         | +165 pts  | +6    | r = -0.689       |
| 35+ photos      | +195 pts  | +30   | r = -0.611       |
| Add floorplan   | +50 pts   | +12   | r = -0.300       |
| Add length      | +0 pts    | +8    | r = -0.125       |

Estimated improvement = total_relevance_gain / 15
Realistic improvement = min(estimated, current_rank - tier_ceiling)
```

### Manufacturer Report Format
Each Thor brand gets a report with:
1. **Brand Summary** - Avg rank, premium vs standard count, total improvement potential
2. **Quick Wins** - Count of easy fixes (missing price, VIN, floorplan, photos)
3. **Dealer Breakdown** - Each dealer's listings with:
   - Dealer metrics (listing count, avg rank vs market)
   - Process issues (missing data patterns)
   - Listing table (rank, year, model, price, photos, length, merch, status, actions)
   - Detailed action list per listing with URLs

### Listing Status Categories
| Status | Meaning |
|--------|---------|
| `Premium` | Paid placement - optimize to maintain position |
| `At Ceiling` | At tier ceiling - needs premium to improve further |
| `Outperform` | Standard listing beating tier ceiling (low competition) |

### CSV Columns (70 total)

**Hierarchy:** thor_brand, dealer_group, dealer_name, dealer_phone, dealer_location

**Vehicle:** id, vin, stock_number, year, make, model, trim, class, condition, length, price, msrp

**Ranking:** rank, relevance_score, merch_score, ad_listing_position

**Tier Analysis:** tier, tier_ceiling, realistic_new_rank, realistic_improvement, outperforming_tier

**Quality Metrics:** has_price, has_vin, has_floorplan, photo_count, photos_needed, length_missing

**Actions:** action_1 through action_5, total_relevance_gain, total_merch_gain, priority_score

**URLs:** listing_url

---

## dealer_scorecard.py

**Visual HTML scorecards that dealers can easily view and share.** This is the recommended tool for creating shareable dealer reports.

### Key Features
- **Beautiful HTML output** - Opens in any browser, easy to print/share
- **Per-dealer one-pagers** - Each dealer gets their own scorecard
- **Visual grade (A-F)** - At-a-glance quality assessment
- **Quick quality check** - Visual indicators for price, VIN, floorplan, photos
- **Top improvement opportunities** - Actionable items with estimated rank gains
- **All listings table** - Complete inventory with status indicators
- **Index page** - Summary of all dealers with links to individual scorecards

### Usage
```bash
python src/complete/dealer_scorecard.py                    # Uses latest ranked_listings CSV
python src/complete/dealer_scorecard.py -i input.csv       # Specific input file
python src/complete/dealer_scorecard.py --brand Jayco      # Filter to specific Thor brand
python src/complete/dealer_scorecard.py --dealer "Thor"    # Filter to specific dealer
```

### Output Files
| File | Purpose |
|------|---------|
| `output/scorecards/index_*.html` | Summary page linking all dealer scorecards |
| `output/scorecards/scorecard_{dealer}_*.html` | Per-dealer visual scorecard |

### Scorecard Sections
1. **Header** - Dealer name, brand, location, phone, overall grade (A-F)
2. **Key Metrics** - Avg rank, total listings, avg photos, positions to gain
3. **Quick Quality Check** - Visual indicators for price/VIN/floorplan/photos
4. **Top Opportunities** - Top 5 listings with specific actions needed
5. **All Listings Table** - Complete inventory with status badges

### Grading Scale
| Grade | Score | Meaning |
|-------|-------|---------|
| A | 90+ | Excellent - listings fully optimized |
| B | 80-89 | Good - minor improvements needed |
| C | 70-79 | Average - several improvements needed |
| D | 60-69 | Below Average - significant gaps |
| F | <60 | Poor - major optimization needed |

### Example Workflow
```bash
# 1. Get fresh ranking data
python src/complete/rank_listings.py --zip 60616

# 2. Generate visual scorecards for all Thor dealers
python src/complete/dealer_scorecard.py

# 3. Open index in browser to see all dealers
# Then share individual scorecard HTML files with dealers
```

---

## RV Type Codes
| Type | Code |
|------|------|
| Class A | 198066 |
| Class B | 198068 |
| Class C | 198067 |
| Fifth Wheel | 198069 |
| Toy Hauler | 198074 |
| Travel Trailer | 198073 |
| Truck Camper | 198072 |
| Pop-Up Camper | 198071 |
| Park Model | 198070 |
| Destination Trailer | 671069 |
| Teardrop Trailer | 764498 |

---

## Thor Industries Brands to Track
| Brand | Make Names to Match |
|-------|---------------------|
| Thor Motor Coach | thor, thor motor coach |
| Jayco | jayco |
| Airstream | airstream |
| Tiffin | tiffin, tiffin motorhomes |
| Entegra Coach | entegra, entegra coach |
| Heartland | heartland |
| Cruiser RV | cruiser |
| Keystone | keystone |
| Dutchmen | dutchmen |

---

## ScraperAPI (NOT USED)
Direct API is faster and works without blocks. ScraperAPI key retained for future use if needed.
- **Status:** DISABLED - direct RVTrader API works fine
- **API Key:** `ef66e965591986214ea474407eb0adc8`
- **Note:** ScraperAPI has async integration issues with aiohttp; direct API is ~50ms vs ~1s per request

---

## Environment
- **Python:** `C:\Users\rbiren\AppData\Local\anaconda3\python.exe`
- **Dependencies:** aiohttp, playwright

```bash
pip install aiohttp playwright
playwright install chromium
```

---

## Files to Potentially Clean Up
These scripts are partial/experimental:
- `src/detail_extractor.py`
- `src/spec_scraper.py`
- `src/spec_scraper_playwright.py`
- `src/fast_detail_scraper.py`

Consider consolidating into single `detail_batch_scraper.py`.

---

## Key Findings from Analysis

1. **Premium tier is dominant** - Paid placement overrides all other factors
2. **Distance is NOT a factor** - Premium at 47mi beats non-premium at 25mi
3. **Description truncated in search** - All 150 chars, can't analyze from search results
4. **Full description matters for merch_score** - Need detail pages
5. **Engagement data working** - Auto cookie refresh via Playwright browser (48h expiry)
6. **Tier ceiling is critical** - Standard listings can outperform their tier but can't promise further improvement
7. **Correlation-based priority works** - Price (r=-0.840) > VIN (r=-0.689) > Photos (r=-0.611) > Floorplan (r=-0.300)
8. **Quick wins available** - Missing VINs, prices, floorplans are easy fixes with high impact

### Sample Analysis Results (Class B, 60616)
| Brand | Listings | Avg Rank | Premium | Improvement Potential |
|-------|----------|----------|---------|----------------------|
| Jayco | 16 | 23.2 | 0 | 17 positions |
| Airstream | 12 | 32.2 | 2 | 30 positions |
| Thor Motor Coach | 6 | 24.0 | 3 | 25 positions |
| Entegra Coach | 2 | 21.5 | 2 | 9 positions |
| Tiffin Motorhomes | 1 | 40.0 | 0 | 0 positions |
