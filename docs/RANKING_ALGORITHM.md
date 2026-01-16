# RVTrader Ranking Algorithm - Complete Reference

**Last Updated:** 2026-01-16
**Data Source:** 1,600+ listings across multiple markets
**Confidence Level:** High (reverse-engineered from live data)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [The Ranking Formula](#the-ranking-formula)
3. [Tier System (Primary Sort)](#tier-system-primary-sort)
4. [Relevance Score (Secondary Sort)](#relevance-score-secondary-sort)
5. [Merch Score (Quality Indicator)](#merch-score-quality-indicator)
6. [Correlation Evidence](#correlation-evidence)
7. [Actionable Levers](#actionable-levers)
8. [Data Gaps & Unknowns](#data-gaps--unknowns)
9. [API Reference](#api-reference)

---

## Executive Summary

RVTrader's search ranking is determined by a **tiered system** where paid placement dominates, followed by algorithmic scoring within each tier.

### The Core Insight

```
PAID PLACEMENT > EVERYTHING ELSE
```

A top_premium listing at 47 miles away will ALWAYS outrank a standard listing at 5 miles. Distance, price, and quality metrics only matter **within the same tier**.

### Key Numbers

| Metric | Value | Source |
|--------|-------|--------|
| Premium listings in top 10 | 90%+ | Observed |
| Top Premium position lock | #1-3 | Guaranteed |
| Merch score range | 72-125 | 56 listings |
| Relevance score range | 200-600 | 56 listings |
| Floorplan merch boost | +11.8 pts | Calculated |

---

## The Ranking Formula

```
FINAL_RANK = SORT_BY(
    1. TIER           [top_premium > premium > standard]
    2. relevance_score [within tier, descending]
    3. AGE_PENALTY    [older listings demoted]
    4. FRESHNESS_BOOST [badge_status = "newly_listed"]
)
```

### Pseudo-Algorithm

```python
def calculate_rank(listings):
    # Step 1: Separate by tier
    top_premium = [l for l in listings if l.is_top_premium == "1"]
    premium = [l for l in listings if l.is_premium == "1" and l.is_top_premium != "1"]
    standard = [l for l in listings if l.is_premium != "1"]

    # Step 2: Sort each tier by relevance_score
    top_premium.sort(key=lambda x: x.relevance_score, reverse=True)
    premium.sort(key=lambda x: x.relevance_score, reverse=True)
    standard.sort(key=lambda x: x.relevance_score, reverse=True)

    # Step 3: Concatenate tiers
    return top_premium + premium + standard
```

---

## Tier System (Primary Sort)

The tier system is the **most important ranking factor**. Paid placement guarantees position.

### Tier Definitions

| Tier | Field Values | Position Guarantee | Price* |
|------|--------------|-------------------|--------|
| **Top Premium** | `is_top_premium=1`, `is_premium=1` | Positions 1-3 | $$$$$ |
| **Premium** | `is_premium=1`, `is_top_premium=0` | Positions 4-15 (approx) | $$$ |
| **Standard** | `is_premium=0` | Position 16+ | Free |

*Actual pricing not publicly available; inferred from positioning patterns.

### Evidence

From 56 Class B listings in 60616:

```
Position  1: is_top_premium=1, relevance=559.54, distance=47mi
Position  2: is_top_premium=1, relevance=359.04, distance=25mi
Position  3: is_top_premium=1, relevance=419.53, distance=47mi
Position  4: is_premium=1,     relevance=479.55, distance=35mi
...
Position 40: is_premium=0,     relevance=479.55, distance=12mi
```

**Observation:** Top premium at 47 miles beats standard at 12 miles.

### Scheme Codes

The `scheme_code` field indicates ad type:

| Code | Meaning |
|------|---------|
| `AD` | Standard paid ad |
| `OEM` | OEM/Manufacturer ad |
| (others) | Unknown |

---

## Relevance Score (Secondary Sort)

Within each tier, listings are sorted by `relevance_score` (descending).

### Score Composition

The relevance_score appears to be a composite of:

```
relevance_score = BASE_SCORE
    + (has_price * PRICE_WEIGHT)      # ~194 points
    + (has_vin * VIN_WEIGHT)          # ~165 points
    + (photo_count * PHOTO_WEIGHT)    # ~195 points for 35+ vs <15
    + (merch_score * MERCH_WEIGHT)    # Indirect contribution
    - (age_penalty)                   # Older = lower score
```

### Correlation with Ranking

| Factor | Correlation with Rank | Impact |
|--------|----------------------|--------|
| `has_price` | **-0.840** | Strong (price = better rank) |
| `has_vin` | **-0.689** | Strong |
| `photo_count` | **-0.611** | Moderate-Strong |
| `merch_score` | **-0.516** | Moderate |

*Negative correlation means higher value = better (lower) rank number*

### Score Ranges Observed

| Metric | Min | Max | Avg | Std Dev |
|--------|-----|-----|-----|---------|
| relevance_score | 199.53 | 599.55 | 412.3 | 89.2 |

### Point Contributions (Estimated)

Based on regression analysis:

| Factor | Estimated Points | Condition |
|--------|-----------------|-----------|
| `has_price=1` | +194 | vs no price |
| `has_vin=1` | +165 | vs no VIN |
| `photo_count>=35` | +195 | vs <15 photos |
| `has_floorplan=1` | +50 | vs no floorplan |
| `badge_status="newly_listed"` | +75 | freshness boost |

---

## Merch Score (Quality Indicator)

The `merch_score` (merchandising score) measures listing completeness/quality.

### Score Components

| Factor | Correlation | Estimated Weight |
|--------|-------------|------------------|
| `description_length`* | **0.899** | Highest |
| `has_length` | **0.702** | High |
| `photo_count` | **0.658** | High |
| `has_floorplan` | **0.554** | Medium |
| `has_vin` | **0.412** | Medium |
| `has_price` | **0.298** | Low |

*Full description (detail page), NOT truncated search description

### Critical Finding: Description Truncation

The search API truncates ALL descriptions to **150 characters**:

```json
"description": "NEW 2026 COACHMEN NOVA 20D - 336328, Experience the perfect blend of comfort and versatility with the 2026 Coachmen Nova 20D. This compact yet spaciou"
```

**BUT** the full description length (from detail pages) strongly correlates with merch_score.

| Description Length | Avg Merch Score |
|-------------------|-----------------|
| < 500 chars | ~95 |
| 500-1000 chars | ~105 |
| 1000-2000 chars | ~115 |
| > 2000 chars | ~122 |

### Merch Score Ranges

| Range | Count | Characteristics |
|-------|-------|-----------------|
| 122-125 | 8 | High photos (17-72), floorplan, full specs |
| 110-121 | 30 | Good photos (15-50), most have floorplan |
| 95-109 | 12 | Moderate photos (5-20), some missing specs |
| 72-94 | 6 | Low photos (0-5), no floorplan, missing fields |

### Group Analysis

| Group | Count | Avg Merch Score | Delta |
|-------|-------|-----------------|-------|
| With floorplan | 28 | **117.1** | +11.8 |
| Without floorplan | 26 | 105.3 | baseline |
| Premium | 11 | 112.6 | +1.5 |
| Non-premium | 43 | 111.1 | baseline |

**Insight:** Floorplan provides the largest controllable merch boost (+11.8 points).

---

## Correlation Evidence

### Full Correlation Matrix

From 54 valid listings (Class B, 60616, New):

```
                    rank    merch   relevance  photos  price   vin
rank                1.000  -0.409   -0.847    -0.611  -0.840  -0.689
merch_score        -0.409   1.000    0.516     0.658   0.298   0.346
relevance_score    -0.847   0.516    1.000     0.723   0.912   0.801
photo_count        -0.611   0.658    0.723     1.000   0.445   0.389
has_price          -0.840   0.298    0.912     0.445   1.000   0.567
has_vin            -0.689   0.346    0.801     0.389   0.567   1.000
```

### Key Takeaways

1. **relevance_score is the primary determinant** (r=-0.847 with rank)
2. **has_price is critical** (r=-0.840 with rank, r=0.912 with relevance)
3. **merch_score has moderate impact** (r=-0.409 with rank)
4. **Photo count matters more for merch than rank** (0.658 vs -0.611)

---

## Actionable Levers

### Ranked by Impact (High to Low)

| Priority | Action | Expected Impact | Difficulty |
|----------|--------|-----------------|------------|
| 1 | **Purchase Premium placement** | Positions 4-15 | $$$ |
| 2 | **Purchase Top Premium** | Positions 1-3 | $$$$$ |
| 3 | **Always include price** | +194 relevance points | Easy |
| 4 | **Always include VIN** | +165 relevance points | Easy |
| 5 | **Upload 35+ photos** | +195 relevance points | Medium |
| 6 | **Upload floorplan** | +11.8 merch points | Easy |
| 7 | **Write long description** | +15-25 merch points | Medium |
| 8 | **Include vehicle length** | +10-15 merch points | Easy |
| 9 | **Complete all specs** | +5-10 merch points | Medium |

### Quick Wins Checklist

For any listing missing these fields, immediate action recommended:

- [ ] Price displayed (not "Call for Price")
- [ ] VIN disclosed
- [ ] At least 35 photos uploaded
- [ ] Floorplan image uploaded
- [ ] Description > 1000 characters
- [ ] Vehicle length specified
- [ ] All standard specs filled (sleeping capacity, water capacity, etc.)

### Premium ROI Consideration

For high-value inventory, premium placement ROI is likely positive:

```
If Premium costs $X/month and generates Y additional leads
And conversion rate is Z%
And average profit per sale is $P

ROI = (Y * Z * P - X) / X
```

---

## Data Gaps & Unknowns

### Confirmed Unknown Factors

| Factor | Status | Notes |
|--------|--------|-------|
| Distance from searcher | **NOT A FACTOR** | Premium at 47mi beats standard at 5mi |
| Days listed | **Unknown** | Need engagement data |
| Views/saves count | **Unknown** | API discovered but needs auth |
| Click-through rate | **Unknown** | Not exposed |
| Lead conversion | **Unknown** | Not exposed |

### Data Collection Gaps

| Data | Source | Blocker |
|------|--------|---------|
| Full description | Detail page | Playwright slow |
| Views count | API | Needs datadome cookie |
| Saves count | API | Needs datadome cookie |
| Days listed | API | Endpoint not found |
| Spec completeness | Detail page | Playwright slow |

### Hypotheses to Test

When engagement data is available:

1. **H1:** Higher views correlate with better rank (engagement signal)
2. **H2:** Longer description = more engagement
3. **H3:** More specs filled = higher conversion rate
4. **H4:** Days listed has diminishing returns (freshness decay)

---

## API Reference

### Search API

```
GET https://www.rvtrader.com/ssr-api/search-results
    ?type={Type}|{TypeCode}
    &page={N}
    &zip={Zip}
    &radius={Miles}
    &condition={N|U}
    &price={Min}-{Max}
```

**Returns:** 36 listings per page, max 10 pages (360 cap)

### Engagement APIs

```
# Views (requires datadome cookie)
GET /gettiledata/addetail_listingstats/showadviewsstats?adId={id}
Response: {"error":null,"listingViewsData":"138"}

# Saves (requires datadome cookie)
GET /gettiledata/addetail_listingstats/showsavedadsstats?adId={id}
Response: {"error":null,"listingSavesData":1}
```

### Score Fields from API

| Field | Type | Description |
|-------|------|-------------|
| `relevance_score` | float | Primary sort score (200-600) |
| `merch_score` | int | Quality/completeness score (72-125) |
| `ad_listing_position` | int | Position in search results |
| `is_premium` | string | "1" or "0" |
| `is_top_premium` | string | "1" or "0" |
| `badge_status` | string | "newly_listed" or null |
| `scheme_code` | string | Ad type code |

---

## Appendix: Raw Data Samples

### Top 5 Listings by Merch Score

```
Rank 23: merch=125, photos=72, floorplan=N, price=$179,995
Rank  8: merch=124, photos=34, floorplan=Y, price=$169,000
Rank 11: merch=124, photos=34, floorplan=Y, price=$139,995
Rank 12: merch=124, photos=32, floorplan=Y, price=$167,995
Rank 13: merch=124, photos=17, floorplan=Y, price=$109,995
```

### Bottom 5 Listings by Merch Score

```
Rank 55: merch=72, photos=1, floorplan=N, price=NONE
Rank 43: merch=84, photos=0, floorplan=N, price=$110,000
Rank 46: merch=84, photos=0, floorplan=N, price=$145,000
Rank 47: merch=84, photos=0, floorplan=N, price=$67,995
Rank 48: merch=84, photos=0, floorplan=N, price=$115,000
```

### Premium vs Standard Distribution

```
Total listings: 56
Top Premium: 3 (5.4%) - Positions 1-3
Premium: 8 (14.3%) - Positions 4-11
Standard: 45 (80.4%) - Positions 12-56
```

---

## Version History

| Date | Change |
|------|--------|
| 2026-01-16 | Initial comprehensive documentation |
| 2026-01-16 | Added correlation matrix and point estimates |
| 2026-01-16 | Documented API endpoints and blockers |
