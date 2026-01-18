# RVTrader Scraper

## Project Goal
Extract RV listing data from RVTrader.com to help **Thor Industries brands** (Thor Motor Coach, Jayco, Airstream, Tiffin, Entegra Coach) improve their listing rankings.

## Quick Start
```bash
# 1. Get search rankings (fast, no cookies needed)
python src/complete/rank_listings.py --zip 60616

# 2. Generate manufacturer regional reports (NEW - for sales leaders)
python src/complete/regional_summary.py

# 3. Generate dealer scorecards (shareable HTML)
python src/complete/dealer_scorecard.py

# Optional: Additional data collection
# 4. Refresh cookies if needed (opens browser)
python src/complete/engagement_scraper.py --refresh-cookies

# 5. Get engagement stats (views/saves)
python src/complete/engagement_scraper.py --limit 50
```

## Project Structure
```
rv_trader/
├── CLAUDE.md                    # THIS FILE - Project context
├── zip_codes.txt                # Zip codes to search (one per line)
├── .cookie_cache.json           # Cached cookies for scraping (gitignored)
├── src/
│   └── complete/                # Production-ready scripts
│       ├── rank_listings.py           # Bulk ranked extraction (62 fields)
│       ├── regional_summary.py        # Manufacturer + region reports
│       ├── dealer_scorecard.py        # Visual dealer scorecards
│       ├── weekly_tracker.py          # **NEW** WoW tracking + history
│       ├── engagement_scraper.py      # Views/saves extraction
│       ├── description_scraper.py     # Full descriptions from detail pages
│       ├── thor_brand_analysis.py     # Thor analysis v1 (basic)
│       └── thor_brand_analysis_v2.py  # Thor analysis v2 (with tiers)
├── output/
│   ├── reports/                       # Manufacturer regional reports + WoW reports
│   │   ├── {Brand}_regional_*.html    # Per-manufacturer report
│   │   └── wow_report_*.html          # Week-over-week change report
│   ├── scorecards/                    # Dealer scorecards
│   │   ├── index_*.html               # Summary dashboard
│   │   └── scorecard_{dealer}_*.html  # Per-dealer scorecard
│   ├── history/                       # Historical tracking data
│   │   └── listing_history.json       # Item-level history (52 weeks)
│   └── ranked_listings_*.csv          # Raw ranking data
├── docs/
│   ├── RANKING_ALGORITHM.md     # Complete ranking formula
│   └── MERCH_SCORE.md           # Merch score components
└── samples/                     # Sample data files
```

---

## Current Status (2026-01-18)

### What's Complete
| Script | Purpose | Status |
|--------|---------|--------|
| `rank_listings.py` | Search results extraction (62 fields) | **COMPLETE** |
| `regional_summary.py` | Manufacturer + region hierarchy reports | **COMPLETE** |
| `dealer_scorecard.py` | Visual HTML scorecards with benchmarking | **COMPLETE** |
| `weekly_tracker.py` | Week-over-week tracking and history | **NEW** |
| `engagement_scraper.py` | Views/saves extraction | **COMPLETE** |
| `description_scraper.py` | Full descriptions from detail pages | **COMPLETE** |

### Report Hierarchy
```
Manufacturer Report (Jayco, Keystone, etc.)
  └── Regional Summary (Midwest, Southeast, etc.)
        └── Dealer Scorecard
              └── Listing Detail (with specific actions)
```

---

## Ranking Algorithm (Simplified for Users)

### How Rankings Work

```
RANK = TIER + LISTING QUALITY SCORE

TIER (Paid - overrides everything):
  Top Premium  → Positions 1-3
  Premium      → Positions 4-15
  Standard     → Position 16+

LISTING QUALITY SCORE (Free to improve):
  Higher score = better position within your tier
```

### Ranking Factors (Sorted by Impact)

| Factor | Rank Points | Est. Position Gain | Difficulty |
|--------|-------------|-------------------|------------|
| **35+ Photos** | 801 | +53 positions | Medium |
| **Price Listed** | 295 | +20 positions | Easy |
| **Floorplan** | 292 | +19 positions | Easy |
| **VIN Disclosed** | 286 | +19 positions | Easy |
| **Length Spec** | 162 | +11 positions | Easy |

**Note:** ~15 points = 1 position improvement

### How Points Are Calculated
Each factor contributes via TWO pathways:
1. **Direct relevance boost** (immediate ranking impact)
2. **Merch score boost × 20.2 multiplier** (indirect but significant)

Example: Adding a floorplan
- Direct: +50 relevance points
- Merch: +12 points × 20.2 = +242 relevance points
- **Total: 292 points → ~19 position improvement**

---

## regional_summary.py

**Generates per-manufacturer reports with regional breakdown.** Designed for regional sales leaders to share with dealers.

### Usage
```bash
python src/complete/regional_summary.py                    # All manufacturers
python src/complete/regional_summary.py --brand Jayco      # Single manufacturer
python src/complete/regional_summary.py --region Midwest   # Single region
```

### Output
- `output/reports/{Brand}_regional_{timestamp}.html`

### Report Structure
```
Jayco Regional Report
├── Header: Grade, Quality Score, Avg Rank, Positions Available
├── Quick Wins: Missing Price/VIN/Floorplan/Length/Photos
│
├── Midwest Region
│   ├── Dealer: Jayco of Chicago (Grade B)
│   │   ├── Listing: 2025 Terrain 19Y | Rank 9 | Stock: STK001
│   │   │   └── Actions: Add floorplan +19, Add photos +53
│   │   └── Listing: 2024 Swift 27K | Rank 12 | Complete
│   └── Dealer: Camping World (Grade C)
│       └── Listings...
│
├── Southeast Region
│   └── Dealers...
│
└── Footer
```

### Regions
| Region | States |
|--------|--------|
| Midwest | IL, IN, IA, KS, MI, MN, MO, NE, ND, OH, SD, WI |
| Northeast | CT, DE, ME, MD, MA, NH, NJ, NY, PA, RI, VT |
| Southeast | AL, AR, FL, GA, KY, LA, MS, NC, SC, TN, VA, WV |
| Southwest | AZ, NM, OK, TX |
| West | AK, CA, CO, HI, ID, MT, NV, OR, UT, WA, WY |

---

## dealer_scorecard.py

**Visual HTML scorecards for individual dealers.** Easy to share and print.

### Usage
```bash
python src/complete/dealer_scorecard.py                    # All dealers
python src/complete/dealer_scorecard.py --brand Jayco      # Filter by brand
python src/complete/dealer_scorecard.py --dealer "Chicago" # Filter by dealer name
```

### Output
- `output/scorecards/index_*.html` - Dashboard with all dealers
- `output/scorecards/scorecard_{dealer}_*.html` - Individual dealer cards

### Features
- **Overall Grade (A-F)** based on listing quality
- **Market Benchmarks** - Compare dealer vs market average
- **Thor vs Competitor Analysis** - Competitive gaps by ranking factor
- **Quick Wins** - Missing data with estimated position gains
- **Listing Table** - All inventory with status and actions

---

## Weekly Process (Recommended)

```
MONDAY: Data Collection
────────────────────────
1. python src/complete/rank_listings.py        # Get fresh rankings
2. python src/complete/engagement_scraper.py   # Get views/saves (optional)

TUESDAY: Report Generation
──────────────────────────
3. python src/complete/regional_summary.py     # Manufacturer reports
4. python src/complete/dealer_scorecard.py     # Dealer scorecards

WEDNESDAY: Distribution
───────────────────────
5. Send manufacturer reports to regional sales leaders
6. Sales leaders share dealer scorecards with dealers
7. Track quick wins completed
```

---

## weekly_tracker.py

**Week-over-week tracking system.** Stores listing history and tracks changes over time.

### Usage
```bash
python src/complete/weekly_tracker.py                # Process latest data, update history
python src/complete/weekly_tracker.py --report       # Generate WoW report only
python src/complete/weekly_tracker.py --brand Jayco  # Filter to specific brand
```

### Output
- `output/history/listing_history.json` - Historical data (keeps 52 weeks)
- `output/reports/wow_report_{timestamp}.html` - Week-over-week comparison report

### Features
- **Item-level tracking** by stock number or listing ID
- **Rank change tracking** - positions gained/lost
- **Quality score tracking** - improvements over time
- **Action completion tracking** - which fixes were done
- **New/Sold detection** - track inventory changes

### Report Sections
1. **Summary** - Improved/declined/new/sold counts
2. **Top Improvements** - Listings that gained the most positions
3. **Declines** - Listings that lost positions
4. **New Listings** - Added this week

---

## Remaining TODOs

### High Priority
| Task | Description | Script |
|------|-------------|--------|
| **Merge engagement data** | Add views/saves to reports | Update all reports |

### Medium Priority
| Task | Description | Script |
|------|-------------|--------|
| **Multi-zip collection** | Run rankings across multiple markets | `weekly_collector.py` |
| **Trend charts** | Visual rank/quality trends over time | Update reports |
| **Email/PDF export** | For easier distribution | New feature |

### Low Priority
| Task | Description | Script |
|------|-------------|--------|
| **Listing detail page** | Deep-dive single listing report | New script |
| **API integration** | Push data to external systems | New feature |
| **Cleanup old scripts** | Remove experimental files in `src/` | Maintenance |

### Data Gaps to Investigate
| Factor | Status | Notes |
|--------|--------|-------|
| `age_penalty` | **UNKNOWN** | Need to correlate create_date with rank |
| `price_drop` | **UNKNOWN** | price_drop_date field exists, impact unclear |
| `description_length` | **KNOWN** | +909 pts but can't measure from search API |
| `trusted_partner` | **NOT A FACTOR** | No correlation with rank observed |

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
| Cruiser RV | cruiser |
| Keystone RV | keystone |
| Dutchmen RV | dutchmen |

---

## Key Findings

1. **Premium tier dominates** - Paid placement overrides all quality factors
2. **Photos are king** - 801 total points, biggest controllable factor
3. **Merch multiplier is 20.2x** - Merch score contributions are amplified significantly
4. **Quick wins available** - Many listings missing basic data (VIN, floorplan, length)
5. **Description hidden** - Can't measure from search API, need detail pages
6. **Distance doesn't matter** - Premium at 47mi beats standard at 5mi

---

## Environment

```bash
pip install aiohttp playwright
playwright install chromium
```

---

## Project Structure (Clean)
All production scripts are in `src/complete/`. No cleanup needed.
