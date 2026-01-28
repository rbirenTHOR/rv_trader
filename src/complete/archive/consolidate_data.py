"""
Consolidate RV Trader data into a single JSON file for the interactive dashboard.

Merges:
- ranked_listings_*.json (search results with rankings)
- engagement_stats_*.json (views/saves data)

Computes:
- Tier (top_premium, premium, standard)
- Competitive position (Dominant, Strong, Competitive, Neutral, At Risk, Disadvantaged)
- Days listed, improvements needed
- Region from state

Outputs:
- output/reports/rv_data.json (for dashboard consumption)

Usage:
    python src/complete/consolidate_data.py
    python src/complete/consolidate_data.py --input ranked_listings_20260119.json
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict

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

# State to region mapping
STATE_REGIONS = {
    # Midwest
    'IL': 'Midwest', 'IN': 'Midwest', 'MI': 'Midwest', 'OH': 'Midwest',
    'WI': 'Midwest', 'MN': 'Midwest', 'IA': 'Midwest', 'MO': 'Midwest',
    'ND': 'Midwest', 'SD': 'Midwest', 'NE': 'Midwest', 'KS': 'Midwest',
    # Southeast
    'FL': 'Southeast', 'GA': 'Southeast', 'SC': 'Southeast', 'NC': 'Southeast',
    'AL': 'Southeast', 'MS': 'Southeast', 'TN': 'Southeast', 'KY': 'Southeast',
    'VA': 'Southeast', 'WV': 'Southeast',
    # Northeast
    'NY': 'Northeast', 'PA': 'Northeast', 'NJ': 'Northeast', 'CT': 'Northeast',
    'MA': 'Northeast', 'RI': 'Northeast', 'VT': 'Northeast', 'NH': 'Northeast',
    'ME': 'Northeast', 'MD': 'Northeast', 'DE': 'Northeast', 'DC': 'Northeast',
    # Southwest
    'TX': 'Southwest', 'AZ': 'Southwest', 'NM': 'Southwest', 'OK': 'Southwest',
    'AR': 'Southwest', 'LA': 'Southwest',
    # West
    'CA': 'West', 'NV': 'West', 'OR': 'West', 'WA': 'West', 'HI': 'West',
    'AK': 'West',
    # Mountain
    'CO': 'Mountain', 'UT': 'Mountain', 'WY': 'Mountain', 'MT': 'Mountain',
    'ID': 'Mountain',
}

CURRENT_MODEL_YEAR = 2026
YEAR_PENALTY_POINTS = 24
RELEVANCE_PER_RANK = 15.0

# Improvement factors (relevance points)
IMPROVEMENT_FACTORS = {
    'price': 194,
    'vin': 165,
    'photos_35': 195,
    'floorplan': 50,
    'length': 8,  # merch points
}


# =============================================================================
# DATA LOADING
# =============================================================================

def load_ranked_listings(output_dir: Path, input_file: str = None) -> tuple[dict, Path]:
    """Load the most recent ranked_listings JSON file."""
    if input_file:
        path = output_dir / input_file
    else:
        files = sorted(output_dir.glob('ranked_listings_*.json'), reverse=True)
        if not files:
            raise FileNotFoundError("No ranked_listings JSON files found")
        path = files[0]

    print(f"Loading ranked listings: {path.name}")
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data, path


def load_engagement_data(output_dir: Path) -> Dict[str, Dict]:
    """Load the most recent engagement stats JSON file."""
    files = sorted(output_dir.glob('engagement_stats_*.json'), reverse=True)
    if not files:
        print("No engagement data found - Views/Saves will be empty")
        return {}

    path = files[0]
    print(f"Loading engagement data: {path.name}")

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Build lookup by listing ID
    engagement = {}
    for result in data.get('results', []):
        listing_id = str(result.get('id', ''))
        if listing_id:
            engagement[listing_id] = {
                'views': result.get('views'),
                'saves': result.get('saves'),
            }

    print(f"  Loaded engagement for {len(engagement)} listings")
    return engagement


# =============================================================================
# CALCULATIONS
# =============================================================================

def identify_thor_brand(make: str) -> Optional[str]:
    """Check if make belongs to Thor Industries family."""
    if not make:
        return None
    make_lower = make.lower().strip()
    for pattern, brand_name in THOR_BRANDS.items():
        if pattern in make_lower:
            return brand_name
    return None


def get_tier(listing: dict) -> str:
    """Determine listing tier."""
    is_top = listing.get('is_top_premium')
    is_prem = listing.get('is_premium')

    # Handle string "1" / "0" or boolean
    if is_top in ('1', True, 1):
        return 'top_premium'
    elif is_prem in ('1', True, 1):
        return 'premium'
    return 'standard'


def get_competitive_position(tier: str, year: int) -> str:
    """Calculate competitive position based on tier and model year."""
    if not year:
        return 'Unknown'

    years_old = CURRENT_MODEL_YEAR - year

    if tier == 'top_premium':
        if years_old <= 0:
            return 'Dominant'
        elif years_old == 1:
            return 'Strong'
        else:
            return 'Competitive'

    if tier == 'premium':
        if years_old <= 0:
            return 'Strong'
        elif years_old == 1:
            return 'Neutral'
        else:
            return 'At Risk'

    # Standard tier
    if years_old <= 0:
        return 'Competitive'
    elif years_old == 1:
        return 'At Risk'
    return 'Disadvantaged'


def calculate_days_listed(create_date: str) -> Optional[int]:
    """Calculate days since listing was created."""
    if not create_date:
        return None
    try:
        for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
            try:
                created = datetime.strptime(create_date[:19].replace('Z', ''), fmt.replace('Z', ''))
                return (datetime.now() - created).days
            except ValueError:
                continue
        return None
    except Exception:
        return None


def calculate_tier_ceilings(listings: List[dict]) -> Dict[str, int]:
    """Calculate best achievable rank for each tier."""
    top_premium_ranks = [l['rank'] for l in listings
                         if l.get('is_top_premium') in ('1', True, 1) and l.get('rank')]
    premium_ranks = [l['rank'] for l in listings
                    if l.get('is_premium') in ('1', True, 1) and l.get('rank')]

    return {
        'top_premium': 1,
        'premium': max(top_premium_ranks) + 1 if top_premium_ranks else 1,
        'standard': max(premium_ranks) + 1 if premium_ranks else 1,
    }


def calculate_improvements(listing: dict) -> List[str]:
    """Get list of improvement actions needed."""
    actions = []

    # Basic checks
    has_price = listing.get('price') and float(listing.get('price') or 0) > 0
    has_vin = bool(listing.get('vin'))
    has_floorplan = bool(listing.get('floorplan_id'))
    has_length = listing.get('length') and float(listing.get('length') or 0) > 0
    photo_count = int(listing.get('photo_count') or 0)

    if not has_price:
        actions.append(f'Add price (+{IMPROVEMENT_FACTORS["price"]} rel)')
    if not has_vin:
        actions.append(f'Add VIN (+{IMPROVEMENT_FACTORS["vin"]} rel)')
    if photo_count < 35:
        actions.append(f'Add {35 - photo_count} photos (+{IMPROVEMENT_FACTORS["photos_35"]} rel)')
    if not has_floorplan:
        actions.append(f'Add floorplan (+{IMPROVEMENT_FACTORS["floorplan"]} rel)')
    if not has_length:
        actions.append(f'Add length (+{IMPROVEMENT_FACTORS["length"]} merch)')

    # Year-aware recommendations
    year = listing.get('year')
    if year:
        years_old = CURRENT_MODEL_YEAR - year
        tier = get_tier(listing)

        if years_old >= 1 and tier != 'top_premium':
            penalty = years_old * YEAR_PENALTY_POINTS
            if tier == 'standard':
                actions.append(f'Year penalty: -{penalty} pts. Upgrade to Premium')
            else:
                actions.append(f'Year penalty: -{penalty} pts. Consider Top Premium')

    return actions


def get_image_url(listing: dict) -> str:
    """Construct CDN image URL for listing."""
    listing_id = listing.get('id', '')
    if listing_id:
        return f"https://cdn-p.tradercdn.com/images/rvtrader/{listing_id}/0.jpg"
    return ""


def get_region(state: str) -> str:
    """Get region from state code."""
    return STATE_REGIONS.get(state, 'Unknown')


# =============================================================================
# CONSOLIDATION
# =============================================================================

def consolidate_listing(listing: dict, engagement: Dict[str, Dict], tier_ceilings: Dict[str, int]) -> dict:
    """Consolidate a single listing with all computed fields."""
    listing_id = str(listing.get('id', ''))
    eng = engagement.get(listing_id, {})

    tier = get_tier(listing)
    year = listing.get('year')
    state = listing.get('state', '')

    # Quality indicators
    has_price = listing.get('price') and float(listing.get('price') or 0) > 0
    has_vin = bool(listing.get('vin'))
    has_floorplan = bool(listing.get('floorplan_id'))
    has_length = listing.get('length') and float(listing.get('length') or 0) > 0
    photo_count = int(listing.get('photo_count') or 0)

    # Thor brand identification
    thor_brand = identify_thor_brand(listing.get('make', ''))

    # Improvements
    improvements = calculate_improvements(listing)

    return {
        # Identifiers
        'id': listing_id,
        'rank': listing.get('rank'),
        'listing_url': listing.get('listing_url', ''),
        'image_url': get_image_url(listing),

        # Vehicle info
        'year': year,
        'make': listing.get('make', ''),
        'model': listing.get('model', ''),
        'trim': listing.get('trim', ''),
        'vin': listing.get('vin', ''),  # Actual VIN value
        'stock_number': listing.get('stock_number', ''),
        'class': listing.get('class', ''),
        'condition': listing.get('condition', ''),
        'length': listing.get('length'),
        'mileage': listing.get('mileage'),

        # Pricing
        'price': listing.get('price'),
        'msrp': listing.get('msrp'),

        # Location (dealer location)
        'city': listing.get('city', ''),
        'state': state,
        'zip_code': listing.get('zip_code', ''),
        'region': get_region(state),

        # Search context (query parameters)
        'search_zip': listing.get('search_zip', ''),
        'search_type': listing.get('search_type', ''),
        'search_radius': listing.get('search_radius', 50),

        # Dealer
        'dealer_name': listing.get('dealer_name', ''),
        'dealer_id': listing.get('dealer_id', ''),
        'dealer_group': listing.get('dealer_group', ''),
        'dealer_phone': listing.get('dealer_phone', ''),

        # Scoring
        'relevance_score': listing.get('relevance_score'),
        'merch_score': listing.get('merch_score'),

        # Tier analysis
        'tier': tier,
        'tier_ceiling': tier_ceilings.get(tier, 1),
        'is_premium': listing.get('is_premium') in ('1', True, 1),
        'is_top_premium': listing.get('is_top_premium') in ('1', True, 1),

        # Competitive position
        'position': get_competitive_position(tier, year),

        # Quality indicators
        'photo_count': photo_count,
        'has_vin': has_vin,
        'has_floorplan': has_floorplan,
        'has_price': has_price,
        'has_length': has_length,

        # Engagement
        'views': eng.get('views'),
        'saves': eng.get('saves'),

        # Age
        'days_listed': calculate_days_listed(listing.get('create_date')),
        'create_date': listing.get('create_date', ''),
        'price_drop_date': listing.get('price_drop_date', ''),

        # Thor brand info
        'is_thor': bool(thor_brand),
        'thor_brand': thor_brand,

        # Improvements
        'improvements': improvements,
        'improvement_count': len(improvements),
    }


def build_summary(listings: List[dict]) -> dict:
    """Build summary statistics from consolidated listings."""
    total = len(listings)
    thor_listings = [l for l in listings if l.get('is_thor')]
    thor_count = len(thor_listings)

    # Tier breakdown
    by_tier = {
        'top_premium': len([l for l in listings if l.get('tier') == 'top_premium']),
        'premium': len([l for l in listings if l.get('tier') == 'premium']),
        'standard': len([l for l in listings if l.get('tier') == 'standard']),
    }

    # Year breakdown
    by_year = defaultdict(int)
    for l in listings:
        year = l.get('year')
        if year == CURRENT_MODEL_YEAR:
            by_year['current'] += 1
        elif year == CURRENT_MODEL_YEAR - 1:
            by_year['one_year_old'] += 1
        elif year:
            by_year['older'] += 1
        else:
            by_year['unknown'] += 1

    # Brand breakdown (Thor only)
    by_brand = defaultdict(int)
    for l in thor_listings:
        brand = l.get('thor_brand', 'Unknown')
        by_brand[brand] += 1

    # Position breakdown (Thor only)
    by_position = defaultdict(int)
    for l in thor_listings:
        pos = l.get('position', 'Unknown')
        by_position[pos] += 1

    # Region breakdown
    by_region = defaultdict(int)
    for l in listings:
        region = l.get('region', 'Unknown')
        by_region[region] += 1

    # Engagement stats
    views_list = [l['views'] for l in listings if l.get('views') is not None]
    saves_list = [l['saves'] for l in listings if l.get('saves') is not None]

    return {
        'total_listings': total,
        'thor_count': thor_count,
        'thor_pct': round(thor_count / total * 100, 1) if total > 0 else 0,
        'by_tier': dict(by_tier),
        'by_year': dict(by_year),
        'by_brand': dict(by_brand),
        'by_position': dict(by_position),
        'by_region': dict(by_region),
        'engagement': {
            'listings_with_views': len(views_list),
            'total_views': sum(views_list) if views_list else 0,
            'avg_views': round(sum(views_list) / len(views_list), 1) if views_list else 0,
            'total_saves': sum(saves_list) if saves_list else 0,
            'avg_saves': round(sum(saves_list) / len(saves_list), 1) if saves_list else 0,
        },
    }


def consolidate(output_dir: Path, input_file: str = None) -> dict:
    """Main consolidation function."""
    # Load data
    ranked_data, ranked_path = load_ranked_listings(output_dir, input_file)
    engagement = load_engagement_data(output_dir)

    listings = ranked_data.get('listings', [])
    print(f"  Total listings: {len(listings)}")

    # Calculate tier ceilings
    tier_ceilings = calculate_tier_ceilings(listings)
    print(f"  Tier ceilings: {tier_ceilings}")

    # Consolidate each listing
    consolidated = []
    for listing in listings:
        consolidated.append(consolidate_listing(listing, engagement, tier_ceilings))

    # Extract search context from first listing
    first = listings[0] if listings else {}
    search_context = {
        'zip': first.get('search_zip', ''),
        'type': first.get('search_type', ''),
        'radius': first.get('search_radius', 50),
        'condition': first.get('search_condition', 'N'),
    }

    # Build summary
    summary = build_summary(consolidated)

    # Build final output
    result = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'source_ranked': ranked_path.name,
            'source_engagement': 'engagement_stats_*.json (latest)',
            'version': '1.0',
        },
        'search_context': search_context,
        'tier_ceilings': tier_ceilings,
        'summary': summary,
        'listings': consolidated,
    }

    return result


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Consolidate RV data for dashboard')
    parser.add_argument('--input', '-i', help='Input ranked_listings JSON file (default: latest)')
    parser.add_argument('--output', '-o', help='Output JSON path (default: output/reports/rv_data.json)')
    args = parser.parse_args()

    # Paths
    output_dir = Path(__file__).parent.parent.parent / 'output'
    reports_dir = output_dir / 'reports'
    reports_dir.mkdir(exist_ok=True)

    # Consolidate
    print("Consolidating RV Trader data...")
    print("=" * 60)

    data = consolidate(output_dir, args.input)

    # Save
    output_path = args.output or str(reports_dir / 'rv_data.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print(f"Consolidated data saved: {output_path}")
    print(f"  Total listings: {data['summary']['total_listings']}")
    print(f"  Thor listings: {data['summary']['thor_count']} ({data['summary']['thor_pct']}%)")
    print(f"  Search: {data['search_context']['type']} near {data['search_context']['zip']}")
    print(f"\nOpen rv_dashboard.html to view the interactive report.")


if __name__ == '__main__':
    main()
