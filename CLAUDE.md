# RVTrader Scraper

## Project Goal
Extract RV listing data from RVTrader.com to help **Thor Industries brands** (Thor Motor Coach, Jayco, Airstream, Tiffin, Entegra Coach) improve their listing rankings.

## Quick Start
```bash
# Rank all listings by zip code (all RV types)
python src/rank_listings.py --zip 60616

# Single RV type only
python src/rank_listings.py --zip 60616 --type "Travel Trailer"

# Used condition instead of New (default)
python src/rank_listings.py --zip 60616 --condition U
```

## Project Structure
```
rv_trader/
├── CLAUDE.md                # THIS FILE - Project context
├── zip_codes.txt            # Zip codes to search (one per line)
├── src/
│   ├── rank_listings.py     # MAIN: Bulk ranked extraction (62 fields, ~5s/zip)
│   ├── nuxt_extractor.py    # Single page extraction (Playwright)
│   └── engagement_scraper.py # Views/saves extraction (needs work)
├── output/                  # Extracted data (CSV/JSON)
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
| `nuxt_extractor.py` | Single page detail extraction | **COMPLETE** |

### What Needs Work
| Task | Status | Blocker |
|------|--------|---------|
| Engagement data (views/saves) | **BLOCKED** | API needs session cookies |
| Detail page batch scraping | **PARTIAL** | HTTP blocked, Playwright slow |
| Analytics pipeline | **NOT STARTED** | Waiting on data collection |

### Next Priority
1. Fix `engagement_scraper.py` - cookies expire, need fresh datadome cookie
2. Build batch detail scraper via ScraperAPI
3. Merge search + detail + engagement data
4. Build Thor brand comparison analytics

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

Fast bulk extraction using async HTTP via ScraperAPI. Extracts all listings for each RV type in a zip code with search position ranks.

### Usage
```bash
python src/rank_listings.py                              # All zips in zip_codes.txt
python src/rank_listings.py --zip 60616                  # Single zip
python src/rank_listings.py --zip 60616 --type "Class B" # Single type
python src/rank_listings.py --zip 60616 --condition U    # Used (default=New)
python src/rank_listings.py --zip 60616 --radius 100     # Custom radius (default=50)
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
- 10 concurrent requests via ScraperAPI

---

## engagement_scraper.py

Extracts views/saves/days_listed from detail pages via API endpoints.

### API Endpoints (Discovered)
```
Views: /gettiledata/addetail_listingstats/showadviewsstats?adId={id}
Saves: /gettiledata/addetail_listingstats/showsavedadsstats?adId={id}
```

### Current Issue
Requires valid `datadome` session cookie. Cookies expire. Need to:
1. Open browser to RVTrader
2. Copy fresh `datadome` cookie from DevTools
3. Update COOKIE constant in script

### Response Format
```json
{"error": null, "listingViewsData": "138"}
{"error": null, "listingSavesData": 1}
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

## ScraperAPI
All search requests route through ScraperAPI to avoid IP blocks.
- **API Key:** `ef66e965591986214ea474407eb0adc8`
- **Endpoint:** `http://api.scraperapi.com?api_key=KEY&url=TARGET`
- **Config:** Line 22 in `rank_listings.py`

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
5. **Engagement data requires browser session** - API needs datadome cookie
