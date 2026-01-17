# Thor Brand Analysis v2 - Comprehensive Plan

**Date:** 2026-01-16
**Goal:** Create a comprehensive analysis tool that generates manufacturer-ready CSV reports with actionable improvement recommendations for each listing.

---

## Current State (v1)

### What v1 Does Well
- Identifies Thor brand listings
- Calculates basic brand metrics
- Estimates rank improvement potential
- Generates text report

### v1 Limitations
1. **Text-only output** - Not actionable for bulk operations
2. **Missing data sources** - Doesn't use description_scraper or engagement_scraper data
3. **Limited metrics** - Doesn't calculate estimated merch scores
4. **No dealer-level analysis** - Can't identify underperforming dealers
5. **No description scoring** - Ignores full description length (0.899 correlation!)
6. **No engagement correlation** - Has views/saves data but doesn't use it
7. **No priority scoring** - All improvements treated equally

---

## v2 Architecture

### Data Sources to Integrate

| Source | File Pattern | Key Fields |
|--------|--------------|------------|
| **Search Rankings** | `ranked_listings_*.csv` | 62 fields - rank, relevance, merch, all listing data |
| **Full Descriptions** | `detail_data_*.json` | description, description_length, specs |
| **Engagement Stats** | `engagement_stats_*.json` | views, saves |

### Data Merge Strategy

```python
# Primary key: listing id
merged_data = {
    # From ranked_listings CSV
    'id': '5038356664',
    'rank': 1,
    'relevance_score': 560.92,
    'merch_score': 114,
    'photo_count': 36,
    'has_floorplan': True,
    'has_vin': True,
    'has_price': True,
    'price': 139995,
    'length': 21,
    'is_premium': True,
    'is_top_premium': True,
    'badge_status': 'newly_listed',
    'create_date': '2026-01-10',
    'dealer_name': 'General RV Center',
    # ... all 62 fields

    # From detail_data JSON (merged by id)
    'description_full': '...',
    'description_length': 1299,
    'specs': {...},

    # From engagement_stats JSON (merged by id)
    'views': 132,
    'saves': 1,
}
```

---

## Comprehensive Metrics to Calculate

### 1. Listing Quality Scores

| Metric | Formula | Source |
|--------|---------|--------|
| **estimated_merch_score** | 72 + desc_pts + photo_pts + floorplan_pts + vin_pts + price_pts + length_pts | MERCH_SCORE.md |
| **merch_gap** | actual_merch - estimated_merch | Compare expected vs actual |
| **relevance_gap** | potential_relevance - actual_relevance | Missing fields impact |
| **quality_tier** | Low/Medium/High/Excellent (72-90/91-110/111-120/121-125) | MERCH_SCORE.md |

### 2. Description Analysis

| Metric | Calculation | Impact |
|--------|-------------|--------|
| **description_tier** | <500/500-1000/1000-2000/2000+ | +0/+15/+30/+45 merch pts |
| **description_gap** | Points available by improving | Easy lift if short |
| **has_keywords** | Check for key terms | Quality indicator |
| **word_count** | Words in description | Secondary metric |

### 3. Photo Analysis

| Metric | Calculation | Impact |
|--------|-------------|--------|
| **photo_tier** | 0-10/11-20/21-30/31-40/40+ | Diminishing returns curve |
| **photos_needed** | 35 - current (if < 35) | Clear target |
| **photo_pts_available** | Points from adding photos | MERCH_SCORE.md curve |

### 4. Engagement Metrics (when available)

| Metric | Calculation | Purpose |
|--------|-------------|---------|
| **views_per_day** | views / days_listed | Engagement velocity |
| **save_rate** | saves / views | Conversion indicator |
| **engagement_score** | Composite of views/saves/save_rate | Overall engagement |
| **rank_vs_engagement** | Correlation analysis | Are high-ranked listings engaging? |

### 5. Improvement Potential Scores

| Metric | Calculation | Purpose |
|--------|-------------|---------|
| **total_relevance_available** | Sum of all missing field points | Maximum possible gain |
| **total_merch_available** | Sum of all merch improvements | Quality improvement |
| **estimated_rank_improvement** | total_relevance / 15 | Positions recoverable |
| **priority_score** | Weighted by difficulty + impact | Action prioritization |
| **roi_score** | improvement_potential / effort | Quick wins first |

---

## Premium Tier Analysis

From RANKING_ALGORITHM.md, tier is the PRIMARY sort factor:

### Tier Breakdown
```
Top Premium (is_top_premium=1): Positions 1-3 guaranteed
Premium (is_premium=1, !top_premium): Positions 4-15 typical
Standard (is_premium=0): Position 16+ (algorithm-based)
```

### Tier Metrics to Calculate
| Metric | Purpose |
|--------|---------|
| **tier** | top_premium / premium / standard |
| **within_tier_rank** | Position within your tier |
| **tier_advancement_potential** | Would premium help this listing? |
| **premium_roi_score** | For high-merch standard listings |

---

## Dealer-Level Analysis

Group listings by `dealer_name` to identify:

| Metric | Calculation | Purpose |
|--------|-------------|---------|
| **dealer_listing_count** | Count per dealer | Volume |
| **dealer_avg_rank** | Avg rank per dealer | Performance |
| **dealer_avg_merch** | Avg merch per dealer | Quality consistency |
| **dealer_vin_rate** | % listings with VIN | Process gap |
| **dealer_price_rate** | % listings with price | Process gap |
| **dealer_floorplan_rate** | % listings with floorplan | Easy win count |
| **dealer_improvement_potential** | Total points recoverable | Prioritize outreach |

---

## CSV Output Schema

### Manufacturer Action CSV (one row per listing)

**Comprehensive schema with all supporting data:**

```csv
# === HIERARCHY / GROUPING ===
thor_brand,                    # Thor Motor Coach, Jayco, Airstream, etc.
dealer_group,                  # Dealer group name
dealer_name,                   # Individual dealer
dealer_phone,                  # Contact number

# === LISTING IDENTIFIERS ===
id,                           # RVTrader listing ID
listing_url,                  # Direct link to listing
stock_number,                 # Dealer's stock number
vin,                          # VIN (if disclosed)

# === VEHICLE INFO ===
year,
make,
model,
trim,
class,                        # Class A, B, C, etc.
condition,                    # New/Used
length,                       # Vehicle length (ft)
mileage,                      # For used

# === PRICING ===
price,                        # Listed price
msrp,                         # MSRP if available
price_vs_msrp,                # % difference

# === LOCATION ===
city,
state,
zip_code,

# === CURRENT RANKING DATA ===
rank,                         # Current search position
relevance_score,              # RVTrader's relevance score
merch_score,                  # RVTrader's merch score (actual)
estimated_merch_score,        # Our calculated estimate
merch_gap,                    # actual - estimated (quality check)

# === TIER ANALYSIS (CRITICAL) ===
tier,                         # top_premium / premium / standard
is_premium,                   # Boolean
is_top_premium,               # Boolean
tier_ceiling,                 # Best possible rank in tier
is_controllable,              # Can we optimize? (False for premium)
at_tier_ceiling,              # Maxed out standard potential?
premium_recommended,          # Should consider premium upgrade?

# === CURRENT LISTING QUALITY ===
has_price,                    # Boolean
has_vin,                      # Boolean
has_floorplan,                # Boolean
has_length,                   # Boolean
photo_count,                  # Number of photos
description_length,           # Character count (from detail scraper)
description_tier,             # <500 / 500-1000 / 1000-2000 / 2000+
quality_tier,                 # Low / Medium / High / Excellent

# === ENGAGEMENT DATA (if available) ===
views,
saves,
days_listed,
views_per_day,
save_rate,                    # saves / views

# === FRESHNESS / BADGES ===
badge_status,                 # newly_listed or null
create_date,
scheme_code,                  # AD, OEM, etc.
trusted_partner,              # Boolean

# === IMPROVEMENT POTENTIAL ===
total_relevance_available,    # Sum of all possible relevance gains
total_merch_available,        # Sum of all possible merch gains
unconstrained_improvement,    # Theoretical rank improvement
realistic_improvement,        # Tier-constrained improvement
realistic_new_rank,           # Projected rank after optimization
priority_score,               # Correlation-weighted priority

# === SPECIFIC ACTIONS NEEDED (Boolean flags) ===
needs_price,
needs_vin,
needs_floorplan,
needs_more_photos,
needs_longer_description,
needs_length,

# === ACTION DETAILS WITH POINT GAINS ===
# Price
price_action,                 # "Add price" or ""
price_relevance_gain,         # +194 or 0
price_merch_gain,             # +5 or 0

# VIN
vin_action,                   # "Add VIN" or ""
vin_relevance_gain,           # +165 or 0
vin_merch_gain,               # +6 or 0

# Floorplan
floorplan_action,             # "Add floorplan" or ""
floorplan_relevance_gain,     # +50 or 0
floorplan_merch_gain,         # +12 or 0

# Photos
photo_action,                 # "Add X photos to reach 35" or ""
photos_needed,                # Number to add
photo_relevance_gain,         # +195 (full) or +95 (partial) or 0
photo_merch_gain,             # +30 or +15 or 0

# Description
description_action,           # "Expand to 1000+ chars" or ""
description_chars_needed,     # Characters to add
description_merch_gain,       # +15 to +45 depending on tier jump

# Length
length_action,                # "Add vehicle length" or ""
length_merch_gain,            # +8 or 0

# === PRIORITIZED SUMMARY ===
action_1,                     # Highest impact action
action_1_points,              # Total points from action 1
action_2,                     # Second highest
action_2_points,
action_3,                     # Third highest
action_3_points,
all_actions_summary,          # Comma-separated list

# === ROI INDICATORS ===
points_per_action,            # Avg points per action needed
easy_wins_available,          # Count of Easy difficulty actions
```

### Dealer Summary CSV

```csv
# === HIERARCHY ===
thor_brand,
dealer_group,
dealer_name,
dealer_phone,
dealer_website,

# === VOLUME ===
listing_count,
premium_count,
standard_count,

# === PERFORMANCE ===
avg_rank,
best_rank,
worst_rank,
avg_merch_score,
avg_relevance_score,

# === QUALITY METRICS ===
vin_rate,                     # % with VIN
price_rate,                   # % with price
floorplan_rate,               # % with floorplan
avg_photo_count,
avg_description_length,

# === PROCESS GAPS ===
missing_vin_count,
missing_price_count,
missing_floorplan_count,
low_photo_count,              # < 35 photos
short_description_count,      # < 1000 chars

# === IMPROVEMENT POTENTIAL ===
total_relevance_available,
total_realistic_improvement,
avg_improvement_per_listing,
at_ceiling_count,             # Listings maxed in standard tier

# === PRIORITIZATION ===
priority_score,               # Dealer-level priority
top_recommendation,           # Single most impactful action
easy_wins_count,              # Count of easy fixes available
```

### Brand Summary CSV

```csv
thor_brand,
listing_count,
market_share_pct,
avg_rank,
avg_merch_score,
premium_rate,
vin_rate,
price_rate,
floorplan_rate,
avg_photo_count,
total_improvement_potential,
top_recommendation,
```

---

## Enhanced Text Report Sections

### New Sections to Add

1. **Data Sources Summary**
   - Files merged, timestamps, coverage

2. **Premium Tier Breakdown**
   - Top premium vs premium vs standard distribution
   - Thor representation in each tier

3. **Description Analysis**
   - Length distribution by brand
   - Correlation with merch score
   - Specific listings needing longer descriptions

4. **Photo Optimization Matrix**
   - Current distribution by tier
   - Optimal photo count recommendations
   - ROI curve (diminishing returns)

5. **Engagement Correlation** (if data available)
   - Views vs rank
   - Saves vs merch score
   - High-engagement underranked listings

6. **Dealer Scorecards**
   - Top 10 dealers by listing count
   - Improvement potential by dealer
   - Process consistency metrics

7. **Model Performance**
   - Best/worst performing models
   - Model-specific recommendations

8. **Market Comparison** (multi-zip)
   - Thor performance by market
   - Regional opportunities

---

## Point Values Reference (from docs)

### Relevance Score Points
| Factor | Points | Condition |
|--------|--------|-----------|
| has_price | +194 | Price displayed |
| has_vin | +165 | VIN disclosed |
| photo_count >= 35 | +195 | vs <15 photos |
| photo_count >= 20 | +100 | vs <15 photos (partial) |
| has_floorplan | +50 | Floorplan uploaded |
| badge_status=newly_listed | +75 | Freshness boost |

### Merch Score Points
| Factor | Points | Details |
|--------|--------|---------|
| description 2000+ | +45 | Full lift |
| description 1000-2000 | +30 | Good lift |
| description 500-1000 | +15 | Basic lift |
| description 100-500 | +5 | Minimal |
| photo_count | ~0.5/photo | Cap ~33 pts |
| has_floorplan | +12 | Easy win |
| has_vin | +6 | Easy |
| has_price | +5 | Easy |
| has_length | +8 | Easy |

### Conversion
```
~15 relevance points ≈ 1 rank position improvement
```

---

## Grouping Hierarchy

Data will be grouped in this order:
```
Thor Brand (Jayco, Airstream, Thor Motor Coach, etc.)
  └── Dealer Group (dealer_group field)
        └── Dealer Name (dealer_name field)
              └── Individual Listings
```

This allows:
- Brand-level performance comparison
- Dealer group accountability
- Individual dealer process gaps
- Per-listing action items

---

## CRITICAL: Premium Tier Ceiling Constraint

### The Problem
You **CANNOT** outrank premium listings if you're not premium. The ranking system is:

```
Position 1-3:   Top Premium (LOCKED - only money moves you here)
Position 4-15:  Premium (LOCKED - only money moves you here)
Position 16+:   Standard (ALGORITHM - this is what we can optimize)
```

### Realistic Improvement Calculation

```python
def calculate_realistic_improvement(listing, all_listings):
    """
    Calculate improvement constrained by tier ceiling.
    """
    current_rank = listing['rank']
    tier = get_tier(listing)  # 'top_premium', 'premium', 'standard'

    # Find tier ceiling (best possible rank in your tier)
    if tier == 'standard':
        # Find the worst-ranked premium listing
        premium_listings = [l for l in all_listings if l['is_premium']]
        if premium_listings:
            worst_premium_rank = max(l['rank'] for l in premium_listings)
            tier_ceiling = worst_premium_rank + 1  # First standard position
        else:
            tier_ceiling = 1  # No premium = can reach #1
    elif tier == 'premium':
        # Find worst top_premium rank
        top_premium = [l for l in all_listings if l['is_top_premium']]
        tier_ceiling = max(l['rank'] for l in top_premium) + 1 if top_premium else 1
    else:  # top_premium
        tier_ceiling = 1

    # Calculate unconstrained improvement
    unconstrained_improvement = total_relevance_gain / 15  # ~15 pts per position
    unconstrained_new_rank = current_rank - unconstrained_improvement

    # Apply tier ceiling constraint
    realistic_new_rank = max(tier_ceiling, unconstrained_new_rank)
    realistic_improvement = current_rank - realistic_new_rank

    # Flag if hitting ceiling
    at_tier_ceiling = (realistic_new_rank == tier_ceiling)

    return {
        'tier': tier,
        'tier_ceiling': tier_ceiling,
        'unconstrained_improvement': unconstrained_improvement,
        'realistic_improvement': realistic_improvement,
        'realistic_new_rank': realistic_new_rank,
        'at_tier_ceiling': at_tier_ceiling,
        'premium_recommended': at_tier_ceiling and tier == 'standard',
    }
```

### New CSV Columns for Tier Analysis

| Column | Description |
|--------|-------------|
| `tier` | top_premium / premium / standard |
| `tier_ceiling` | Best achievable rank in current tier |
| `unconstrained_improvement` | Theoretical improvement (ignoring tier) |
| `realistic_improvement` | Actual improvement possible in tier |
| `at_tier_ceiling` | True if maxed out standard potential |
| `premium_recommended` | True if should consider premium upgrade |
| `is_controllable` | False for premium/top_premium (can't optimize further) |

---

## Priority Scoring Algorithm (Correlation-Weighted)

Using actual correlations from the data:

### Relevance Correlations (with rank - negative = better)
| Factor | Correlation | Weight |
|--------|-------------|--------|
| has_price | -0.840 | 0.840 |
| has_vin | -0.689 | 0.689 |
| photo_count | -0.611 | 0.611 |
| merch_score | -0.516 | 0.516 |

### Merch Score Correlations (positive = higher merch)
| Factor | Correlation | Weight |
|--------|-------------|--------|
| description_length | 0.899 | 0.899 |
| has_length | 0.702 | 0.702 |
| photo_count | 0.658 | 0.658 |
| has_floorplan | 0.554 | 0.554 |
| has_vin | 0.412 | 0.412 |
| has_price | 0.298 | 0.298 |

```python
# Correlation-weighted point values
WEIGHTED_POINTS = {
    'has_price': {
        'relevance': 194,
        'merch': 5,
        'rank_correlation': 0.840,  # Weight for prioritization
        'merch_correlation': 0.298,
    },
    'has_vin': {
        'relevance': 165,
        'merch': 6,
        'rank_correlation': 0.689,
        'merch_correlation': 0.412,
    },
    'photos_35plus': {
        'relevance': 195,
        'merch': 30,
        'rank_correlation': 0.611,
        'merch_correlation': 0.658,
    },
    'has_floorplan': {
        'relevance': 50,
        'merch': 12,
        'rank_correlation': 0.300,  # Estimated
        'merch_correlation': 0.554,
    },
    'description_2000plus': {
        'relevance': 0,  # No direct relevance impact
        'merch': 45,
        'rank_correlation': 0.200,  # Indirect via merch
        'merch_correlation': 0.899,  # HIGHEST!
    },
    'has_length': {
        'relevance': 0,
        'merch': 8,
        'rank_correlation': 0.100,
        'merch_correlation': 0.702,
    },
}

def calculate_priority_score(listing, improvements):
    """
    Priority score weighted by correlation strength.
    Higher correlation = more reliable impact = higher priority.
    """
    score = 0

    for imp in improvements:
        # Base points
        relevance_pts = imp['relevance_gain']
        merch_pts = imp['merch_gain']

        # Weight by correlation (how confident are we this helps?)
        rank_weight = imp.get('rank_correlation', 0.5)
        merch_weight = imp.get('merch_correlation', 0.5)

        # Combined weighted score
        weighted_impact = (relevance_pts * rank_weight) + (merch_pts * merch_weight * 3)

        # Difficulty multiplier (easy = higher priority)
        difficulty_mult = {'Easy': 1.5, 'Medium': 1.0, 'Cost': 0.3}
        weighted_impact *= difficulty_mult.get(imp['difficulty'], 1.0)

        score += weighted_impact

    # Tier constraint adjustment
    if listing.get('at_tier_ceiling'):
        score *= 0.5  # Lower priority if can't improve further without premium

    return score
```

---

## Implementation Phases

### Phase 1: Data Integration
- [ ] Load ranked_listings CSV
- [ ] Load and merge detail_data JSON (by id)
- [ ] Load and merge engagement_stats JSON (by id)
- [ ] Handle missing data gracefully

### Phase 2: Metric Calculation
- [ ] Calculate estimated_merch_score for each listing
- [ ] Calculate description_tier and gaps
- [ ] Calculate photo optimization recommendations
- [ ] Calculate priority scores
- [ ] Calculate dealer-level aggregations

### Phase 3: CSV Output
- [ ] Generate per-listing action CSV
- [ ] Generate dealer summary CSV
- [ ] Include all fields for manufacturer use

### Phase 4: Enhanced Report
- [ ] Add premium tier breakdown
- [ ] Add description analysis section
- [ ] Add photo optimization matrix
- [ ] Add engagement correlation (if data)
- [ ] Add dealer scorecards

### Phase 5: Testing & Validation
- [ ] Test with sample data
- [ ] Validate estimated merch scores vs actual
- [ ] Verify CSV formats for manufacturer use

---

## Command Line Interface

```bash
# Basic usage (auto-detect latest files)
python src/complete/thor_brand_analysis_v2.py

# Specify input files
python src/complete/thor_brand_analysis_v2.py \
    --rankings output/ranked_listings_*.csv \
    --details output/detail_data_*.json \
    --engagement output/engagement_stats_*.json

# Output options
python src/complete/thor_brand_analysis_v2.py \
    --output-csv output/thor_actions.csv \
    --output-dealer output/dealer_summary.csv \
    --output-report output/thor_report_v2.txt

# Filter options
python src/complete/thor_brand_analysis_v2.py \
    --thor-only              # Only Thor brands
    --min-rank 10            # Only listings ranked worse than 10
    --min-improvement 5      # Only listings with 5+ position potential
```

---

## Expected Output Files

1. **thor_listing_actions_{timestamp}.csv** - Per-listing recommendations
2. **thor_dealer_summary_{timestamp}.csv** - Dealer-level summary
3. **thor_analysis_report_{timestamp}.txt** - Enhanced text report

---

## Success Criteria

1. **CSV is actionable** - Manufacturer can filter/sort and take action
2. **All factors considered** - Uses all 62 ranked_listings fields + description + engagement
3. **Estimated merch score accurate** - Within ±3 points of actual
4. **Priority scoring works** - High-value quick wins at top
5. **Dealer insights useful** - Identifies process gaps by dealer
6. **Multi-market ready** - Works with data from multiple zips

---

## Questions Before Implementation

1. **CSV column preferences?** - Any specific columns you need?
2. **Dealer grouping?** - Group by dealer_name or dealer_group?
3. **Multi-zip handling?** - One combined report or per-zip?
4. **Engagement thresholds?** - What views/saves counts are "good"?
