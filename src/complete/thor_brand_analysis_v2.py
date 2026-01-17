"""
Thor Industries Brand Analysis v2 - Comprehensive Manufacturer Report
Generates actionable CSV with per-listing improvement recommendations.

Key features:
- Tier-constrained ranking improvements (can't pass premium without premium)
- Correlation-weighted priority scoring
- Grouped by: Thor Brand → Dealer Group → Dealer Name
- Single comprehensive CSV output for manufacturer action
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, List, Any


# =============================================================================
# CONFIGURATION
# =============================================================================

# Thor Industries brands (case-insensitive matching)
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

# Point values from ranking algorithm analysis (docs/RANKING_ALGORITHM.md)
# Correlations used for priority weighting
IMPROVEMENT_FACTORS = {
    'price': {
        'relevance_pts': 194,
        'merch_pts': 5,
        'rank_correlation': 0.840,  # Strongest correlation with rank
        'merch_correlation': 0.298,
        'difficulty': 'Easy',
    },
    'vin': {
        'relevance_pts': 165,
        'merch_pts': 6,
        'rank_correlation': 0.689,
        'merch_correlation': 0.412,
        'difficulty': 'Easy',
    },
    'photos_to_35': {
        'relevance_pts': 195,
        'merch_pts': 30,
        'rank_correlation': 0.611,
        'merch_correlation': 0.658,
        'difficulty': 'Medium',
    },
    'photos_20_to_35': {
        'relevance_pts': 95,  # Partial gain (already have 20+)
        'merch_pts': 15,
        'rank_correlation': 0.611,
        'merch_correlation': 0.658,
        'difficulty': 'Medium',
    },
    'floorplan': {
        'relevance_pts': 50,
        'merch_pts': 12,
        'rank_correlation': 0.300,  # Estimated
        'merch_correlation': 0.554,
        'difficulty': 'Easy',
    },
    'length': {
        'relevance_pts': 0,
        'merch_pts': 8,
        'rank_correlation': 0.100,
        'merch_correlation': 0.702,
        'difficulty': 'Easy',
    },
}

# Conversion factor: relevance points to rank positions
RELEVANCE_PER_RANK = 15.0

# Merch score estimation (from docs/MERCH_SCORE.md)
MERCH_BASE_SCORE = 72
MERCH_PHOTO_FACTOR = 0.5  # ~0.5 pts per photo, cap at 33
MERCH_PHOTO_CAP = 33


# =============================================================================
# DATA LOADING
# =============================================================================

def load_ranked_listings(csv_path: str) -> List[Dict]:
    """Load ranked listings from CSV file."""
    listings = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric fields
            row['rank'] = safe_int(row.get('rank'))
            row['price'] = safe_float(row.get('price'))
            row['msrp'] = safe_float(row.get('msrp'))
            row['relevance_score'] = safe_float(row.get('relevance_score'))
            row['merch_score'] = safe_float(row.get('merch_score'))
            row['photo_count'] = safe_int(row.get('photo_count')) or 0
            row['length'] = safe_float(row.get('length'))
            row['mileage'] = safe_int(row.get('mileage'))
            row['year'] = safe_int(row.get('year'))

            # Boolean conversions
            row['is_premium'] = row.get('is_premium') in ('1', 'True', 'true', True)
            row['is_top_premium'] = row.get('is_top_premium') in ('1', 'True', 'true', True)
            row['trusted_partner'] = row.get('trusted_partner') in ('1', 'True', 'true', True)

            # Derived booleans
            row['has_price'] = bool(row['price'] and row['price'] > 0)
            row['has_vin'] = bool(row.get('vin'))
            row['has_floorplan'] = bool(row.get('floorplan_id'))
            row['has_length'] = bool(row['length'] and row['length'] > 0)

            listings.append(row)
    return listings


def safe_int(val) -> Optional[int]:
    """Safely convert to int."""
    if val is None or val == '':
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def safe_float(val) -> Optional[float]:
    """Safely convert to float."""
    if val is None or val == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# =============================================================================
# THOR BRAND IDENTIFICATION
# =============================================================================

def identify_thor_brand(make: str) -> Optional[str]:
    """Check if a make belongs to Thor Industries family."""
    if not make:
        return None
    make_lower = make.lower().strip()
    for pattern, brand_name in THOR_BRANDS.items():
        if pattern in make_lower:
            return brand_name
    return None


# =============================================================================
# TIER ANALYSIS
# =============================================================================

def get_tier(listing: Dict) -> str:
    """Determine listing tier."""
    if listing.get('is_top_premium'):
        return 'top_premium'
    elif listing.get('is_premium'):
        return 'premium'
    return 'standard'


def calculate_tier_ceilings(listings: List[Dict]) -> Dict[str, int]:
    """
    Calculate the best achievable rank for each tier.

    Standard listings cannot pass premium listings.
    Premium listings cannot pass top_premium listings.
    """
    top_premium_ranks = [l['rank'] for l in listings if l.get('is_top_premium') and l.get('rank')]
    premium_ranks = [l['rank'] for l in listings if l.get('is_premium') and not l.get('is_top_premium') and l.get('rank')]

    # Top premium ceiling is always 1
    top_premium_ceiling = 1

    # Premium ceiling is after the last top_premium
    if top_premium_ranks:
        premium_ceiling = max(top_premium_ranks) + 1
    else:
        premium_ceiling = 1

    # Standard ceiling is after the last premium
    all_premium_ranks = [l['rank'] for l in listings if l.get('is_premium') and l.get('rank')]
    if all_premium_ranks:
        standard_ceiling = max(all_premium_ranks) + 1
    else:
        standard_ceiling = 1

    return {
        'top_premium': top_premium_ceiling,
        'premium': premium_ceiling,
        'standard': standard_ceiling,
    }


# =============================================================================
# MERCH SCORE ESTIMATION
# =============================================================================

def estimate_merch_score(listing: Dict) -> int:
    """
    Estimate merch score based on known factors.
    From docs/MERCH_SCORE.md formula.
    """
    score = MERCH_BASE_SCORE

    # Photo contribution (capped)
    photo_count = listing.get('photo_count', 0)
    photo_pts = min(photo_count * MERCH_PHOTO_FACTOR, MERCH_PHOTO_CAP)
    score += photo_pts

    # Floorplan
    if listing.get('has_floorplan'):
        score += 12

    # VIN
    if listing.get('has_vin'):
        score += 6

    # Price
    if listing.get('has_price'):
        score += 5

    # Length
    if listing.get('has_length'):
        score += 8

    return min(int(score), 125)  # Cap at observed max


def get_quality_tier(merch_score: Optional[float]) -> str:
    """Categorize merch score into quality tier."""
    if not merch_score:
        return 'Unknown'
    if merch_score >= 121:
        return 'Excellent'
    elif merch_score >= 111:
        return 'High'
    elif merch_score >= 91:
        return 'Medium'
    return 'Low'


# =============================================================================
# IMPROVEMENT CALCULATION
# =============================================================================

def calculate_improvements(listing: Dict) -> List[Dict]:
    """
    Calculate all possible improvements for a listing.
    Returns list of actions sorted by correlation-weighted impact.
    """
    improvements = []

    photo_count = listing.get('photo_count', 0)

    # Price
    if not listing.get('has_price'):
        factor = IMPROVEMENT_FACTORS['price']
        improvements.append({
            'action': 'Add price',
            'action_key': 'price',
            'relevance_gain': factor['relevance_pts'],
            'merch_gain': factor['merch_pts'],
            'rank_correlation': factor['rank_correlation'],
            'merch_correlation': factor['merch_correlation'],
            'difficulty': factor['difficulty'],
            'detail': '',
        })

    # VIN
    if not listing.get('has_vin'):
        factor = IMPROVEMENT_FACTORS['vin']
        improvements.append({
            'action': 'Add VIN',
            'action_key': 'vin',
            'relevance_gain': factor['relevance_pts'],
            'merch_gain': factor['merch_pts'],
            'rank_correlation': factor['rank_correlation'],
            'merch_correlation': factor['merch_correlation'],
            'difficulty': factor['difficulty'],
            'detail': '',
        })

    # Photos
    if photo_count < 35:
        photos_needed = 35 - photo_count
        if photo_count < 20:
            factor = IMPROVEMENT_FACTORS['photos_to_35']
        else:
            factor = IMPROVEMENT_FACTORS['photos_20_to_35']

        improvements.append({
            'action': f'Add {photos_needed} photos to reach 35',
            'action_key': 'photos',
            'relevance_gain': factor['relevance_pts'],
            'merch_gain': factor['merch_pts'],
            'rank_correlation': factor['rank_correlation'],
            'merch_correlation': factor['merch_correlation'],
            'difficulty': factor['difficulty'],
            'detail': f'{photos_needed} needed',
        })

    # Floorplan
    if not listing.get('has_floorplan'):
        factor = IMPROVEMENT_FACTORS['floorplan']
        improvements.append({
            'action': 'Add floorplan image',
            'action_key': 'floorplan',
            'relevance_gain': factor['relevance_pts'],
            'merch_gain': factor['merch_pts'],
            'rank_correlation': factor['rank_correlation'],
            'merch_correlation': factor['merch_correlation'],
            'difficulty': factor['difficulty'],
            'detail': '',
        })

    # Length
    if not listing.get('has_length'):
        factor = IMPROVEMENT_FACTORS['length']
        improvements.append({
            'action': 'Add vehicle length',
            'action_key': 'length',
            'relevance_gain': factor['relevance_pts'],
            'merch_gain': factor['merch_pts'],
            'rank_correlation': factor['rank_correlation'],
            'merch_correlation': factor['merch_correlation'],
            'difficulty': factor['difficulty'],
            'detail': '',
        })

    # Calculate priority score for each improvement
    for imp in improvements:
        imp['priority_score'] = calculate_action_priority(imp)

    # Sort by priority (highest first)
    improvements.sort(key=lambda x: x['priority_score'], reverse=True)

    return improvements


def calculate_action_priority(improvement: Dict) -> float:
    """
    Calculate priority score for an action using correlation weights.
    Higher score = higher priority.
    """
    relevance_pts = improvement['relevance_gain']
    merch_pts = improvement['merch_gain']
    rank_corr = improvement['rank_correlation']
    merch_corr = improvement['merch_correlation']

    # Weighted impact: relevance weighted by rank correlation,
    # merch weighted by merch correlation (scaled up since merch pts are smaller)
    weighted_impact = (relevance_pts * rank_corr) + (merch_pts * merch_corr * 3)

    # Difficulty multiplier (easy actions get bonus)
    difficulty_mult = {'Easy': 1.5, 'Medium': 1.0, 'Cost': 0.3}
    weighted_impact *= difficulty_mult.get(improvement['difficulty'], 1.0)

    return weighted_impact


def calculate_listing_analysis(listing: Dict, tier_ceilings: Dict) -> Dict:
    """
    Calculate full analysis for a single listing.
    Returns dict with all calculated fields.
    """
    current_rank = listing.get('rank') or 999
    tier = get_tier(listing)
    tier_ceiling = tier_ceilings.get(tier, 1)

    # Is this a controllable listing? (standard tier only)
    is_controllable = (tier == 'standard')

    # Get improvements
    improvements = calculate_improvements(listing)

    # Calculate totals
    total_relevance = sum(imp['relevance_gain'] for imp in improvements)
    total_merch = sum(imp['merch_gain'] for imp in improvements)

    # Unconstrained improvement (theoretical)
    unconstrained_improvement = int(total_relevance / RELEVANCE_PER_RANK) if total_relevance > 0 else 0
    unconstrained_new_rank = max(1, current_rank - unconstrained_improvement)

    # Check if listing is outperforming its tier (ranked better than ceiling)
    outperforming_tier = current_rank < tier_ceiling

    # Realistic improvement (constrained by tier ceiling)
    if outperforming_tier:
        # Already outperforming - can't improve further without understanding why
        # they're ranked above tier ceiling (maybe no premium competition?)
        realistic_new_rank = current_rank  # Can't promise improvement
        realistic_improvement = 0
        at_tier_ceiling = False
    else:
        realistic_new_rank = max(tier_ceiling, unconstrained_new_rank)
        realistic_improvement = current_rank - realistic_new_rank
        # At ceiling?
        at_tier_ceiling = (realistic_new_rank == tier_ceiling) and (unconstrained_new_rank < tier_ceiling)

    premium_recommended = at_tier_ceiling and tier == 'standard'

    # Overall priority score
    priority_score = sum(imp['priority_score'] for imp in improvements)
    if at_tier_ceiling:
        priority_score *= 0.5  # Lower priority if maxed out

    # Estimated merch score
    estimated_merch = estimate_merch_score(listing)
    actual_merch = listing.get('merch_score')
    merch_gap = (actual_merch - estimated_merch) if actual_merch else None

    # Quality tier
    quality_tier = get_quality_tier(actual_merch)

    # Price vs MSRP
    price = listing.get('price')
    msrp = listing.get('msrp')
    price_vs_msrp = None
    if price and msrp and msrp > 0:
        price_vs_msrp = round((price - msrp) / msrp * 100, 1)

    # Top 3 actions
    top_actions = improvements[:3]
    action_1 = top_actions[0]['action'] if len(top_actions) > 0 else ''
    action_1_pts = (top_actions[0]['relevance_gain'] + top_actions[0]['merch_gain']) if len(top_actions) > 0 else 0
    action_2 = top_actions[1]['action'] if len(top_actions) > 1 else ''
    action_2_pts = (top_actions[1]['relevance_gain'] + top_actions[1]['merch_gain']) if len(top_actions) > 1 else 0
    action_3 = top_actions[2]['action'] if len(top_actions) > 2 else ''
    action_3_pts = (top_actions[2]['relevance_gain'] + top_actions[2]['merch_gain']) if len(top_actions) > 2 else 0

    # All actions summary
    all_actions = '; '.join(imp['action'] for imp in improvements) if improvements else 'None needed'

    # Count easy wins
    easy_wins = len([imp for imp in improvements if imp['difficulty'] == 'Easy'])

    # Extract specific action details
    def get_action_detail(key):
        for imp in improvements:
            if imp['action_key'] == key:
                return imp
        return None

    price_imp = get_action_detail('price')
    vin_imp = get_action_detail('vin')
    floorplan_imp = get_action_detail('floorplan')
    photo_imp = get_action_detail('photos')
    length_imp = get_action_detail('length')

    return {
        # Tier analysis
        'tier': tier,
        'tier_ceiling': tier_ceiling,
        'is_controllable': is_controllable,
        'outperforming_tier': outperforming_tier,
        'at_tier_ceiling': at_tier_ceiling,
        'premium_recommended': premium_recommended,

        # Scores
        'estimated_merch_score': estimated_merch,
        'merch_gap': merch_gap,
        'quality_tier': quality_tier,
        'price_vs_msrp': price_vs_msrp,

        # Improvement totals
        'total_relevance_available': total_relevance,
        'total_merch_available': total_merch,
        'unconstrained_improvement': unconstrained_improvement,
        'realistic_improvement': realistic_improvement,
        'realistic_new_rank': realistic_new_rank,
        'priority_score': round(priority_score, 1),

        # Action flags
        'needs_price': not listing.get('has_price'),
        'needs_vin': not listing.get('has_vin'),
        'needs_floorplan': not listing.get('has_floorplan'),
        'needs_more_photos': listing.get('photo_count', 0) < 35,
        'needs_length': not listing.get('has_length'),

        # Price action
        'price_action': price_imp['action'] if price_imp else '',
        'price_relevance_gain': price_imp['relevance_gain'] if price_imp else 0,
        'price_merch_gain': price_imp['merch_gain'] if price_imp else 0,

        # VIN action
        'vin_action': vin_imp['action'] if vin_imp else '',
        'vin_relevance_gain': vin_imp['relevance_gain'] if vin_imp else 0,
        'vin_merch_gain': vin_imp['merch_gain'] if vin_imp else 0,

        # Floorplan action
        'floorplan_action': floorplan_imp['action'] if floorplan_imp else '',
        'floorplan_relevance_gain': floorplan_imp['relevance_gain'] if floorplan_imp else 0,
        'floorplan_merch_gain': floorplan_imp['merch_gain'] if floorplan_imp else 0,

        # Photo action
        'photo_action': photo_imp['action'] if photo_imp else '',
        'photos_needed': 35 - listing.get('photo_count', 0) if photo_imp else 0,
        'photo_relevance_gain': photo_imp['relevance_gain'] if photo_imp else 0,
        'photo_merch_gain': photo_imp['merch_gain'] if photo_imp else 0,

        # Length action
        'length_action': length_imp['action'] if length_imp else '',
        'length_merch_gain': length_imp['merch_gain'] if length_imp else 0,

        # Summary
        'action_1': action_1,
        'action_1_points': action_1_pts,
        'action_2': action_2,
        'action_2_points': action_2_pts,
        'action_3': action_3,
        'action_3_points': action_3_pts,
        'all_actions_summary': all_actions,
        'easy_wins_count': easy_wins,
        'total_actions_needed': len(improvements),
    }


# =============================================================================
# CSV OUTPUT
# =============================================================================

CSV_COLUMNS = [
    # Hierarchy / Grouping
    'thor_brand', 'dealer_group', 'dealer_name', 'dealer_phone',

    # Listing identifiers
    'id', 'listing_url', 'stock_number', 'vin',

    # Vehicle info
    'year', 'make', 'model', 'trim', 'class', 'condition', 'length', 'mileage',

    # Pricing
    'price', 'msrp', 'price_vs_msrp',

    # Location
    'city', 'state', 'zip_code',

    # Current ranking
    'rank', 'relevance_score', 'merch_score', 'estimated_merch_score', 'merch_gap', 'quality_tier',

    # Tier analysis
    'tier', 'is_premium', 'is_top_premium', 'tier_ceiling', 'is_controllable',
    'outperforming_tier', 'at_tier_ceiling', 'premium_recommended',

    # Current quality
    'has_price', 'has_vin', 'has_floorplan', 'has_length', 'photo_count',

    # Badges / freshness
    'badge_status', 'create_date', 'scheme_code', 'trusted_partner',

    # Improvement potential
    'total_relevance_available', 'total_merch_available',
    'unconstrained_improvement', 'realistic_improvement', 'realistic_new_rank',
    'priority_score',

    # Action flags
    'needs_price', 'needs_vin', 'needs_floorplan', 'needs_more_photos', 'needs_length',

    # Action details
    'price_action', 'price_relevance_gain', 'price_merch_gain',
    'vin_action', 'vin_relevance_gain', 'vin_merch_gain',
    'floorplan_action', 'floorplan_relevance_gain', 'floorplan_merch_gain',
    'photo_action', 'photos_needed', 'photo_relevance_gain', 'photo_merch_gain',
    'length_action', 'length_merch_gain',

    # Summary
    'action_1', 'action_1_points', 'action_2', 'action_2_points', 'action_3', 'action_3_points',
    'all_actions_summary', 'easy_wins_count', 'total_actions_needed',
]


def build_csv_row(listing: Dict, analysis: Dict) -> Dict:
    """Build a CSV row combining listing data and analysis."""
    row = {}

    # Thor brand
    row['thor_brand'] = listing.get('thor_brand', '')

    # From listing data
    row['dealer_group'] = listing.get('dealer_group', '')
    row['dealer_name'] = listing.get('dealer_name', '')
    row['dealer_phone'] = listing.get('dealer_phone', '')
    row['id'] = listing.get('id', '')
    row['listing_url'] = listing.get('listing_url', '')
    row['stock_number'] = listing.get('stock_number', '')
    row['vin'] = listing.get('vin', '')
    row['year'] = listing.get('year', '')
    row['make'] = listing.get('make', '')
    row['model'] = listing.get('model', '')
    row['trim'] = listing.get('trim', '')
    row['class'] = listing.get('class', '')
    row['condition'] = listing.get('condition', '')
    row['length'] = listing.get('length', '')
    row['mileage'] = listing.get('mileage', '')
    row['price'] = listing.get('price', '')
    row['msrp'] = listing.get('msrp', '')
    row['city'] = listing.get('city', '')
    row['state'] = listing.get('state', '')
    row['zip_code'] = listing.get('zip_code', '')
    row['rank'] = listing.get('rank', '')
    row['relevance_score'] = listing.get('relevance_score', '')
    row['merch_score'] = listing.get('merch_score', '')
    row['is_premium'] = listing.get('is_premium', False)
    row['is_top_premium'] = listing.get('is_top_premium', False)
    row['has_price'] = listing.get('has_price', False)
    row['has_vin'] = listing.get('has_vin', False)
    row['has_floorplan'] = listing.get('has_floorplan', False)
    row['has_length'] = listing.get('has_length', False)
    row['photo_count'] = listing.get('photo_count', 0)
    row['badge_status'] = listing.get('badge_status', '')
    row['create_date'] = listing.get('create_date', '')
    row['scheme_code'] = listing.get('scheme_code', '')
    row['trusted_partner'] = listing.get('trusted_partner', False)

    # From analysis
    for key, value in analysis.items():
        row[key] = value

    return row


def write_csv(rows: List[Dict], output_path: str):
    """Write rows to CSV file."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


# =============================================================================
# TEXT REPORT
# =============================================================================

def generate_manufacturer_reports(analyzed: List[Dict], all_listings: List[Dict],
                                   output_dir: str) -> Dict[str, str]:
    """
    Generate per-manufacturer reports that can be sent to each Thor brand.
    Each report breaks down by dealer with actionable tables.
    """
    reports = {}

    # Group by thor_brand
    by_brand = defaultdict(list)
    for row in analyzed:
        brand = row.get('thor_brand', 'Unknown')
        if brand:
            by_brand[brand].append(row)

    # Calculate overall dealer stats for comparison
    all_dealer_stats = defaultdict(lambda: {'ranks': [], 'count': 0})
    for row in analyzed:
        dealer = row.get('dealer_name', 'Unknown')
        if row.get('rank'):
            all_dealer_stats[dealer]['ranks'].append(row['rank'])
            all_dealer_stats[dealer]['count'] += 1

    for dealer, stats in all_dealer_stats.items():
        stats['avg_rank'] = sum(stats['ranks']) / len(stats['ranks']) if stats['ranks'] else 0

    overall_avg_rank = sum(s['avg_rank'] for s in all_dealer_stats.values()) / len(all_dealer_stats) if all_dealer_stats else 0

    # Generate report for each brand
    for brand, brand_listings in sorted(by_brand.items()):
        lines = []

        # Header
        lines.append("=" * 100)
        lines.append(f"MANUFACTURER REPORT: {brand.upper()}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Total Listings: {len(brand_listings)}")
        lines.append("=" * 100)

        # Brand Summary
        brand_ranks = [l['rank'] for l in brand_listings if l.get('rank')]
        brand_avg_rank = sum(brand_ranks) / len(brand_ranks) if brand_ranks else 0
        premium_count = len([l for l in brand_listings if l.get('is_premium')])
        standard_count = len([l for l in brand_listings if not l.get('is_premium')])

        lines.append(f"\nBRAND SUMMARY")
        lines.append("-" * 50)
        lines.append(f"  Average Rank: {brand_avg_rank:.1f}")
        lines.append(f"  Premium Listings: {premium_count}")
        lines.append(f"  Standard Listings: {standard_count}")
        lines.append(f"  Total Improvement Potential: {sum(l.get('realistic_improvement', 0) for l in brand_listings)} positions")

        # Quick stats
        missing_price = len([l for l in brand_listings if l.get('needs_price')])
        missing_vin = len([l for l in brand_listings if l.get('needs_vin')])
        missing_floorplan = len([l for l in brand_listings if l.get('needs_floorplan')])
        missing_length = len([l for l in brand_listings if l.get('needs_length')])
        low_photos = len([l for l in brand_listings if l.get('needs_more_photos')])

        lines.append(f"\nQUICK WINS SUMMARY")
        lines.append("-" * 50)
        lines.append(f"  Missing Price: {missing_price} listings (+{missing_price * 194} relevance pts)")
        lines.append(f"  Missing VIN: {missing_vin} listings (+{missing_vin * 165} relevance pts)")
        lines.append(f"  Missing Floorplan: {missing_floorplan} listings (+{missing_floorplan * 50} relevance pts)")
        lines.append(f"  Missing Length/Specs: {missing_length} listings (+{missing_length * 8} merch pts)")
        lines.append(f"  Need More Photos (<35): {low_photos} listings")

        # Group by dealer
        by_dealer = defaultdict(list)
        for row in brand_listings:
            dealer = row.get('dealer_name') or 'Unknown Dealer'
            by_dealer[dealer].append(row)

        lines.append(f"\n\n{'=' * 100}")
        lines.append(f"DEALER BREAKDOWN ({len(by_dealer)} dealers)")
        lines.append("=" * 100)

        # Sort dealers by avg rank (best first)
        dealer_summaries = []
        for dealer, listings in by_dealer.items():
            ranks = [l['rank'] for l in listings if l.get('rank')]
            avg_rank = sum(ranks) / len(ranks) if ranks else 999
            dealer_summaries.append({
                'dealer': dealer,
                'listings': listings,
                'avg_rank': avg_rank,
                'count': len(listings),
                'premium_count': len([l for l in listings if l.get('is_premium')]),
            })

        dealer_summaries.sort(key=lambda x: x['avg_rank'])

        for dealer_info in dealer_summaries:
            dealer = dealer_info['dealer']
            listings = dealer_info['listings']
            dealer_avg = dealer_info['avg_rank']
            dealer_premium = dealer_info['premium_count']

            # Compare to overall
            rank_diff = dealer_avg - overall_avg_rank
            rank_comparison = f"({rank_diff:+.1f} vs avg)" if rank_diff != 0 else "(at avg)"

            lines.append(f"\n\n{'─' * 100}")
            lines.append(f"DEALER: {dealer}")
            lines.append(f"{'─' * 100}")

            # Dealer contact (get from first listing)
            phone = listings[0].get('dealer_phone', 'N/A')
            city = listings[0].get('city', '')
            state = listings[0].get('state', '')
            lines.append(f"Contact: {phone} | Location: {city}, {state}")

            # Dealer metrics
            lines.append(f"\nDealer Metrics:")
            lines.append(f"  Listings: {len(listings)}")
            lines.append(f"  Avg Rank: {dealer_avg:.1f} {rank_comparison}")
            if dealer_premium > 0:
                lines.append(f"  Premium Listings: {dealer_premium}")
            else:
                lines.append(f"  Premium Listings: NONE ⚠️  (Consider premium placement for top units)")

            # Dealer-level issues
            dealer_issues = []
            d_missing_price = len([l for l in listings if l.get('needs_price')])
            d_missing_vin = len([l for l in listings if l.get('needs_vin')])
            d_missing_floorplan = len([l for l in listings if l.get('needs_floorplan')])
            d_missing_length = len([l for l in listings if l.get('needs_length')])
            d_low_photos = len([l for l in listings if l.get('needs_more_photos')])

            if d_missing_price > 0:
                dealer_issues.append(f"Missing price on {d_missing_price} listings")
            if d_missing_vin > 0:
                dealer_issues.append(f"Missing VIN on {d_missing_vin} listings")
            if d_missing_floorplan > 0:
                dealer_issues.append(f"Missing floorplan on {d_missing_floorplan} listings")
            if d_missing_length > 0:
                dealer_issues.append(f"Missing length/specs on {d_missing_length} listings")
            if d_low_photos > 0:
                dealer_issues.append(f"Low photos (<35) on {d_low_photos} listings")

            if dealer_issues:
                lines.append(f"\n  ⚠️  Process Issues:")
                for issue in dealer_issues:
                    lines.append(f"      • {issue}")

            # Listing table
            lines.append(f"\n  LISTINGS:")
            lines.append(f"  {'─' * 96}")

            # Table header
            lines.append(f"  {'Rank':<6}{'Year':<6}{'Model':<25}{'Price':<12}{'Photos':<8}{'Length':<8}{'Merch':<7}{'Status':<12}{'Top Actions':<40}")
            lines.append(f"  {'─' * 96}")

            # Sort listings by rank
            for listing in sorted(listings, key=lambda x: x.get('rank') or 999):
                rank = listing.get('rank', 'N/A')
                year = listing.get('year', '')
                model = (listing.get('model') or '')[:24]
                price = f"${listing.get('price', 0):,.0f}" if listing.get('price') else 'NO PRICE'
                photos = listing.get('photo_count', 0)
                length = f"{listing.get('length', 0):.0f}ft" if listing.get('length') else 'MISSING'
                merch = listing.get('merch_score', 0)

                # Status
                if listing.get('is_premium'):
                    status = 'Premium'
                elif listing.get('outperforming_tier'):
                    status = 'Outperform'
                elif listing.get('at_tier_ceiling'):
                    status = 'At Ceiling'
                else:
                    status = 'Standard'

                # Top action
                action = listing.get('action_1', '') or 'None needed'
                if len(action) > 38:
                    action = action[:35] + '...'

                lines.append(f"  {rank:<6}{year:<6}{model:<25}{price:<12}{photos:<8}{length:<8}{merch:<7.0f}{status:<12}{action:<40}")

            # Detailed action items for this dealer
            actionable = [l for l in listings if l.get('total_actions_needed', 0) > 0]
            if actionable:
                lines.append(f"\n  DETAILED ACTIONS NEEDED:")
                lines.append(f"  {'─' * 96}")

                for listing in sorted(actionable, key=lambda x: -x.get('priority_score', 0)):
                    lines.append(f"\n  • {listing.get('year')} {listing.get('model')} (Rank {listing.get('rank')})")
                    lines.append(f"    Stock#: {listing.get('stock_number', 'N/A')} | VIN: {listing.get('vin') or 'MISSING'}")
                    lines.append(f"    Current: {listing.get('photo_count', 0)} photos | Length: {listing.get('length') or 'MISSING'} | Merch: {listing.get('merch_score', 0):.0f}")

                    if listing.get('realistic_improvement', 0) > 0:
                        lines.append(f"    Potential: Rank {listing.get('rank')} → {listing.get('realistic_new_rank')} (+{listing.get('realistic_improvement')} positions)")
                    elif listing.get('outperforming_tier'):
                        lines.append(f"    Status: OUTPERFORMING tier ceiling - apply actions to maintain position")

                    lines.append(f"    Actions:")
                    if listing.get('price_action'):
                        lines.append(f"      → {listing.get('price_action')} (+{listing.get('price_relevance_gain')} relevance)")
                    if listing.get('vin_action'):
                        lines.append(f"      → {listing.get('vin_action')} (+{listing.get('vin_relevance_gain')} relevance)")
                    if listing.get('floorplan_action'):
                        lines.append(f"      → {listing.get('floorplan_action')} (+{listing.get('floorplan_relevance_gain')} relevance, +{listing.get('floorplan_merch_gain')} merch)")
                    if listing.get('photo_action'):
                        lines.append(f"      → {listing.get('photo_action')} (+{listing.get('photo_relevance_gain')} relevance, +{listing.get('photo_merch_gain')} merch)")
                    if listing.get('length_action'):
                        lines.append(f"      → {listing.get('length_action')} (+{listing.get('length_merch_gain')} merch)")

                    lines.append(f"    URL: {listing.get('listing_url', 'N/A')}")

        # Footer
        lines.append(f"\n\n{'=' * 100}")
        lines.append("POINT VALUES REFERENCE")
        lines.append("=" * 100)
        lines.append("""
  Action                  Relevance Points    Merch Points    Difficulty
  ─────────────────────────────────────────────────────────────────────
  Add price               +194                +5              Easy
  Add VIN                 +165                +6              Easy
  Add 35+ photos          +195                +30             Medium
  Add floorplan           +50                 +12             Easy
  Add length/specs        +0                  +8              Easy

  ~15 relevance points ≈ 1 rank position improvement
  Tier ceiling: Standard listings cannot pass premium without purchasing premium
""")

        reports[brand] = "\n".join(lines)

        # Save to file
        safe_brand = brand.replace(' ', '_').replace('/', '_')
        report_path = Path(output_dir) / f"manufacturer_report_{safe_brand}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(reports[brand])
        print(f"Manufacturer report saved: {report_path}")

    return reports


def generate_text_report(listings: List[Dict], thor_listings: List[Dict],
                         analyzed: List[Dict], tier_ceilings: Dict) -> str:
    """Generate enhanced text report."""
    lines = []

    # Header
    lines.append("=" * 80)
    lines.append("THOR INDUSTRIES BRAND ANALYSIS REPORT v2")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 80)

    # Executive Summary
    lines.append("\n" + "=" * 40)
    lines.append("EXECUTIVE SUMMARY")
    lines.append("=" * 40)

    total_listings = len(listings)
    total_thor = len(thor_listings)
    thor_share = (total_thor / total_listings * 100) if total_listings > 0 else 0

    lines.append(f"\nMarket Presence:")
    lines.append(f"  Thor brand listings: {total_thor} ({thor_share:.1f}%)")
    lines.append(f"  Total listings: {total_listings}")

    # Tier distribution
    lines.append(f"\nTier Distribution:")
    lines.append(f"  Tier ceilings: Top Premium ends at {tier_ceilings['premium']-1}, "
                 f"Premium ends at {tier_ceilings['standard']-1}")

    top_prem = len([l for l in listings if l.get('is_top_premium')])
    prem = len([l for l in listings if l.get('is_premium') and not l.get('is_top_premium')])
    standard = len([l for l in listings if not l.get('is_premium')])
    lines.append(f"  Top Premium: {top_prem} listings")
    lines.append(f"  Premium: {prem} listings")
    lines.append(f"  Standard: {standard} listings (positions {tier_ceilings['standard']}+)")

    # Thor in each tier
    thor_top_prem = len([l for l in thor_listings if l.get('is_top_premium')])
    thor_prem = len([l for l in thor_listings if l.get('is_premium') and not l.get('is_top_premium')])
    thor_standard = len([l for l in thor_listings if not l.get('is_premium')])
    lines.append(f"\nThor Tier Breakdown:")
    lines.append(f"  Top Premium: {thor_top_prem}")
    lines.append(f"  Premium: {thor_prem}")
    lines.append(f"  Standard (controllable): {thor_standard}")

    # Improvement potential for controllable listings
    controllable = [a for a in analyzed if a.get('is_controllable')]
    outperforming = [a for a in controllable if a.get('outperforming_tier')]
    can_improve = [a for a in controllable if not a.get('outperforming_tier')]
    total_realistic_improvement = sum(a['realistic_improvement'] for a in can_improve)
    at_ceiling_count = len([a for a in can_improve if a['at_tier_ceiling']])

    lines.append(f"\nImprovement Potential (Standard Tier Only):")
    lines.append(f"  Controllable listings: {len(controllable)}")
    lines.append(f"  - Already outperforming tier ceiling: {len(outperforming)} (no improvement possible)")
    lines.append(f"  - Can improve within tier: {len(can_improve)}")
    lines.append(f"  Total realistic rank improvement: {total_realistic_improvement} positions")
    lines.append(f"  Listings at tier ceiling (need premium): {at_ceiling_count}")

    # Brand breakdown
    lines.append("\n" + "=" * 40)
    lines.append("THOR BRAND PERFORMANCE")
    lines.append("=" * 40)

    brand_stats = defaultdict(lambda: {'count': 0, 'ranks': [], 'merch': [], 'improvements': []})
    for a in analyzed:
        brand = a.get('thor_brand', 'Unknown')
        brand_stats[brand]['count'] += 1
        if a.get('rank'):
            brand_stats[brand]['ranks'].append(a['rank'])
        if a.get('merch_score'):
            brand_stats[brand]['merch'].append(a['merch_score'])
        brand_stats[brand]['improvements'].append(a['realistic_improvement'])

    lines.append(f"\n{'Brand':<20} {'Count':>6} {'Avg Rank':>10} {'Avg Merch':>10} {'Improve':>10}")
    lines.append("-" * 60)

    for brand in sorted(brand_stats.keys()):
        stats = brand_stats[brand]
        avg_rank = sum(stats['ranks']) / len(stats['ranks']) if stats['ranks'] else 0
        avg_merch = sum(stats['merch']) / len(stats['merch']) if stats['merch'] else 0
        total_imp = sum(stats['improvements'])
        lines.append(f"{brand:<20} {stats['count']:>6} {avg_rank:>10.1f} {avg_merch:>10.1f} {total_imp:>10}")

    # Top opportunities (only listings that CAN improve)
    lines.append("\n" + "=" * 40)
    lines.append("TOP 15 IMPROVEMENT OPPORTUNITIES")
    lines.append("(Standard tier, can improve, sorted by priority score)")
    lines.append("=" * 40)

    # Sort by priority score - only show listings that can actually improve
    opportunities = sorted(
        [a for a in controllable if not a.get('outperforming_tier') and a.get('realistic_improvement', 0) > 0],
        key=lambda x: x['priority_score'],
        reverse=True
    )[:15]

    if not opportunities:
        lines.append("\nNo listings with improvement potential found.")
    else:
        for i, opp in enumerate(opportunities, 1):
            lines.append(f"\n{i}. {opp['thor_brand']} {opp['model']} ({opp['year']})")
            lines.append(f"   Rank: {opp['rank']} -> {opp['realistic_new_rank']} "
                         f"(+{opp['realistic_improvement']} positions)")
            if opp['at_tier_ceiling']:
                lines.append(f"   *** AT TIER CEILING - Premium recommended for further improvement ***")
            lines.append(f"   Priority Score: {opp['priority_score']}")
            lines.append(f"   Top Actions: {opp['action_1']}; {opp['action_2']}; {opp['action_3']}")
            lines.append(f"   URL: {opp['listing_url']}")

    # Show outperforming listings separately
    if outperforming:
        lines.append("\n" + "-" * 40)
        lines.append(f"OUTPERFORMING TIER ({len(outperforming)} listings)")
        lines.append("These standard listings rank above the tier ceiling - likely due to")
        lines.append("low premium competition in this search. Still apply actions to maintain position.")
        lines.append("-" * 40)
        for opp in sorted(outperforming, key=lambda x: x['rank'])[:10]:
            lines.append(f"  Rank {opp['rank']}: {opp['thor_brand']} {opp['model']} - "
                         f"Actions: {opp['all_actions_summary'][:60]}")

    # Quick wins summary
    lines.append("\n" + "=" * 40)
    lines.append("QUICK WINS SUMMARY")
    lines.append("=" * 40)

    missing_price = len([a for a in controllable if a['needs_price']])
    missing_vin = len([a for a in controllable if a['needs_vin']])
    missing_floorplan = len([a for a in controllable if a['needs_floorplan']])
    missing_photos = len([a for a in controllable if a['needs_more_photos']])

    lines.append(f"\nEasy Fixes (Standard tier Thor listings):")
    lines.append(f"  Missing price: {missing_price} listings (+{missing_price * 194} relevance pts)")
    lines.append(f"  Missing VIN: {missing_vin} listings (+{missing_vin * 165} relevance pts)")
    lines.append(f"  Missing floorplan: {missing_floorplan} listings (+{missing_floorplan * 50} relevance pts)")
    lines.append(f"  Need more photos: {missing_photos} listings")

    lines.append("\n" + "=" * 80)

    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================

def analyze(csv_path: str, output_csv: str = None, output_report: str = None,
            thor_only: bool = True) -> tuple:
    """
    Run full analysis.

    Args:
        csv_path: Path to ranked_listings CSV
        output_csv: Path for output CSV (optional)
        output_report: Path for text report (optional)
        thor_only: If True, only analyze Thor brands

    Returns:
        (analyzed_rows, report_text)
    """
    print(f"\nLoading data from: {csv_path}")
    listings = load_ranked_listings(csv_path)
    print(f"Total listings loaded: {len(listings)}")

    # Identify Thor brands
    for listing in listings:
        listing['thor_brand'] = identify_thor_brand(listing.get('make', ''))

    thor_listings = [l for l in listings if l.get('thor_brand')]
    print(f"Thor brand listings: {len(thor_listings)}")

    # Calculate tier ceilings
    tier_ceilings = calculate_tier_ceilings(listings)
    print(f"Tier ceilings: {tier_ceilings}")

    # Analyze listings
    if thor_only:
        to_analyze = thor_listings
    else:
        to_analyze = listings

    analyzed_rows = []
    for listing in to_analyze:
        analysis = calculate_listing_analysis(listing, tier_ceilings)
        row = build_csv_row(listing, analysis)
        analyzed_rows.append(row)

    # Sort by thor_brand, dealer_group, dealer_name, priority_score
    analyzed_rows.sort(key=lambda x: (
        x.get('thor_brand', ''),
        x.get('dealer_group', ''),
        x.get('dealer_name', ''),
        -x.get('priority_score', 0)  # Descending
    ))

    print(f"Analyzed {len(analyzed_rows)} listings")

    # Generate report
    report = generate_text_report(listings, thor_listings, analyzed_rows, tier_ceilings)

    # Write outputs
    if output_csv:
        write_csv(analyzed_rows, output_csv)
        print(f"CSV saved to: {output_csv}")

    if output_report:
        with open(output_report, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Report saved to: {output_report}")

    # Generate per-manufacturer reports
    output_dir = Path(output_csv).parent if output_csv else Path('output')
    manufacturer_reports = generate_manufacturer_reports(analyzed_rows, listings, str(output_dir))

    return analyzed_rows, report


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Thor Industries Brand Analysis v2 - Manufacturer Action Report'
    )
    parser.add_argument('--input', '-i', help='Input ranked_listings CSV (default: latest)')
    parser.add_argument('--output-csv', '-o', help='Output CSV path (default: auto-named)')
    parser.add_argument('--output-report', '-r', help='Output report path (default: auto-named)')
    parser.add_argument('--all', action='store_true', help='Analyze all listings, not just Thor')
    parser.add_argument('--print-report', action='store_true', help='Print report to stdout')
    args = parser.parse_args()

    # Find input file
    if args.input:
        csv_path = Path(args.input)
    else:
        output_dir = Path(__file__).parent.parent.parent / 'output'
        csv_files = sorted(output_dir.glob('ranked_listings_*.csv'), reverse=True)
        if not csv_files:
            print("Error: No ranked_listings CSV files found in output/")
            return
        csv_path = csv_files[0]

    # Auto-name outputs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(__file__).parent.parent.parent / 'output'

    output_csv = args.output_csv or str(output_dir / f'thor_actions_{timestamp}.csv')
    output_report = args.output_report or str(output_dir / f'thor_report_v2_{timestamp}.txt')

    # Run analysis
    analyzed, report = analyze(
        str(csv_path),
        output_csv=output_csv,
        output_report=output_report,
        thor_only=not args.all
    )

    if args.print_report:
        print("\n" + report)

    print(f"\nDone! Analyzed {len(analyzed)} listings.")


if __name__ == '__main__':
    main()
