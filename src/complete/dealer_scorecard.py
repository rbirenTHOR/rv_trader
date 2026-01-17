"""
Dealer Scorecard Generator - Visual HTML Reports with Benchmarking

Generates beautiful, shareable HTML scorecards with comprehensive benchmarking:
- Overall listing quality grade (A-F)
- % Premium listings vs market
- Avg photos vs market benchmark
- % with specs (price, VIN, floorplan, length)
- Avg listing age
- Data completeness score
- Percentile rankings vs all dealers

Usage:
    python dealer_scorecard.py                    # Uses latest ranked_listings CSV
    python dealer_scorecard.py -i input.csv       # Specific input file
    python dealer_scorecard.py --brand Jayco      # Filter to specific Thor brand
    python dealer_scorecard.py --dealer "Thor Motor Coach of Chicago"  # Single dealer
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
import html


# =============================================================================
# CONFIGURATION
# =============================================================================

THOR_BRANDS = {
    'thor': 'Thor Motor Coach',
    'thor motor coach': 'Thor Motor Coach',
    'jayco': 'Jayco',
    'airstream': 'Airstream',
    'tiffin': 'Tiffin Motorhomes',
    'tiffin motorhomes': 'Tiffin Motorhomes',
    'entegra': 'Entegra Coach',
    'entegra coach': 'Entegra Coach',
    'heartland': 'Heartland RV',
    'cruiser': 'Cruiser RV',
    'keystone': 'Keystone RV',
    'dutchmen': 'Dutchmen RV',
}

IMPROVEMENT_FACTORS = {
    'price': {'relevance': 194, 'merch': 5, 'label': 'Add listing price'},
    'vin': {'relevance': 165, 'merch': 6, 'label': 'Add VIN number'},
    'photos_35': {'relevance': 195, 'merch': 30, 'label': 'Add photos to reach 35'},
    'floorplan': {'relevance': 50, 'merch': 12, 'label': 'Add floorplan image'},
    'length': {'relevance': 0, 'merch': 8, 'label': 'Add vehicle length'},
}

RELEVANCE_PER_RANK = 15.0

# Benchmark thresholds
BENCHMARKS = {
    'photos_excellent': 35,
    'photos_good': 25,
    'photos_minimum': 15,
    'premium_target': 20,  # % premium listings target
    'data_completeness_target': 90,  # % target
    'listing_age_warning': 30,  # days
    'listing_age_critical': 60,  # days
}


# =============================================================================
# DATA LOADING
# =============================================================================

def load_csv(csv_path: str) -> List[Dict]:
    """Load and parse CSV file."""
    listings = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['rank'] = safe_int(row.get('rank'))
            row['price'] = safe_float(row.get('price'))
            row['msrp'] = safe_float(row.get('msrp'))
            row['relevance_score'] = safe_float(row.get('relevance_score'))
            row['merch_score'] = safe_float(row.get('merch_score'))
            row['photo_count'] = safe_int(row.get('photo_count')) or 0
            row['length'] = safe_float(row.get('length'))
            row['year'] = safe_int(row.get('year'))

            row['is_premium'] = row.get('is_premium') in ('1', 'True', 'true', True)
            row['is_top_premium'] = row.get('is_top_premium') in ('1', 'True', 'true', True)

            row['has_price'] = bool(row['price'] and row['price'] > 0)
            row['has_vin'] = bool(row.get('vin'))
            row['has_floorplan'] = bool(row.get('floorplan_id'))
            row['has_length'] = bool(row['length'] and row['length'] > 0)

            # Parse create_date for listing age
            row['listing_age_days'] = calculate_listing_age(row.get('create_date'))

            listings.append(row)
    return listings


def safe_int(val) -> Optional[int]:
    if val is None or val == '':
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def safe_float(val) -> Optional[float]:
    if val is None or val == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def calculate_listing_age(create_date_str: str) -> Optional[int]:
    """Calculate listing age in days from create_date string."""
    if not create_date_str:
        return None
    try:
        # Try common formats
        for fmt in ['%Y-%m-%d', '%b %d %Y', '%Y-%m-%dT%H:%M:%S']:
            try:
                create_date = datetime.strptime(create_date_str.split('T')[0], fmt.split('T')[0])
                return (datetime.now() - create_date).days
            except ValueError:
                continue
        return None
    except Exception:
        return None


def identify_thor_brand(make: str) -> Optional[str]:
    """Check if make belongs to Thor Industries."""
    if not make:
        return None
    make_lower = make.lower().strip()
    for pattern, brand_name in THOR_BRANDS.items():
        if pattern in make_lower:
            return brand_name
    return None


# =============================================================================
# BENCHMARKING CALCULATIONS
# =============================================================================

def calculate_market_benchmarks(all_listings: List[Dict]) -> Dict:
    """Calculate market-wide benchmarks for comparison."""
    if not all_listings:
        return {}

    total = len(all_listings)
    ranks = [l['rank'] for l in all_listings if l.get('rank')]
    photos = [l['photo_count'] for l in all_listings]
    ages = [l['listing_age_days'] for l in all_listings if l.get('listing_age_days') is not None]

    premium_count = sum(1 for l in all_listings if l.get('is_premium'))
    with_price = sum(1 for l in all_listings if l.get('has_price'))
    with_vin = sum(1 for l in all_listings if l.get('has_vin'))
    with_floorplan = sum(1 for l in all_listings if l.get('has_floorplan'))
    with_length = sum(1 for l in all_listings if l.get('has_length'))
    photos_35_plus = sum(1 for l in all_listings if l.get('photo_count', 0) >= 35)

    return {
        'total_listings': total,
        'avg_rank': sum(ranks) / len(ranks) if ranks else 50,
        'avg_photos': sum(photos) / len(photos) if photos else 0,
        'avg_age_days': sum(ages) / len(ages) if ages else 0,
        'pct_premium': round(premium_count / total * 100, 1) if total > 0 else 0,
        'pct_price': round(with_price / total * 100, 1) if total > 0 else 0,
        'pct_vin': round(with_vin / total * 100, 1) if total > 0 else 0,
        'pct_floorplan': round(with_floorplan / total * 100, 1) if total > 0 else 0,
        'pct_length': round(with_length / total * 100, 1) if total > 0 else 0,
        'pct_photos_35': round(photos_35_plus / total * 100, 1) if total > 0 else 0,
        'data_completeness': round((with_price + with_vin + with_floorplan + with_length) / (total * 4) * 100, 1) if total > 0 else 0,
    }


def calculate_dealer_benchmarks(dealer_listings: List[Dict], market: Dict) -> Dict:
    """Calculate comprehensive dealer benchmarks with market comparison."""
    if not dealer_listings:
        return {}

    total = len(dealer_listings)
    ranks = [l['rank'] for l in dealer_listings if l.get('rank')]
    photos = [l['photo_count'] for l in dealer_listings]
    ages = [l['listing_age_days'] for l in dealer_listings if l.get('listing_age_days') is not None]
    merch_scores = [l['merch_score'] for l in dealer_listings if l.get('merch_score')]

    premium_count = sum(1 for l in dealer_listings if l.get('is_premium'))
    top_premium_count = sum(1 for l in dealer_listings if l.get('is_top_premium'))
    with_price = sum(1 for l in dealer_listings if l.get('has_price'))
    with_vin = sum(1 for l in dealer_listings if l.get('has_vin'))
    with_floorplan = sum(1 for l in dealer_listings if l.get('has_floorplan'))
    with_length = sum(1 for l in dealer_listings if l.get('has_length'))
    photos_35_plus = sum(1 for l in dealer_listings if l.get('photo_count', 0) >= 35)
    photos_25_plus = sum(1 for l in dealer_listings if l.get('photo_count', 0) >= 25)

    # Age distribution
    age_under_30 = sum(1 for l in dealer_listings if (l.get('listing_age_days') or 0) < 30)
    age_30_60 = sum(1 for l in dealer_listings if 30 <= (l.get('listing_age_days') or 0) < 60)
    age_over_60 = sum(1 for l in dealer_listings if (l.get('listing_age_days') or 0) >= 60)

    # Calculate values
    avg_rank = sum(ranks) / len(ranks) if ranks else 999
    avg_photos = sum(photos) / len(photos) if photos else 0
    avg_age = sum(ages) / len(ages) if ages else 0
    avg_merch = sum(merch_scores) / len(merch_scores) if merch_scores else 0

    pct_premium = round(premium_count / total * 100, 1) if total > 0 else 0
    pct_price = round(with_price / total * 100, 1) if total > 0 else 0
    pct_vin = round(with_vin / total * 100, 1) if total > 0 else 0
    pct_floorplan = round(with_floorplan / total * 100, 1) if total > 0 else 0
    pct_length = round(with_length / total * 100, 1) if total > 0 else 0
    pct_photos_35 = round(photos_35_plus / total * 100, 1) if total > 0 else 0
    pct_photos_25 = round(photos_25_plus / total * 100, 1) if total > 0 else 0

    data_completeness = round((with_price + with_vin + with_floorplan + with_length) / (total * 4) * 100, 1) if total > 0 else 0

    # Comparison to market
    def compare(dealer_val, market_val, lower_is_better=False):
        if market_val == 0:
            return 0
        diff = dealer_val - market_val
        if lower_is_better:
            diff = -diff
        return round(diff, 1)

    return {
        # Core metrics
        'total_listings': total,
        'avg_rank': round(avg_rank, 1),
        'avg_photos': round(avg_photos, 1),
        'avg_age_days': round(avg_age, 1),
        'avg_merch_score': round(avg_merch, 1),

        # Premium breakdown
        'premium_count': premium_count,
        'top_premium_count': top_premium_count,
        'standard_count': total - premium_count,
        'pct_premium': pct_premium,

        # Data completeness
        'with_price': with_price,
        'with_vin': with_vin,
        'with_floorplan': with_floorplan,
        'with_length': with_length,
        'pct_price': pct_price,
        'pct_vin': pct_vin,
        'pct_floorplan': pct_floorplan,
        'pct_length': pct_length,
        'data_completeness': data_completeness,

        # Photo metrics
        'photos_35_plus': photos_35_plus,
        'photos_25_plus': photos_25_plus,
        'pct_photos_35': pct_photos_35,
        'pct_photos_25': pct_photos_25,

        # Age distribution
        'age_under_30': age_under_30,
        'age_30_60': age_30_60,
        'age_over_60': age_over_60,
        'pct_fresh': round(age_under_30 / total * 100, 1) if total > 0 else 0,
        'pct_stale': round(age_over_60 / total * 100, 1) if total > 0 else 0,

        # Market comparison (positive = better than market)
        'vs_market_rank': compare(avg_rank, market.get('avg_rank', 50), lower_is_better=True),
        'vs_market_photos': compare(avg_photos, market.get('avg_photos', 0)),
        'vs_market_premium': compare(pct_premium, market.get('pct_premium', 0)),
        'vs_market_price': compare(pct_price, market.get('pct_price', 0)),
        'vs_market_vin': compare(pct_vin, market.get('pct_vin', 0)),
        'vs_market_floorplan': compare(pct_floorplan, market.get('pct_floorplan', 0)),
        'vs_market_completeness': compare(data_completeness, market.get('data_completeness', 0)),
    }


def calculate_percentile(dealer_value: float, all_dealer_values: List[float], higher_is_better: bool = True) -> int:
    """Calculate percentile rank (0-100) for a dealer metric."""
    if not all_dealer_values:
        return 50
    sorted_values = sorted(all_dealer_values)
    count_below = sum(1 for v in sorted_values if v < dealer_value)
    percentile = int(count_below / len(sorted_values) * 100)
    return percentile if higher_is_better else 100 - percentile


def calculate_grade(benchmarks: Dict, market: Dict) -> Tuple[str, str, float]:
    """Calculate overall grade based on benchmarks."""
    score = 0
    max_score = 100

    # Premium placement (15 pts)
    if benchmarks['pct_premium'] >= 30:
        score += 15
    elif benchmarks['pct_premium'] >= 20:
        score += 12
    elif benchmarks['pct_premium'] >= 10:
        score += 8
    elif benchmarks['pct_premium'] > 0:
        score += 4

    # Data completeness (25 pts)
    score += min(benchmarks['data_completeness'] / 100 * 25, 25)

    # Photo quality (25 pts)
    if benchmarks['avg_photos'] >= 35:
        score += 25
    elif benchmarks['avg_photos'] >= 25:
        score += 20
    elif benchmarks['avg_photos'] >= 15:
        score += 12
    else:
        score += max(0, benchmarks['avg_photos'] / 35 * 12)

    # Rank performance (20 pts) - based on vs market
    rank_diff = benchmarks['vs_market_rank']
    if rank_diff > 10:
        score += 20  # Much better than market
    elif rank_diff > 5:
        score += 16
    elif rank_diff > 0:
        score += 12
    elif rank_diff > -5:
        score += 8
    elif rank_diff > -10:
        score += 4

    # Listing freshness (15 pts)
    if benchmarks['pct_fresh'] >= 60:
        score += 15
    elif benchmarks['pct_fresh'] >= 40:
        score += 12
    elif benchmarks['pct_fresh'] >= 20:
        score += 8
    else:
        score += 4

    # Penalty for stale listings
    if benchmarks['pct_stale'] > 30:
        score -= 10
    elif benchmarks['pct_stale'] > 20:
        score -= 5

    score = max(0, min(100, score))

    if score >= 90:
        return 'A', '#22c55e', score
    elif score >= 80:
        return 'B', '#84cc16', score
    elif score >= 70:
        return 'C', '#eab308', score
    elif score >= 60:
        return 'D', '#f97316', score
    else:
        return 'F', '#ef4444', score


# =============================================================================
# ANALYSIS
# =============================================================================

def calculate_tier_ceilings(listings: List[Dict]) -> Dict[str, int]:
    """Calculate tier ceilings for standard listings."""
    premium_ranks = [l['rank'] for l in listings if l.get('is_premium') and l.get('rank')]
    if premium_ranks:
        return {'standard': max(premium_ranks) + 1}
    return {'standard': 1}


def calculate_listing_actions(listing: Dict) -> List[Dict]:
    """Calculate improvement actions for a listing."""
    actions = []
    photo_count = listing.get('photo_count', 0)

    if not listing.get('has_price'):
        f = IMPROVEMENT_FACTORS['price']
        actions.append({
            'action': f['label'],
            'relevance': f['relevance'],
            'merch': f['merch'],
            'rank_gain': int(f['relevance'] / RELEVANCE_PER_RANK),
            'priority': 1,
        })

    if not listing.get('has_vin'):
        f = IMPROVEMENT_FACTORS['vin']
        actions.append({
            'action': f['label'],
            'relevance': f['relevance'],
            'merch': f['merch'],
            'rank_gain': int(f['relevance'] / RELEVANCE_PER_RANK),
            'priority': 2,
        })

    if photo_count < 35:
        f = IMPROVEMENT_FACTORS['photos_35']
        needed = 35 - photo_count
        actions.append({
            'action': f"{f['label']} ({needed} more)",
            'relevance': f['relevance'],
            'merch': f['merch'],
            'rank_gain': int(f['relevance'] / RELEVANCE_PER_RANK),
            'priority': 3,
        })

    if not listing.get('has_floorplan'):
        f = IMPROVEMENT_FACTORS['floorplan']
        actions.append({
            'action': f['label'],
            'relevance': f['relevance'],
            'merch': f['merch'],
            'rank_gain': int(f['relevance'] / RELEVANCE_PER_RANK),
            'priority': 4,
        })

    if not listing.get('has_length'):
        f = IMPROVEMENT_FACTORS['length']
        actions.append({
            'action': f['label'],
            'relevance': f['relevance'],
            'merch': f['merch'],
            'rank_gain': 0,
            'priority': 5,
        })

    actions.sort(key=lambda x: x['priority'])
    return actions


def calculate_total_improvement(dealer_listings: List[Dict], tier_ceiling: int) -> Dict:
    """Calculate total improvement potential for dealer."""
    total_actions = 0
    total_rank_gain = 0
    top_opportunities = []

    for listing in dealer_listings:
        if listing.get('is_premium'):
            continue

        actions = calculate_listing_actions(listing)
        if not actions:
            continue

        total_actions += len(actions)
        current_rank = listing.get('rank') or 999
        potential_gain = sum(a['rank_gain'] for a in actions)
        realistic_gain = min(potential_gain, max(0, current_rank - tier_ceiling))
        total_rank_gain += realistic_gain

        if realistic_gain > 0 or actions:
            top_opportunities.append({
                'listing': listing,
                'actions': actions,
                'potential_gain': potential_gain,
                'realistic_gain': realistic_gain,
            })

    top_opportunities.sort(key=lambda x: x['realistic_gain'], reverse=True)

    return {
        'total_actions': total_actions,
        'total_rank_gain': total_rank_gain,
        'top_opportunities': top_opportunities[:5],
    }


# =============================================================================
# HTML GENERATION
# =============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dealer Scorecard - {dealer_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #1f2937;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .card {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.15);
            overflow: hidden;
            margin-bottom: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
            color: white;
            padding: 25px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header-left h1 {{ font-size: 1.6rem; margin-bottom: 6px; }}
        .header-left .brand-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            margin-right: 8px;
        }}
        .header-left .location {{ margin-top: 8px; opacity: 0.9; font-size: 0.9rem; }}
        .grade-circle {{
            width: 90px;
            height: 90px;
            border-radius: 50%;
            background: {grade_color};
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }}
        .grade-letter {{ font-size: 2.5rem; font-weight: bold; line-height: 1; }}
        .grade-label {{ font-size: 0.65rem; text-transform: uppercase; letter-spacing: 1px; }}

        /* Benchmark Section */
        .benchmark-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1px;
            background: #e5e7eb;
        }}
        .benchmark {{
            background: white;
            padding: 16px;
            text-align: center;
        }}
        .benchmark-value {{
            font-size: 1.8rem;
            font-weight: bold;
            color: #1e3a5f;
        }}
        .benchmark-value.good {{ color: #22c55e; }}
        .benchmark-value.warning {{ color: #f97316; }}
        .benchmark-value.bad {{ color: #ef4444; }}
        .benchmark-label {{ font-size: 0.8rem; color: #6b7280; margin-top: 2px; }}
        .benchmark-compare {{
            font-size: 0.75rem;
            margin-top: 4px;
            padding: 2px 6px;
            border-radius: 4px;
            display: inline-block;
        }}
        .benchmark-compare.positive {{ background: #dcfce7; color: #166534; }}
        .benchmark-compare.negative {{ background: #fee2e2; color: #991b1b; }}
        .benchmark-compare.neutral {{ background: #f3f4f6; color: #6b7280; }}

        /* Progress Bars */
        .progress-section {{ padding: 20px 25px; }}
        .progress-row {{
            display: flex;
            align-items: center;
            margin-bottom: 12px;
            gap: 15px;
        }}
        .progress-label {{
            width: 140px;
            font-size: 0.85rem;
            font-weight: 500;
            color: #374151;
        }}
        .progress-bar-container {{
            flex: 1;
            height: 24px;
            background: #e5e7eb;
            border-radius: 12px;
            overflow: hidden;
            position: relative;
        }}
        .progress-bar {{
            height: 100%;
            border-radius: 12px;
            transition: width 0.3s ease;
        }}
        .progress-bar.excellent {{ background: linear-gradient(90deg, #22c55e, #16a34a); }}
        .progress-bar.good {{ background: linear-gradient(90deg, #84cc16, #65a30d); }}
        .progress-bar.warning {{ background: linear-gradient(90deg, #eab308, #ca8a04); }}
        .progress-bar.poor {{ background: linear-gradient(90deg, #f97316, #ea580c); }}
        .progress-bar.bad {{ background: linear-gradient(90deg, #ef4444, #dc2626); }}
        .progress-value {{
            width: 60px;
            text-align: right;
            font-weight: 600;
            font-size: 0.9rem;
        }}
        .progress-benchmark {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #1e3a5f;
        }}
        .progress-benchmark::after {{
            content: 'MKT';
            position: absolute;
            top: -16px;
            left: -10px;
            font-size: 0.6rem;
            color: #1e3a5f;
            font-weight: 600;
        }}

        .section {{
            padding: 20px 25px;
            border-top: 1px solid #e5e7eb;
        }}
        .section-title {{
            font-size: 1rem;
            font-weight: 600;
            color: #1e3a5f;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        /* Quick Wins Grid */
        .quick-wins {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }}
        .quick-win {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .quick-win.complete {{ background: #f0fdf4; border-color: #86efac; }}
        .quick-win.incomplete {{ background: #fef3c7; border-color: #fcd34d; }}
        .quick-win-icon {{ font-size: 1.3rem; }}
        .quick-win-label {{ font-weight: 500; color: #374151; font-size: 0.9rem; }}
        .quick-win-stat {{ font-size: 0.8rem; color: #6b7280; }}

        /* Opportunities */
        .opportunity {{
            background: #f8fafc;
            border-radius: 8px;
            padding: 12px 15px;
            margin-bottom: 10px;
        }}
        .opp-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .opp-title {{ font-weight: 600; color: #1f2937; font-size: 0.95rem; }}
        .opp-badges {{ display: flex; gap: 6px; }}
        .opp-rank {{
            background: #1e3a5f;
            color: white;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
        }}
        .opp-gain {{
            background: #22c55e;
            color: white;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
        }}
        .opp-actions {{ display: flex; flex-wrap: wrap; gap: 5px; }}
        .action-chip {{
            background: #e0e7ff;
            color: #4338ca;
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
        }}

        /* Listings Table */
        .listing-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
        .listing-table th {{
            background: #f1f5f9;
            padding: 10px 8px;
            text-align: left;
            font-size: 0.7rem;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
        }}
        .listing-table td {{ padding: 10px 8px; border-bottom: 1px solid #e2e8f0; }}
        .status-badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 500;
        }}
        .status-premium {{ background: #fef3c7; color: #92400e; }}
        .status-good {{ background: #dcfce7; color: #166534; }}
        .status-needs-work {{ background: #fee2e2; color: #991b1b; }}
        .check {{ color: #22c55e; }}
        .cross {{ color: #ef4444; }}

        .summary-box {{
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 15px;
        }}
        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            text-align: center;
        }}
        .summary-stat-value {{ font-size: 1.5rem; font-weight: bold; }}
        .summary-stat-label {{ font-size: 0.75rem; opacity: 0.9; }}

        .footer {{
            text-align: center;
            padding: 15px;
            color: #9ca3af;
            font-size: 0.8rem;
        }}

        @media print {{
            body {{ background: white; padding: 0; }}
            .card {{ box-shadow: none; border: 1px solid #e5e7eb; }}
        }}
        @media (max-width: 768px) {{
            .header {{ flex-direction: column; text-align: center; gap: 15px; }}
            .benchmark-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .quick-wins {{ grid-template-columns: 1fr; }}
            .summary-stats {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <div class="header-left">
                    <h1>{dealer_name}</h1>
                    <span class="brand-badge">{thor_brand}</span>
                    <span class="brand-badge">{total_listings} Listings</span>
                    <div class="location">{location} | {phone}</div>
                </div>
                <div class="grade-circle">
                    <span class="grade-letter">{grade}</span>
                    <span class="grade-label">Score: {score:.0f}</span>
                </div>
            </div>

            <!-- Key Benchmarks -->
            <div class="benchmark-grid">
                <div class="benchmark">
                    <div class="benchmark-value {rank_class}">{avg_rank}</div>
                    <div class="benchmark-label">Avg Rank</div>
                    <div class="benchmark-compare {rank_compare_class}">{rank_compare}</div>
                </div>
                <div class="benchmark">
                    <div class="benchmark-value {premium_class}">{pct_premium}%</div>
                    <div class="benchmark-label">Premium</div>
                    <div class="benchmark-compare {premium_compare_class}">{premium_compare}</div>
                </div>
                <div class="benchmark">
                    <div class="benchmark-value {photos_class}">{avg_photos}</div>
                    <div class="benchmark-label">Avg Photos</div>
                    <div class="benchmark-compare {photos_compare_class}">{photos_compare}</div>
                </div>
                <div class="benchmark">
                    <div class="benchmark-value {completeness_class}">{data_completeness}%</div>
                    <div class="benchmark-label">Data Complete</div>
                    <div class="benchmark-compare {completeness_compare_class}">{completeness_compare}</div>
                </div>
            </div>

            <!-- Progress Bars -->
            <div class="progress-section">
                <div class="section-title">Data Completeness vs Market</div>
                {progress_bars_html}
            </div>

            <!-- Quick Quality Check -->
            <div class="section">
                <div class="section-title">Quick Quality Check</div>
                <div class="quick-wins">
                    <div class="quick-win {price_status}">
                        <div class="quick-win-icon">{price_icon}</div>
                        <div>
                            <div class="quick-win-label">Listing Prices</div>
                            <div class="quick-win-stat">{with_price}/{total_listings} ({pct_price}%)</div>
                        </div>
                    </div>
                    <div class="quick-win {vin_status}">
                        <div class="quick-win-icon">{vin_icon}</div>
                        <div>
                            <div class="quick-win-label">VIN Numbers</div>
                            <div class="quick-win-stat">{with_vin}/{total_listings} ({pct_vin}%)</div>
                        </div>
                    </div>
                    <div class="quick-win {floorplan_status}">
                        <div class="quick-win-icon">{floorplan_icon}</div>
                        <div>
                            <div class="quick-win-label">Floorplan Images</div>
                            <div class="quick-win-stat">{with_floorplan}/{total_listings} ({pct_floorplan}%)</div>
                        </div>
                    </div>
                    <div class="quick-win {photos_35_status}">
                        <div class="quick-win-icon">{photos_35_icon}</div>
                        <div>
                            <div class="quick-win-label">35+ Photos</div>
                            <div class="quick-win-stat">{photos_35_plus}/{total_listings} ({pct_photos_35}%)</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Listing Age Distribution -->
            <div class="section">
                <div class="section-title">Listing Age Distribution</div>
                <div class="summary-box">
                    <div class="summary-stats">
                        <div>
                            <div class="summary-stat-value">{age_under_30}</div>
                            <div class="summary-stat-label">Fresh (&lt;30 days)</div>
                        </div>
                        <div>
                            <div class="summary-stat-value">{age_30_60}</div>
                            <div class="summary-stat-label">Moderate (30-60)</div>
                        </div>
                        <div>
                            <div class="summary-stat-value">{age_over_60}</div>
                            <div class="summary-stat-label">Stale (&gt;60 days)</div>
                        </div>
                        <div>
                            <div class="summary-stat-value">{avg_age_days:.0f}</div>
                            <div class="summary-stat-label">Avg Age (days)</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Improvement Opportunities -->
            <div class="section">
                <div class="section-title">Top Improvement Opportunities</div>
                <div class="summary-box">
                    <div class="summary-stats">
                        <div>
                            <div class="summary-stat-value">{total_actions}</div>
                            <div class="summary-stat-label">Actions Needed</div>
                        </div>
                        <div>
                            <div class="summary-stat-value">+{total_rank_gain}</div>
                            <div class="summary-stat-label">Positions to Gain</div>
                        </div>
                        <div>
                            <div class="summary-stat-value">{premium_count}</div>
                            <div class="summary-stat-label">Premium Listings</div>
                        </div>
                        <div>
                            <div class="summary-stat-value">{standard_count}</div>
                            <div class="summary-stat-label">Standard Listings</div>
                        </div>
                    </div>
                </div>
                {opportunities_html}
            </div>

            <!-- All Listings -->
            <div class="section">
                <div class="section-title">All Listings</div>
                <table class="listing-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Year</th>
                            <th>Model</th>
                            <th>Price</th>
                            <th>Photos</th>
                            <th>Age</th>
                            <th>VIN</th>
                            <th>FP</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {listings_html}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="footer">
            Generated {timestamp} | RVTrader Ranking Analysis | Thor Industries
        </div>
    </div>
</body>
</html>
"""


def generate_progress_bar_html(label: str, dealer_pct: float, market_pct: float) -> str:
    """Generate HTML for a progress bar with market benchmark."""
    # Determine bar class
    if dealer_pct >= 90:
        bar_class = 'excellent'
    elif dealer_pct >= 75:
        bar_class = 'good'
    elif dealer_pct >= 50:
        bar_class = 'warning'
    elif dealer_pct >= 25:
        bar_class = 'poor'
    else:
        bar_class = 'bad'

    # Market benchmark position (capped at 100%)
    market_pos = min(market_pct, 100)

    return f"""
    <div class="progress-row">
        <div class="progress-label">{label}</div>
        <div class="progress-bar-container">
            <div class="progress-bar {bar_class}" style="width: {min(dealer_pct, 100)}%"></div>
            <div class="progress-benchmark" style="left: {market_pos}%"></div>
        </div>
        <div class="progress-value">{dealer_pct:.0f}%</div>
    </div>
    """


def generate_opportunity_html(opp: Dict) -> str:
    """Generate HTML for a single opportunity."""
    listing = opp['listing']
    actions = opp['actions']

    year = listing.get('year', 'N/A')
    model = listing.get('model', 'Unknown')[:28]
    rank = listing.get('rank', 'N/A')
    gain = opp['realistic_gain']

    actions_html = ''.join(
        f'<span class="action-chip">{html.escape(a["action"][:35])}</span>'
        for a in actions[:3]
    )

    gain_html = f'<span class="opp-gain">+{gain} positions</span>' if gain > 0 else ''

    return f"""
    <div class="opportunity">
        <div class="opp-header">
            <div class="opp-title">{year} {html.escape(model)}</div>
            <div class="opp-badges">
                <span class="opp-rank">Rank #{rank}</span>
                {gain_html}
            </div>
        </div>
        <div class="opp-actions">{actions_html}</div>
    </div>
    """


def generate_listing_row_html(listing: Dict) -> str:
    """Generate HTML table row for a listing."""
    rank = listing.get('rank', 'N/A')
    year = listing.get('year', 'N/A')
    model = html.escape(str(listing.get('model', 'Unknown'))[:22])
    price = f"${listing.get('price', 0):,.0f}" if listing.get('has_price') else '<span class="cross">-</span>'
    photos = listing.get('photo_count', 0)
    age = listing.get('listing_age_days')
    age_str = f"{age}d" if age is not None else '-'

    vin_icon = '<span class="check">Y</span>' if listing.get('has_vin') else '<span class="cross">N</span>'
    fp_icon = '<span class="check">Y</span>' if listing.get('has_floorplan') else '<span class="cross">N</span>'

    actions = calculate_listing_actions(listing)
    if listing.get('is_premium'):
        status = '<span class="status-badge status-premium">Premium</span>'
    elif len(actions) == 0:
        status = '<span class="status-badge status-good">Complete</span>'
    else:
        status = '<span class="status-badge status-needs-work">Fix</span>'

    photo_class = 'good' if photos >= 35 else 'warning' if photos >= 20 else 'bad'
    age_class = '' if age is None else ('good' if age < 30 else 'warning' if age < 60 else 'bad')

    return f"""
    <tr>
        <td>{rank}</td>
        <td>{year}</td>
        <td>{model}</td>
        <td>{price}</td>
        <td><span class="{photo_class}">{photos}</span></td>
        <td><span class="{age_class}">{age_str}</span></td>
        <td>{vin_icon}</td>
        <td>{fp_icon}</td>
        <td>{status}</td>
    </tr>
    """


def generate_dealer_scorecard(dealer_name: str, dealer_listings: List[Dict],
                               market: Dict, tier_ceiling: int, thor_brand: str) -> str:
    """Generate complete HTML scorecard for a dealer."""

    benchmarks = calculate_dealer_benchmarks(dealer_listings, market)
    grade, grade_color, score = calculate_grade(benchmarks, market)
    improvement = calculate_total_improvement(dealer_listings, tier_ceiling)

    first = dealer_listings[0] if dealer_listings else {}
    location = f"{first.get('city', 'Unknown')}, {first.get('state', 'XX')}"
    phone = first.get('dealer_phone', 'N/A')

    # Progress bars
    progress_bars = [
        ('Has Price', benchmarks['pct_price'], market.get('pct_price', 0)),
        ('Has VIN', benchmarks['pct_vin'], market.get('pct_vin', 0)),
        ('Has Floorplan', benchmarks['pct_floorplan'], market.get('pct_floorplan', 0)),
        ('Has Length', benchmarks['pct_length'], market.get('pct_length', 0)),
        ('35+ Photos', benchmarks['pct_photos_35'], market.get('pct_photos_35', 0)),
    ]
    progress_bars_html = ''.join(generate_progress_bar_html(l, d, m) for l, d, m in progress_bars)

    # Opportunities
    opportunities_html = ''.join(
        generate_opportunity_html(opp) for opp in improvement['top_opportunities']
    )
    if not opportunities_html:
        opportunities_html = '<p style="color: #6b7280; text-align: center; padding: 20px;">All listings are fully optimized!</p>'

    # Listings table
    sorted_listings = sorted(dealer_listings, key=lambda x: x.get('rank') or 999)
    listings_html = ''.join(generate_listing_row_html(l) for l in sorted_listings)

    # Helper functions
    def get_status(pct):
        return 'complete' if pct >= 90 else 'incomplete'

    def get_icon(pct):
        return '&#10004;' if pct >= 90 else '&#9888;'

    def get_class(val, good_threshold, warn_threshold, lower_is_better=False):
        if lower_is_better:
            if val <= good_threshold:
                return 'good'
            elif val <= warn_threshold:
                return 'warning'
            return 'bad'
        else:
            if val >= good_threshold:
                return 'good'
            elif val >= warn_threshold:
                return 'warning'
            return 'bad'

    def get_compare(val, label='vs mkt'):
        if val > 0:
            return f'+{val:.1f} {label}', 'positive'
        elif val < 0:
            return f'{val:.1f} {label}', 'negative'
        return f'= {label}', 'neutral'

    rank_compare, rank_compare_class = get_compare(benchmarks['vs_market_rank'])
    premium_compare, premium_compare_class = get_compare(benchmarks['vs_market_premium'], 'pts')
    photos_compare, photos_compare_class = get_compare(benchmarks['vs_market_photos'])
    completeness_compare, completeness_compare_class = get_compare(benchmarks['vs_market_completeness'], 'pts')

    return HTML_TEMPLATE.format(
        dealer_name=html.escape(dealer_name),
        thor_brand=html.escape(thor_brand),
        location=html.escape(location),
        phone=html.escape(phone),
        grade=grade,
        grade_color=grade_color,
        score=score,
        total_listings=benchmarks['total_listings'],

        # Benchmarks
        avg_rank=benchmarks['avg_rank'],
        rank_class=get_class(benchmarks['vs_market_rank'], 5, 0),
        rank_compare=rank_compare,
        rank_compare_class=rank_compare_class,

        pct_premium=benchmarks['pct_premium'],
        premium_class=get_class(benchmarks['pct_premium'], 20, 10),
        premium_compare=premium_compare,
        premium_compare_class=premium_compare_class,

        avg_photos=benchmarks['avg_photos'],
        photos_class=get_class(benchmarks['avg_photos'], 35, 25),
        photos_compare=photos_compare,
        photos_compare_class=photos_compare_class,

        data_completeness=benchmarks['data_completeness'],
        completeness_class=get_class(benchmarks['data_completeness'], 90, 70),
        completeness_compare=completeness_compare,
        completeness_compare_class=completeness_compare_class,

        progress_bars_html=progress_bars_html,

        # Quick wins
        with_price=benchmarks['with_price'],
        pct_price=benchmarks['pct_price'],
        price_status=get_status(benchmarks['pct_price']),
        price_icon=get_icon(benchmarks['pct_price']),

        with_vin=benchmarks['with_vin'],
        pct_vin=benchmarks['pct_vin'],
        vin_status=get_status(benchmarks['pct_vin']),
        vin_icon=get_icon(benchmarks['pct_vin']),

        with_floorplan=benchmarks['with_floorplan'],
        pct_floorplan=benchmarks['pct_floorplan'],
        floorplan_status=get_status(benchmarks['pct_floorplan']),
        floorplan_icon=get_icon(benchmarks['pct_floorplan']),

        photos_35_plus=benchmarks['photos_35_plus'],
        pct_photos_35=benchmarks['pct_photos_35'],
        photos_35_status=get_status(benchmarks['pct_photos_35']),
        photos_35_icon=get_icon(benchmarks['pct_photos_35']),

        # Age distribution
        age_under_30=benchmarks['age_under_30'],
        age_30_60=benchmarks['age_30_60'],
        age_over_60=benchmarks['age_over_60'],
        avg_age_days=benchmarks['avg_age_days'],

        # Improvement
        total_actions=improvement['total_actions'],
        total_rank_gain=improvement['total_rank_gain'],
        premium_count=benchmarks['premium_count'],
        standard_count=benchmarks['standard_count'],
        opportunities_html=opportunities_html,
        listings_html=listings_html,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M'),
    )


# =============================================================================
# INDEX PAGE
# =============================================================================

def generate_index_page(by_dealer: Dict, all_listings: List[Dict], market: Dict, output_dir: Path) -> str:
    """Generate comprehensive index page with market benchmarks."""

    rows = []
    for dealer_name, listings in sorted(by_dealer.items()):
        benchmarks = calculate_dealer_benchmarks(listings, market)
        grade, grade_color, score = calculate_grade(benchmarks, market)

        brand_counts = defaultdict(int)
        for l in listings:
            brand_counts[l.get('thor_brand', 'Unknown')] += 1
        primary_brand = max(brand_counts.items(), key=lambda x: x[1])[0]

        safe_name = dealer_name.replace(' ', '_').replace('/', '_').replace('\\', '_')[:50]

        rows.append(f"""
        <tr>
            <td><a href="scorecard_{safe_name}_*.html" style="color: #2563eb;">{html.escape(dealer_name)}</a></td>
            <td>{html.escape(primary_brand)}</td>
            <td>{benchmarks['total_listings']}</td>
            <td><span style="font-weight: bold; color: {grade_color};">{grade}</span></td>
            <td>{benchmarks['avg_rank']}</td>
            <td>{benchmarks['pct_premium']}%</td>
            <td>{benchmarks['avg_photos']}</td>
            <td>{benchmarks['data_completeness']}%</td>
            <td>{benchmarks['avg_age_days']:.0f}d</td>
        </tr>
        """)

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Dealer Scorecards - Benchmarking Dashboard</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 30px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); color: white; padding: 25px; border-radius: 12px 12px 0 0; }}
            .header h1 {{ margin: 0 0 10px 0; }}
            .benchmarks {{
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 15px;
                margin-top: 15px;
            }}
            .bench {{ background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px; text-align: center; }}
            .bench-value {{ font-size: 1.5rem; font-weight: bold; }}
            .bench-label {{ font-size: 0.8rem; opacity: 0.9; }}
            .card {{ background: white; border-radius: 0 0 12px 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ background: #f1f5f9; padding: 12px; text-align: left; font-size: 0.8rem; font-weight: 600; color: #64748b; text-transform: uppercase; }}
            td {{ padding: 12px; border-bottom: 1px solid #e5e7eb; }}
            tr:hover {{ background: #f9fafb; }}
            a {{ text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Thor Dealer Benchmarking Dashboard</h1>
                <p>Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | {len(by_dealer)} Dealers | {market['total_listings']} Total Listings</p>
                <div class="benchmarks">
                    <div class="bench">
                        <div class="bench-value">{market['avg_rank']:.1f}</div>
                        <div class="bench-label">Market Avg Rank</div>
                    </div>
                    <div class="bench">
                        <div class="bench-value">{market['pct_premium']}%</div>
                        <div class="bench-label">Market % Premium</div>
                    </div>
                    <div class="bench">
                        <div class="bench-value">{market['avg_photos']:.1f}</div>
                        <div class="bench-label">Market Avg Photos</div>
                    </div>
                    <div class="bench">
                        <div class="bench-value">{market['data_completeness']}%</div>
                        <div class="bench-label">Market Data Complete</div>
                    </div>
                    <div class="bench">
                        <div class="bench-value">{market['avg_age_days']:.0f}d</div>
                        <div class="bench-label">Market Avg Age</div>
                    </div>
                </div>
            </div>
            <div class="card">
                <table>
                    <thead>
                        <tr>
                            <th>Dealer</th>
                            <th>Brand</th>
                            <th>Listings</th>
                            <th>Grade</th>
                            <th>Avg Rank</th>
                            <th>% Premium</th>
                            <th>Avg Photos</th>
                            <th>Data %</th>
                            <th>Avg Age</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """


# =============================================================================
# MAIN
# =============================================================================

def generate_scorecards(csv_path: str, output_dir: str = None,
                        brand_filter: str = None, dealer_filter: str = None) -> List[str]:
    """Generate dealer scorecards with comprehensive benchmarking."""
    print(f"\nLoading data from: {csv_path}")
    listings = load_csv(csv_path)
    print(f"Total listings loaded: {len(listings)}")

    for listing in listings:
        listing['thor_brand'] = identify_thor_brand(listing.get('make', ''))

    thor_listings = [l for l in listings if l.get('thor_brand')]
    print(f"Thor brand listings: {len(thor_listings)}")

    if brand_filter:
        thor_listings = [l for l in thor_listings if l['thor_brand'].lower() == brand_filter.lower()]
        print(f"After brand filter '{brand_filter}': {len(thor_listings)}")

    if dealer_filter:
        thor_listings = [l for l in thor_listings if dealer_filter.lower() in l.get('dealer_name', '').lower()]
        print(f"After dealer filter '{dealer_filter}': {len(thor_listings)}")

    if not thor_listings:
        print("No listings found matching filters!")
        return []

    # Calculate market benchmarks
    market = calculate_market_benchmarks(listings)
    tier_ceilings = calculate_tier_ceilings(listings)
    tier_ceiling = tier_ceilings.get('standard', 1)

    print(f"\nMarket Benchmarks:")
    print(f"  Avg Rank: {market['avg_rank']:.1f}")
    print(f"  % Premium: {market['pct_premium']}%")
    print(f"  Avg Photos: {market['avg_photos']:.1f}")
    print(f"  Data Completeness: {market['data_completeness']}%")
    print(f"  Avg Age: {market['avg_age_days']:.0f} days")

    # Group by dealer
    by_dealer = defaultdict(list)
    for listing in thor_listings:
        dealer = listing.get('dealer_name') or 'Unknown Dealer'
        by_dealer[dealer].append(listing)

    print(f"\nGenerating scorecards for {len(by_dealer)} dealers...")

    if output_dir is None:
        output_dir = Path(__file__).parent.parent.parent / 'output' / 'scorecards'
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    for dealer_name, dealer_listings in sorted(by_dealer.items()):
        brand_counts = defaultdict(int)
        for l in dealer_listings:
            brand_counts[l.get('thor_brand', 'Unknown')] += 1
        primary_brand = max(brand_counts.items(), key=lambda x: x[1])[0]

        html_content = generate_dealer_scorecard(
            dealer_name=dealer_name,
            dealer_listings=dealer_listings,
            market=market,
            tier_ceiling=tier_ceiling,
            thor_brand=primary_brand,
        )

        safe_name = dealer_name.replace(' ', '_').replace('/', '_').replace('\\', '_')[:50]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = output_dir / f"scorecard_{safe_name}_{timestamp}.html"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        generated.append(str(file_path))
        print(f"  Created: {file_path.name}")

    # Generate index page
    index_html = generate_index_page(by_dealer, listings, market, output_dir)
    index_path = output_dir / f"index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_html)
    generated.append(str(index_path))
    print(f"  Created: {index_path.name} (index)")

    return generated


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate visual HTML dealer scorecards with benchmarking'
    )
    parser.add_argument('--input', '-i', help='Input ranked_listings CSV')
    parser.add_argument('--output', '-o', help='Output directory for scorecards')
    parser.add_argument('--brand', '-b', help='Filter to specific Thor brand')
    parser.add_argument('--dealer', '-d', help='Filter to specific dealer')
    args = parser.parse_args()

    if args.input:
        csv_path = Path(args.input)
    else:
        output_dir = Path(__file__).parent.parent.parent / 'output'
        csv_files = sorted(output_dir.glob('ranked_listings*.csv'), reverse=True)
        if not csv_files:
            print("Error: No ranked_listings CSV files found in output/")
            return
        csv_path = csv_files[0]

    generated = generate_scorecards(
        str(csv_path),
        output_dir=args.output,
        brand_filter=args.brand,
        dealer_filter=args.dealer,
    )

    print(f"\nDone! Generated {len(generated)} files.")
    if generated:
        print(f"Open in browser: file://{generated[-1]}")


if __name__ == '__main__':
    main()
