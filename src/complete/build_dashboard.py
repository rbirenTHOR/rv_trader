"""
Build standalone RV Trader dashboard with embedded data.

This is the MAIN OUTPUT SCRIPT. It:
1. Loads ranked_listings_*.json (search results)
2. Loads engagement_stats_*.json (views/saves)
3. Consolidates all data
4. Generates standalone HTML with embedded JSON
5. Auto-cleans old data files

Output: output/reports/rv_dashboard_standalone.html

Usage:
    python src/complete/build_dashboard.py
    python src/complete/build_dashboard.py --input ranked_listings_merged.json
    python src/complete/build_dashboard.py --keep-data  # Don't auto-clean old files
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
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

STATE_REGIONS = {
    'IL': 'Midwest', 'IN': 'Midwest', 'MI': 'Midwest', 'OH': 'Midwest',
    'WI': 'Midwest', 'MN': 'Midwest', 'IA': 'Midwest', 'MO': 'Midwest',
    'ND': 'Midwest', 'SD': 'Midwest', 'NE': 'Midwest', 'KS': 'Midwest',
    'FL': 'Southeast', 'GA': 'Southeast', 'SC': 'Southeast', 'NC': 'Southeast',
    'AL': 'Southeast', 'MS': 'Southeast', 'TN': 'Southeast', 'KY': 'Southeast',
    'VA': 'Southeast', 'WV': 'Southeast',
    'NY': 'Northeast', 'PA': 'Northeast', 'NJ': 'Northeast', 'CT': 'Northeast',
    'MA': 'Northeast', 'RI': 'Northeast', 'VT': 'Northeast', 'NH': 'Northeast',
    'ME': 'Northeast', 'MD': 'Northeast', 'DE': 'Northeast', 'DC': 'Northeast',
    'TX': 'Southwest', 'AZ': 'Southwest', 'NM': 'Southwest', 'OK': 'Southwest',
    'AR': 'Southwest', 'LA': 'Southwest',
    'CA': 'West', 'NV': 'West', 'OR': 'West', 'WA': 'West', 'HI': 'West', 'AK': 'West',
    'CO': 'Mountain', 'UT': 'Mountain', 'WY': 'Mountain', 'MT': 'Mountain', 'ID': 'Mountain',
}

CURRENT_MODEL_YEAR = 2026
YEAR_PENALTY_POINTS = 24

IMPROVEMENT_FACTORS = {
    'price': 194,
    'vin': 165,
    'photos_35': 195,
    'floorplan': 50,
    'length': 8,
}

# =============================================================================
# DATA LOADING
# =============================================================================

def load_ranked_listings(output_dir: Path, input_file: str = None) -> tuple:
    """Load the most recent ranked_listings JSON file."""
    if input_file:
        path = output_dir / input_file
        if not path.exists():
            path = Path(input_file)
    else:
        files = sorted(output_dir.glob('ranked_listings_*.json'), reverse=True)
        files = [f for f in files if 'merged' not in f.name]  # Prefer non-merged first
        if not files:
            files = sorted(output_dir.glob('ranked_listings_*.json'), reverse=True)
        if not files:
            raise FileNotFoundError("No ranked_listings JSON files found in output/")
        path = files[0]

    print(f"  Loading: {path.name}")
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data, path


def load_engagement_data(output_dir: Path) -> Dict[str, Dict]:
    """Load the most recent engagement stats JSON file."""
    files = sorted(output_dir.glob('engagement_stats_*.json'), reverse=True)
    if not files:
        print("  No engagement data found - Views/Saves will be empty")
        return {}

    path = files[0]
    print(f"  Loading: {path.name}")

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    engagement = {}
    for result in data.get('results', []):
        listing_id = str(result.get('id', ''))
        if listing_id:
            engagement[listing_id] = {
                'views': result.get('views'),
                'saves': result.get('saves'),
            }
    return engagement


# =============================================================================
# CALCULATIONS
# =============================================================================

def identify_thor_brand(make: str) -> Optional[str]:
    if not make:
        return None
    make_lower = make.lower().strip()
    for pattern, brand_name in THOR_BRANDS.items():
        if pattern in make_lower:
            return brand_name
    return None


def get_tier(listing: dict) -> str:
    is_top = listing.get('is_top_premium')
    is_prem = listing.get('is_premium')
    if is_top in ('1', True, 1):
        return 'top_premium'
    elif is_prem in ('1', True, 1):
        return 'premium'
    return 'standard'


def get_competitive_position(tier: str, year: int) -> str:
    if not year:
        return 'Unknown'
    years_old = CURRENT_MODEL_YEAR - year

    if tier == 'top_premium':
        if years_old <= 0:
            return 'Dominant'
        elif years_old == 1:
            return 'Strong'
        return 'Competitive'

    if tier == 'premium':
        if years_old <= 0:
            return 'Strong'
        elif years_old == 1:
            return 'Neutral'
        return 'At Risk'

    if years_old <= 0:
        return 'Competitive'
    elif years_old == 1:
        return 'At Risk'
    return 'Disadvantaged'


def calculate_days_listed(create_date: str) -> Optional[int]:
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
    actions = []
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
    listing_id = listing.get('id', '')
    if listing_id:
        return f"https://cdn-p.tradercdn.com/images/rvtrader/{listing_id}/0.jpg"
    return ""


def get_region(state: str) -> str:
    return STATE_REGIONS.get(state, 'Unknown')


# =============================================================================
# CONSOLIDATION
# =============================================================================

def consolidate_listing(listing: dict, engagement: Dict[str, Dict], tier_ceilings: Dict[str, int]) -> dict:
    listing_id = str(listing.get('id', ''))
    eng = engagement.get(listing_id, {})
    tier = get_tier(listing)
    year = listing.get('year')
    state = listing.get('state', '')

    has_price = listing.get('price') and float(listing.get('price') or 0) > 0
    has_vin = bool(listing.get('vin'))
    has_floorplan = bool(listing.get('floorplan_id'))
    has_length = listing.get('length') and float(listing.get('length') or 0) > 0
    photo_count = int(listing.get('photo_count') or 0)

    thor_brand = identify_thor_brand(listing.get('make', ''))
    improvements = calculate_improvements(listing)

    return {
        'id': listing_id,
        'rank': listing.get('rank'),
        'listing_url': listing.get('listing_url', ''),
        'image_url': get_image_url(listing),
        'year': year,
        'make': listing.get('make', ''),
        'model': listing.get('model', ''),
        'trim': listing.get('trim', ''),
        'vin': listing.get('vin', ''),
        'stock_number': listing.get('stock_number', ''),
        'class': listing.get('class', ''),
        'condition': listing.get('condition', ''),
        'length': listing.get('length'),
        'mileage': listing.get('mileage'),
        'price': listing.get('price'),
        'msrp': listing.get('msrp'),
        'city': listing.get('city', ''),
        'state': state,
        'zip_code': listing.get('zip_code', ''),
        'region': get_region(state),
        'search_zip': listing.get('search_zip', ''),
        'search_type': listing.get('search_type', ''),
        'search_radius': listing.get('search_radius', 50),
        'dealer_name': listing.get('dealer_name', ''),
        'dealer_id': listing.get('dealer_id', ''),
        'dealer_group': listing.get('dealer_group', ''),
        'dealer_phone': listing.get('dealer_phone', ''),
        'relevance_score': listing.get('relevance_score'),
        'merch_score': listing.get('merch_score'),
        'tier': tier,
        'tier_ceiling': tier_ceilings.get(tier, 1),
        'is_premium': listing.get('is_premium') in ('1', True, 1),
        'is_top_premium': listing.get('is_top_premium') in ('1', True, 1),
        'position': get_competitive_position(tier, year),
        'photo_count': photo_count,
        'has_vin': has_vin,
        'has_floorplan': has_floorplan,
        'has_price': has_price,
        'has_length': has_length,
        'views': eng.get('views'),
        'saves': eng.get('saves'),
        'days_listed': calculate_days_listed(listing.get('create_date')),
        'create_date': listing.get('create_date', ''),
        'price_drop_date': listing.get('price_drop_date', ''),
        'is_thor': bool(thor_brand),
        'thor_brand': thor_brand,
        'improvements': improvements,
        'improvement_count': len(improvements),
    }


def build_summary(listings: List[dict]) -> dict:
    total = len(listings)
    thor_listings = [l for l in listings if l.get('is_thor')]
    thor_count = len(thor_listings)

    by_tier = {
        'top_premium': len([l for l in listings if l.get('tier') == 'top_premium']),
        'premium': len([l for l in listings if l.get('tier') == 'premium']),
        'standard': len([l for l in listings if l.get('tier') == 'standard']),
    }

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

    by_brand = defaultdict(int)
    for l in thor_listings:
        brand = l.get('thor_brand', 'Unknown')
        by_brand[brand] += 1

    by_position = defaultdict(int)
    for l in thor_listings:
        pos = l.get('position', 'Unknown')
        by_position[pos] += 1

    by_region = defaultdict(int)
    for l in listings:
        region = l.get('region', 'Unknown')
        by_region[region] += 1

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
    ranked_data, ranked_path = load_ranked_listings(output_dir, input_file)
    engagement = load_engagement_data(output_dir)

    listings = ranked_data.get('listings', [])
    print(f"  Total listings: {len(listings)}")

    tier_ceilings = calculate_tier_ceilings(listings)
    print(f"  Tier ceilings: {tier_ceilings}")

    consolidated = [consolidate_listing(listing, engagement, tier_ceilings) for listing in listings]

    first = listings[0] if listings else {}
    search_context = {
        'zip': first.get('search_zip', ''),
        'type': first.get('search_type', ''),
        'radius': first.get('search_radius', 50),
        'condition': first.get('search_condition', 'N'),
    }

    summary = build_summary(consolidated)

    return {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'source_ranked': ranked_path.name,
            'version': '2.0',
        },
        'search_context': search_context,
        'tier_ceilings': tier_ceilings,
        'summary': summary,
        'listings': consolidated,
    }


# =============================================================================
# HTML TEMPLATE
# =============================================================================

def get_html_template() -> str:
    """Return the standalone dashboard HTML template."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RV Trader Analysis Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root { --primary-dark: #1a1a2e; --primary-light: #16213e; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f6fa; font-size: 15px; }
        .dashboard-header { background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary-light) 100%); color: white; padding: 1.5rem 2rem; margin-bottom: 1.5rem; }
        .dashboard-header h1 { margin: 0 0 0.5rem 0; font-size: 1.75rem; }
        .search-meta { display: flex; gap: 1.5rem; flex-wrap: wrap; }
        .meta-item { background: rgba(255,255,255,0.1); padding: 0.5rem 1rem; border-radius: 6px; }
        .meta-label { font-size: 0.7rem; opacity: 0.8; text-transform: uppercase; }
        .meta-value { font-size: 1.1rem; font-weight: 600; }
        .stat-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.75rem; margin-bottom: 1.5rem; }
        .stat-card { background: white; border-radius: 8px; padding: 0.75rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 4px solid #0d6efd; }
        .stat-card.success { border-left-color: #198754; }
        .stat-card.warning { border-left-color: #ffc107; }
        .stat-card.info { border-left-color: #0dcaf0; }
        .stat-card.danger { border-left-color: #dc3545; }
        .stat-value { font-size: 1.5rem; font-weight: 700; line-height: 1.2; }
        .stat-label { font-size: 0.75rem; color: #6c757d; text-transform: uppercase; }
        .stat-delta { font-size: 0.8rem; font-weight: 600; }
        .stat-delta.positive { color: #198754; }
        .stat-delta.negative { color: #dc3545; }
        .stat-delta.neutral { color: #6c757d; }
        .filter-panel { background: white; border-radius: 8px; padding: 1rem 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .filter-row { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: flex-end; }
        .query-filters { background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border: 2px solid #1976d2; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1rem; }
        .query-filters-title { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; color: #1565c0; margin-bottom: 0.5rem; letter-spacing: 0.5px; }
        .query-filters .filter-group label { color: #1565c0; }
        .query-filters .form-select { border-color: #1976d2; background-color: white; }
        .filter-group { flex: 1; min-width: 120px; }
        .filter-group label { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; color: #6c757d; margin-bottom: 0.25rem; }
        .view-toggle { display: flex; gap: 0.25rem; background: #e9ecef; padding: 3px; border-radius: 6px; }
        .view-toggle button { border: none; background: transparent; padding: 0.35rem 0.7rem; border-radius: 4px; font-size: 0.75rem; cursor: pointer; }
        .view-toggle button.active { background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .data-table-container { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow: hidden; }
        .table-wrapper { max-height: 75vh; overflow-y: auto; overflow-x: auto; }
        .table { margin-bottom: 0; font-size: 0.9rem; border-collapse: separate; border-spacing: 0; }
        .table th { background: var(--primary-dark); color: white; cursor: pointer; user-select: none; white-space: nowrap; position: sticky; top: 0; z-index: 20; font-size: 0.8rem; padding: 0.5rem 0.4rem; font-weight: 600; border-bottom: 2px solid #0d6efd; }
        .table th:hover { background: var(--primary-light); }
        .table th .sort-indicator { margin-left: 2px; opacity: 0.5; }
        .table th.sort-asc .sort-indicator::after { content: ' ▲'; opacity: 1; }
        .table th.sort-desc .sort-indicator::after { content: ' ▼'; opacity: 1; }
        .table td { padding: 0.4rem 0.35rem; vertical-align: middle; }
        .table tbody tr { cursor: pointer; transition: all 0.15s ease; }
        .table tbody tr:hover { background-color: #e3f2fd !important; transform: scale(1.002); box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .listing-link { color: #0d6efd; text-decoration: none; }
        .listing-link:hover { text-decoration: underline; }
        .badge-dominant { background: #198754; }
        .badge-strong { background: #0d6efd; }
        .badge-competitive { background: #0dcaf0; color: #000; }
        .badge-neutral { background: #6c757d; }
        .badge-atrisk { background: #ffc107; color: #000; }
        .badge-disadvantaged { background: #dc3545; }
        .tier-tp { background: #198754; color: white; }
        .tier-p { background: #0d6efd; color: white; }
        .tier-s { background: #6c757d; color: white; }
        #image-preview { display: none; position: fixed; z-index: 9999; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); padding: 16px 20px; max-width: 280px; pointer-events: none; text-align: center; }
        #image-preview .preview-icon { font-size: 2.5rem; margin-bottom: 8px; }
        #image-preview .preview-title { font-size: 1rem; font-weight: 600; margin-bottom: 4px; }
        #image-preview .preview-hint { font-size: 0.8rem; opacity: 0.8; }
        .yn-badge { display: inline-block; width: 20px; height: 20px; line-height: 20px; text-align: center; border-radius: 3px; font-size: 0.7rem; font-weight: 600; }
        .yn-yes { background: #d4edda; color: #155724; }
        .yn-no { background: #f8d7da; color: #721c24; }
        .vin-cell { font-size: 0.75rem; min-width: 150px; }
        .vin-text { font-family: 'Consolas', 'Monaco', monospace; font-size: 0.72rem; color: #495057; letter-spacing: 0.3px; }
        .actions-cell { min-width: 200px; max-width: 280px; }
        .action-item { font-size: 0.78rem; padding: 3px 0; border-bottom: 1px dotted #dee2e6; color: #856404; line-height: 1.3; }
        .action-item:last-child { border-bottom: none; }
        .thor-toggle { display: flex; align-items: center; gap: 0.5rem; }
        .thor-toggle input { width: 16px; height: 16px; }
        .text-success { color: #198754 !important; }
        .text-warning { color: #856404 !important; }
        .text-danger { color: #dc3545 !important; }
        .dealer-section { background: white; border-radius: 8px; margin-bottom: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow: hidden; }
        .dealer-header { background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); color: white; padding: 0.75rem 1rem; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
        .dealer-header:hover { background: linear-gradient(135deg, #34495e 0%, #2c3e50 100%); }
        .dealer-name { font-weight: 600; font-size: 1rem; }
        .dealer-stats { display: flex; gap: 1rem; font-size: 0.8rem; }
        .dealer-stat { text-align: center; }
        .dealer-stat-value { font-weight: 700; font-size: 1rem; }
        .dealer-stat-label { opacity: 0.8; font-size: 0.65rem; text-transform: uppercase; }
        .dealer-stat-delta { font-size: 0.7rem; }
        .dealer-stat-delta.positive { color: #2ecc71; }
        .dealer-stat-delta.negative { color: #e74c3c; }
        @media (max-width: 768px) { .filter-group { min-width: 100%; } .stat-cards { grid-template-columns: repeat(2, 1fr); } }
    </style>
</head>
<body>
    <div id="image-preview">
        <div class="preview-icon">🚐</div>
        <div class="preview-title">Click to View Listing</div>
        <div class="preview-hint">Opens on RVTrader.com</div>
    </div>

    <div class="dashboard-header">
        <h1>RV Trader Analysis Dashboard</h1>
        <p id="generated-at" class="mb-2 opacity-75"></p>
        <div class="search-meta" id="search-meta"></div>
    </div>

    <div class="container-fluid px-4">
        <div class="stat-cards" id="stat-cards"></div>

        <div class="filter-panel">
            <div class="query-filters">
                <div class="query-filters-title">🔍 Query Filters (Primary Search Criteria)</div>
                <div class="filter-row">
                    <div class="filter-group">
                        <label>Search Zip</label>
                        <select id="filter-zip" class="form-select form-select-sm"><option value="all">All Zip Codes</option></select>
                    </div>
                    <div class="filter-group">
                        <label>RV Type</label>
                        <select id="filter-type" class="form-select form-select-sm"><option value="all">All Types</option></select>
                    </div>
                    <div class="filter-group" style="flex: 0 0 auto;">
                        <label>&nbsp;</label>
                        <div class="small text-muted" id="query-count" style="padding: 0.375rem 0;"></div>
                    </div>
                </div>
            </div>

            <div class="filter-row">
                <div class="filter-group">
                    <label>View</label>
                    <div class="view-toggle">
                        <button id="view-list" class="active" onclick="setView('list')">List</button>
                        <button id="view-dealer" onclick="setView('dealer')">By Dealer</button>
                    </div>
                </div>
                <div class="filter-group">
                    <label>Brand</label>
                    <select id="filter-brand" class="form-select form-select-sm"><option value="all">All Brands</option></select>
                </div>
                <div class="filter-group">
                    <label>Tier</label>
                    <select id="filter-tier" class="form-select form-select-sm">
                        <option value="all">All Tiers</option>
                        <option value="top_premium">Top Premium</option>
                        <option value="premium">Premium</option>
                        <option value="standard">Standard</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Year</label>
                    <select id="filter-year" class="form-select form-select-sm"><option value="all">All Years</option></select>
                </div>
                <div class="filter-group">
                    <label>Position</label>
                    <select id="filter-position" class="form-select form-select-sm">
                        <option value="all">All Positions</option>
                        <option value="Dominant">Dominant</option>
                        <option value="Strong">Strong</option>
                        <option value="Competitive">Competitive</option>
                        <option value="Neutral">Neutral</option>
                        <option value="At Risk">At Risk</option>
                        <option value="Disadvantaged">Disadvantaged</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Region</label>
                    <select id="filter-region" class="form-select form-select-sm"><option value="all">All Regions</option></select>
                </div>
                <div class="filter-group">
                    <label>Dealer</label>
                    <input type="text" id="filter-dealer" class="form-control form-control-sm" placeholder="Search...">
                </div>
                <div class="filter-group thor-toggle">
                    <input type="checkbox" id="filter-thor" class="form-check-input">
                    <label for="filter-thor" class="form-check-label">Thor Only</label>
                </div>
                <div class="filter-actions">
                    <button id="btn-reset" class="btn btn-outline-secondary btn-sm">Reset</button>
                    <button id="btn-export" class="btn btn-success btn-sm">CSV</button>
                </div>
            </div>
        </div>

        <div id="data-container">
            <div class="data-table-container" id="list-view">
                <div class="table-wrapper">
                    <table class="table table-striped table-hover" id="data-table">
                        <thead>
                            <tr>
                                <th data-sort="rank">Rank<span class="sort-indicator"></span></th>
                                <th data-sort="year">Year<span class="sort-indicator"></span></th>
                                <th data-sort="make">Make<span class="sort-indicator"></span></th>
                                <th data-sort="model">Model<span class="sort-indicator"></span></th>
                                <th data-sort="stock_number">Stock#<span class="sort-indicator"></span></th>
                                <th data-sort="vin">VIN<span class="sort-indicator"></span></th>
                                <th data-sort="price">Price<span class="sort-indicator"></span></th>
                                <th data-sort="relevance_score">Relevance<span class="sort-indicator"></span></th>
                                <th data-sort="merch_score">Merch<span class="sort-indicator"></span></th>
                                <th data-sort="length">Length<span class="sort-indicator"></span></th>
                                <th data-sort="photo_count">Photos<span class="sort-indicator"></span></th>
                                <th>FP</th>
                                <th data-sort="views">Views<span class="sort-indicator"></span></th>
                                <th data-sort="saves">Saves<span class="sort-indicator"></span></th>
                                <th data-sort="tier">Tier<span class="sort-indicator"></span></th>
                                <th data-sort="position">Position<span class="sort-indicator"></span></th>
                                <th data-sort="days_listed">Days<span class="sort-indicator"></span></th>
                                <th data-sort="price_drop_date">Price Drop<span class="sort-indicator"></span></th>
                                <th data-sort="state">Location<span class="sort-indicator"></span></th>
                                <th data-sort="dealer_name">Dealer<span class="sort-indicator"></span></th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="table-body"></tbody>
                    </table>
                </div>
            </div>
            <div id="dealer-view" style="display: none;"></div>
        </div>

        <div class="card mt-4 mb-4">
            <div class="card-header"><h6 class="mb-0">Legend & Reference</h6></div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-3">
                        <h6>Competitive Positions</h6>
                        <ul class="list-unstyled small">
                            <li><span class="badge badge-dominant">Dominant</span> Top Premium + 2026</li>
                            <li><span class="badge badge-strong">Strong</span> Premium + 2026</li>
                            <li><span class="badge badge-competitive">Competitive</span> Standard + 2026</li>
                            <li><span class="badge badge-neutral">Neutral</span> Premium + 2025</li>
                            <li><span class="badge badge-atrisk">At Risk</span> Standard + 2025</li>
                            <li><span class="badge badge-disadvantaged">Disadvantaged</span> 2+ yrs old</li>
                        </ul>
                    </div>
                    <div class="col-md-3">
                        <h6>Tiers (Paid Placement)</h6>
                        <ul class="list-unstyled small">
                            <li><span class="badge tier-tp">Top Premium</span> Positions 1-3</li>
                            <li><span class="badge tier-p">Premium</span> Positions 4-40</li>
                            <li><span class="badge tier-s">Standard</span> Position 41+ (free)</li>
                        </ul>
                    </div>
                    <div class="col-md-3">
                        <h6>Scores</h6>
                        <ul class="list-unstyled small">
                            <li><strong>Relevance</strong> = Ranking score</li>
                            <li><strong>Merch</strong> = Listing quality</li>
                            <li>~15 rel pts = 1 rank position</li>
                            <li>Each year older = -24 rel pts</li>
                        </ul>
                    </div>
                    <div class="col-md-3">
                        <h6>Quick Win Points</h6>
                        <ul class="list-unstyled small">
                            <li>Add price: +194 relevance</li>
                            <li>Add VIN: +165 relevance</li>
                            <li>35+ photos: +195 relevance</li>
                            <li>Add floorplan: +50 relevance</li>
                        </ul>
                        <p class="small text-muted mb-0"><strong>Tip:</strong> Click any row to open on RVTrader</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // EMBEDDED DATA - replaced at build time
        const DATA = __EMBEDDED_DATA__;

        let allListings = DATA.listings || [];
        let filteredListings = [...allListings];
        let sortColumn = 'rank';
        let sortDirection = 'asc';
        let currentView = 'list';

        function init() {
            document.getElementById('generated-at').textContent = `Generated: ${new Date(DATA.metadata?.generated_at).toLocaleString()}`;
            renderMeta();
            populateFilters();
            renderStats();
            renderCurrentView();
            setupEventListeners();
        }

        function setView(view) {
            currentView = view;
            document.getElementById('view-list').classList.toggle('active', view === 'list');
            document.getElementById('view-dealer').classList.toggle('active', view === 'dealer');
            document.getElementById('list-view').style.display = view === 'list' ? 'block' : 'none';
            document.getElementById('dealer-view').style.display = view === 'dealer' ? 'block' : 'none';
            renderCurrentView();
        }

        function renderCurrentView() {
            if (currentView === 'list') renderTable();
            else renderDealerView();
        }

        function renderMeta() {
            const meta = document.getElementById('search-meta');
            const zipFilter = document.getElementById('filter-zip')?.value || 'all';
            const typeFilter = document.getElementById('filter-type')?.value || 'all';

            const uniqueZips = [...new Set(filteredListings.map(l => l.search_zip).filter(Boolean))];
            const uniqueTypes = [...new Set(filteredListings.map(l => l.search_type).filter(Boolean))];
            const uniqueRadii = [...new Set(filteredListings.map(l => l.search_radius).filter(Boolean))];

            const zipDisplay = zipFilter !== 'all' ? zipFilter : (uniqueZips.length === 1 ? uniqueZips[0] : `${uniqueZips.length} zips`);
            const typeDisplay = typeFilter !== 'all' ? typeFilter : (uniqueTypes.length === 1 ? uniqueTypes[0] : `${uniqueTypes.length} types`);
            const radiusDisplay = uniqueRadii.length === 1 ? uniqueRadii[0] : (uniqueRadii.length > 0 ? `${Math.min(...uniqueRadii)}-${Math.max(...uniqueRadii)}` : 50);

            const tc = calculateTierCeilings(filteredListings);

            meta.innerHTML = `
                <div class="meta-item"><div class="meta-label">Location</div><div class="meta-value">${zipDisplay}</div></div>
                <div class="meta-item"><div class="meta-label">RV Type</div><div class="meta-value">${typeDisplay}</div></div>
                <div class="meta-item"><div class="meta-label">Radius</div><div class="meta-value">${radiusDisplay} mi</div></div>
                <div class="meta-item"><div class="meta-label">Showing</div><div class="meta-value">${filteredListings.length} <span style="font-size:0.7rem;opacity:0.8">of ${allListings.length}</span></div></div>
                <div class="meta-item"><div class="meta-label">Tier Ceilings</div><div class="meta-value" style="font-size:0.85rem">TP≤${tc.top_premium} P≤${tc.premium} S≤${tc.standard}</div></div>
            `;
        }

        function calculateTierCeilings(listings) {
            const topPremiumRanks = listings.filter(l => l.is_top_premium).map(l => l.rank).filter(Boolean);
            const premiumRanks = listings.filter(l => l.is_premium || l.is_top_premium).map(l => l.rank).filter(Boolean);
            return {
                top_premium: 1,
                premium: topPremiumRanks.length > 0 ? Math.max(...topPremiumRanks) + 1 : 1,
                standard: premiumRanks.length > 0 ? Math.max(...premiumRanks) + 1 : 1
            };
        }

        function renderStats() {
            const container = document.getElementById('stat-cards');
            const brand = document.getElementById('filter-brand')?.value || 'all';
            const thorOnly = document.getElementById('filter-thor')?.checked || false;

            let brandListings, competitorListings;
            if (brand !== 'all') {
                brandListings = filteredListings;
                competitorListings = allListings.filter(l => l.make !== brand);
            } else if (thorOnly) {
                brandListings = filteredListings;
                competitorListings = allListings.filter(l => !l.is_thor);
            } else {
                brandListings = filteredListings;
                competitorListings = [];
            }

            const stats = calcStats(brandListings);
            const compStats = competitorListings.length > 0 ? calcStats(competitorListings) : null;

            const fmt = (val, decimals = 0) => val == null || isNaN(val) ? '-' : val.toFixed(decimals);

            function delta(val, comp, inverse = false) {
                if (!compStats || comp == null || val == null || isNaN(comp) || isNaN(val)) return '';
                const diff = inverse ? (comp - val) : (val - comp);
                if (isNaN(diff)) return '';
                const cls = diff > 0.1 ? 'positive' : diff < -0.1 ? 'negative' : 'neutral';
                const sign = diff > 0.1 ? '+' : '';
                return `<div class="stat-delta ${cls}">${sign}${diff.toFixed(1)} vs others</div>`;
            }

            container.innerHTML = `
                <div class="stat-card"><div class="stat-value">${stats.total}</div><div class="stat-label">Listings</div></div>
                <div class="stat-card info"><div class="stat-value">${fmt(stats.avgRank, 1)}</div><div class="stat-label">Avg Rank</div>${delta(stats.avgRank, compStats?.avgRank, true)}</div>
                <div class="stat-card warning"><div class="stat-value">${fmt(stats.avgViews)}</div><div class="stat-label">Avg Views</div>${delta(stats.avgViews, compStats?.avgViews)}</div>
                <div class="stat-card"><div class="stat-value">${fmt(stats.avgSaves, 1)}</div><div class="stat-label">Avg Saves</div>${delta(stats.avgSaves, compStats?.avgSaves)}</div>
                <div class="stat-card success"><div class="stat-value">${fmt(stats.avgPhotos)}</div><div class="stat-label">Avg Photos</div>${delta(stats.avgPhotos, compStats?.avgPhotos)}</div>
                <div class="stat-card"><div class="stat-value">${fmt(stats.premiumPct)}%</div><div class="stat-label">Premium</div>${delta(stats.premiumPct, compStats?.premiumPct)}</div>
                <div class="stat-card danger"><div class="stat-value">${fmt(stats.qualityScore)}%</div><div class="stat-label">Quality Score</div>${delta(stats.qualityScore, compStats?.qualityScore)}</div>
                <div class="stat-card info"><div class="stat-value">${stats.tp}/${stats.p}/${stats.s}</div><div class="stat-label">TP / P / S</div></div>
            `;
        }

        function calcStats(listings) {
            const empty = { total: 0, avgRank: 0, avgViews: 0, avgSaves: 0, avgPhotos: 0, premiumPct: 0, qualityScore: 0, tp: 0, p: 0, s: 0 };
            if (!listings || !listings.length) return empty;

            const total = listings.length;
            const ranks = listings.map(l => l.rank).filter(r => r != null && !isNaN(r) && r > 0);
            const views = listings.map(l => l.views).filter(v => v != null && !isNaN(v));
            const saves = listings.map(l => l.saves).filter(s => s != null && !isNaN(s));
            const photos = listings.map(l => l.photo_count || 0);

            const premium = listings.filter(l => l.tier === 'top_premium' || l.tier === 'premium').length;
            const tp = listings.filter(l => l.tier === 'top_premium').length;
            const p = listings.filter(l => l.tier === 'premium').length;
            const s = listings.filter(l => l.tier === 'standard').length;

            const withPrice = listings.filter(l => l.has_price).length;
            const withVin = listings.filter(l => l.has_vin).length;
            const withFP = listings.filter(l => l.has_floorplan).length;
            const withLength = listings.filter(l => l.length && l.length > 0).length;
            const with35Photos = listings.filter(l => l.photo_count >= 35).length;
            const qualityScore = total > 0 ? (withPrice + withVin + withFP + withLength + with35Photos) / (total * 5) * 100 : 0;

            const safeAvg = (arr) => arr.length > 0 ? arr.reduce((a,b) => a+b, 0) / arr.length : 0;

            return { total, avgRank: safeAvg(ranks), avgViews: safeAvg(views), avgSaves: safeAvg(saves), avgPhotos: safeAvg(photos), premiumPct: total > 0 ? (premium / total) * 100 : 0, qualityScore: isNaN(qualityScore) ? 0 : qualityScore, tp, p, s };
        }

        function renderTable() {
            const tbody = document.getElementById('table-body');
            const sorted = sortListings(filteredListings);

            tbody.innerHTML = sorted.map(l => {
                const tierLabel = { 'top_premium': 'Top Premium', 'premium': 'Premium', 'standard': 'Standard' }[l.tier] || 'Standard';
                const tierClass = { 'top_premium': 'tier-tp', 'premium': 'tier-p', 'standard': 'tier-s' }[l.tier] || 'tier-s';
                const posClass = getPositionClass(l.position);
                const photoClass = l.photo_count >= 35 ? 'text-success' : l.photo_count >= 20 ? 'text-warning' : 'text-danger';
                const viewsClass = l.views >= 100 ? 'text-success' : l.views >= 30 ? 'text-warning' : l.views != null ? 'text-danger' : '';
                const savesClass = l.saves >= 5 ? 'text-success' : l.saves >= 1 ? 'text-warning' : '';
                const daysClass = l.days_listed > 90 ? 'text-danger' : l.days_listed > 30 ? 'text-warning' : l.days_listed != null ? 'text-success' : '';
                const price = l.price ? `$${Number(l.price).toLocaleString()}` : '<span class="text-danger">-</span>';
                const improvementList = l.improvements || [];
                const actions = improvementList.length > 0 ? improvementList.map(imp => `<div class="action-item">${escapeHtml(imp)}</div>`).join('') : '<span class="text-success">OK</span>';
                const rel = l.relevance_score ? Math.round(l.relevance_score) : '-';
                const merch = l.merch_score ? Math.round(l.merch_score) : '-';
                const vinDisplay = l.vin ? `<span class="vin-text">${escapeHtml(l.vin)}</span>` : '<span class="text-muted">-</span>';
                const stockDisplay = l.stock_number ? `<span class="small">${escapeHtml(l.stock_number)}</span>` : '<span class="text-muted">-</span>';
                const priceDropDisplay = l.price_drop_date ? new Date(l.price_drop_date).toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: '2-digit' }) : '-';

                return `<tr data-url="${l.listing_url || ''}">
                    <td class="text-center fw-bold">${l.rank || '-'}</td>
                    <td>${l.year || '-'}</td>
                    <td>${escapeHtml(l.make || '')}</td>
                    <td><a href="${l.listing_url || '#'}" target="_blank" class="listing-link">${escapeHtml((l.model || '').substring(0, 18))}</a></td>
                    <td class="small">${stockDisplay}</td>
                    <td class="vin-cell">${vinDisplay}</td>
                    <td class="text-end">${price}</td>
                    <td class="text-center text-primary fw-bold">${rel}</td>
                    <td class="text-center text-muted">${merch}</td>
                    <td class="text-center">${l.length ? l.length + "'" : '-'}</td>
                    <td class="text-center ${photoClass}">${l.photo_count || 0}</td>
                    <td class="text-center"><span class="yn-badge ${l.has_floorplan ? 'yn-yes' : 'yn-no'}">${l.has_floorplan ? 'Y' : 'N'}</span></td>
                    <td class="text-center ${viewsClass}">${l.views != null ? l.views : '-'}</td>
                    <td class="text-center ${savesClass}">${l.saves != null ? l.saves : '-'}</td>
                    <td class="text-center"><span class="badge ${tierClass}" style="font-size:0.6rem">${tierLabel}</span></td>
                    <td class="text-center"><span class="badge ${posClass}" style="font-size:0.65rem">${l.position || '-'}</span></td>
                    <td class="text-center ${daysClass}">${l.days_listed != null ? l.days_listed : '-'}</td>
                    <td class="text-center small">${priceDropDisplay}</td>
                    <td class="small">${l.city ? escapeHtml(l.city) + ', ' : ''}${l.state || '-'}</td>
                    <td class="small">${escapeHtml((l.dealer_name || '').substring(0, 18))}</td>
                    <td class="actions-cell">${actions}</td>
                </tr>`;
            }).join('');

            document.querySelectorAll('#data-table th').forEach(th => {
                th.classList.remove('sort-asc', 'sort-desc');
                if (th.dataset.sort === sortColumn) th.classList.add(sortDirection === 'asc' ? 'sort-asc' : 'sort-desc');
            });

            setupRowHover();
        }

        function renderDealerView() {
            const container = document.getElementById('dealer-view');
            const dealerMap = {};
            filteredListings.forEach(l => {
                const dealer = l.dealer_name || 'Unknown Dealer';
                if (!dealerMap[dealer]) dealerMap[dealer] = { name: dealer, listings: [], id: l.dealer_id };
                dealerMap[dealer].listings.push(l);
            });

            const avgAll = calcStats(filteredListings);
            const dealers = Object.values(dealerMap).sort((a, b) => b.listings.length - a.listings.length);

            const fmt = (val, decimals = 0) => val == null || isNaN(val) ? '-' : val.toFixed(decimals);
            const calcDelta = (dealerVal, allVal, inverse = false) => {
                if (dealerVal == null || allVal == null || isNaN(dealerVal) || isNaN(allVal)) return { value: '-', cls: '', sign: '' };
                const diff = inverse ? (allVal - dealerVal) : (dealerVal - allVal);
                const cls = diff > 0.1 ? 'positive' : diff < -0.1 ? 'negative' : '';
                const sign = diff > 0.1 ? '+' : '';
                return { value: diff.toFixed(1), cls, sign };
            };

            container.innerHTML = dealers.map((d, idx) => {
                const avg = calcStats(d.listings);
                const rankDelta = calcDelta(avg.avgRank, avgAll.avgRank, true);
                const viewsDelta = calcDelta(avg.avgViews, avgAll.avgViews);
                const photosDelta = calcDelta(avg.avgPhotos, avgAll.avgPhotos);
                const savesDelta = calcDelta(avg.avgSaves, avgAll.avgSaves);

                return `<div class="dealer-section">
                    <div class="dealer-header" onclick="toggleDealer(${idx})">
                        <div class="dealer-name">${escapeHtml(d.name)}</div>
                        <div class="dealer-stats">
                            <div class="dealer-stat"><div class="dealer-stat-value">${d.listings.length}</div><div class="dealer-stat-label">Units</div></div>
                            <div class="dealer-stat"><div class="dealer-stat-value">${fmt(avg.avgRank)}</div><div class="dealer-stat-label">Avg Rank</div><div class="dealer-stat-delta ${rankDelta.cls}">${rankDelta.sign}${rankDelta.value}</div></div>
                            <div class="dealer-stat"><div class="dealer-stat-value">${fmt(avg.avgPhotos)}</div><div class="dealer-stat-label">Photos</div><div class="dealer-stat-delta ${photosDelta.cls}">${photosDelta.sign}${photosDelta.value}</div></div>
                            <div class="dealer-stat"><div class="dealer-stat-value">${fmt(avg.avgViews)}</div><div class="dealer-stat-label">Views</div><div class="dealer-stat-delta ${viewsDelta.cls}">${viewsDelta.sign}${viewsDelta.value}</div></div>
                            <div class="dealer-stat"><div class="dealer-stat-value">${fmt(avg.avgSaves, 1)}</div><div class="dealer-stat-label">Saves</div><div class="dealer-stat-delta ${savesDelta.cls}">${savesDelta.sign}${savesDelta.value}</div></div>
                            <div class="dealer-stat"><div class="dealer-stat-value">${fmt(avg.premiumPct)}%</div><div class="dealer-stat-label">Premium</div></div>
                        </div>
                    </div>
                    <div class="dealer-listings" id="dealer-${idx}" style="display: none;">
                        <div class="table-wrapper" style="max-height: 400px;">
                            <table class="table table-striped table-hover mb-0">
                                <thead><tr><th>Rank</th><th>Year</th><th>Model</th><th>Stock#</th><th>VIN</th><th>Price</th><th>Rel</th><th>Merch</th><th>Length</th><th>Photos</th><th>FP</th><th>Views</th><th>Saves</th><th>Days</th><th>Location</th><th>Tier</th><th>Position</th><th>Actions</th></tr></thead>
                                <tbody>${d.listings.sort((a,b) => a.rank - b.rank).map(l => {
                                    const tierLabel = { 'top_premium': 'Top Premium', 'premium': 'Premium', 'standard': 'Standard' }[l.tier] || 'Standard';
                                    const tierClass = { 'top_premium': 'tier-tp', 'premium': 'tier-p', 'standard': 'tier-s' }[l.tier] || 'tier-s';
                                    const posClass = getPositionClass(l.position);
                                    const photoClass = l.photo_count >= 35 ? 'text-success' : l.photo_count >= 20 ? 'text-warning' : 'text-danger';
                                    const viewsClass = l.views >= 100 ? 'text-success' : l.views >= 30 ? 'text-warning' : l.views != null ? 'text-danger' : '';
                                    const daysClass = l.days_listed > 90 ? 'text-danger' : l.days_listed > 30 ? 'text-warning' : 'text-success';
                                    const price = l.price ? `$${Number(l.price).toLocaleString()}` : '-';
                                    const improvementList = l.improvements || [];
                                    const actions = improvementList.length > 0 ? improvementList.map(imp => `<div class="action-item">${escapeHtml(imp)}</div>`).join('') : '<span class="text-success">OK</span>';
                                    const vinDisplay = l.vin ? `<span class="vin-text">${escapeHtml(l.vin)}</span>` : '-';
                                    return `<tr data-url="${l.listing_url || ''}">
                                        <td class="text-center fw-bold">${l.rank}</td><td>${l.year}</td>
                                        <td><a href="${l.listing_url || '#'}" target="_blank" class="listing-link">${escapeHtml((l.model || '').substring(0, 18))}</a></td>
                                        <td class="small">${l.stock_number || '-'}</td><td class="vin-cell">${vinDisplay}</td>
                                        <td class="text-end">${price}</td><td class="text-center text-primary fw-bold">${l.relevance_score ? Math.round(l.relevance_score) : '-'}</td>
                                        <td class="text-center text-muted">${l.merch_score ? Math.round(l.merch_score) : '-'}</td>
                                        <td class="text-center">${l.length ? l.length + "'" : '-'}</td><td class="text-center ${photoClass}">${l.photo_count || 0}</td>
                                        <td class="text-center"><span class="yn-badge ${l.has_floorplan ? 'yn-yes' : 'yn-no'}">${l.has_floorplan ? 'Y' : 'N'}</span></td>
                                        <td class="text-center ${viewsClass}">${l.views != null ? l.views : '-'}</td>
                                        <td class="text-center">${l.saves != null ? l.saves : '-'}</td>
                                        <td class="text-center ${daysClass}">${l.days_listed != null ? l.days_listed : '-'}</td>
                                        <td class="small">${l.city ? escapeHtml(l.city) + ', ' : ''}${l.state || '-'}</td>
                                        <td class="text-center"><span class="badge ${tierClass}" style="font-size:0.7rem">${tierLabel}</span></td>
                                        <td class="text-center"><span class="badge ${posClass}" style="font-size:0.7rem">${l.position}</span></td>
                                        <td class="actions-cell">${actions}</td>
                                    </tr>`;
                                }).join('')}</tbody>
                            </table>
                        </div>
                    </div>
                </div>`;
            }).join('');

            setupRowHover();
        }

        function toggleDealer(idx) {
            const el = document.getElementById('dealer-' + idx);
            el.style.display = el.style.display === 'none' ? 'block' : 'none';
            setupRowHover();
        }

        function getPositionClass(position) {
            return { 'Dominant': 'badge-dominant', 'Strong': 'badge-strong', 'Competitive': 'badge-competitive', 'Neutral': 'badge-neutral', 'At Risk': 'badge-atrisk', 'Disadvantaged': 'badge-disadvantaged' }[position] || 'bg-secondary';
        }

        function escapeHtml(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        function populateFilters() {
            const brands = [...new Set(allListings.map(l => l.make).filter(Boolean))].sort();
            const brandSelect = document.getElementById('filter-brand');
            brands.forEach(b => { const opt = document.createElement('option'); opt.value = b; opt.textContent = b; brandSelect.appendChild(opt); });

            const years = [...new Set(allListings.map(l => l.year).filter(Boolean))].sort((a, b) => b - a);
            const yearSelect = document.getElementById('filter-year');
            years.forEach(y => { const opt = document.createElement('option'); opt.value = y; opt.textContent = y; yearSelect.appendChild(opt); });

            const searchZips = [...new Set(allListings.map(l => l.search_zip).filter(Boolean))].sort();
            const zipSelect = document.getElementById('filter-zip');
            searchZips.forEach(z => { const opt = document.createElement('option'); opt.value = z; const count = allListings.filter(l => l.search_zip === z).length; opt.textContent = `${z} (${count})`; zipSelect.appendChild(opt); });

            const searchTypes = [...new Set(allListings.map(l => l.search_type).filter(Boolean))].sort();
            const typeSelect = document.getElementById('filter-type');
            searchTypes.forEach(t => { const opt = document.createElement('option'); opt.value = t; const count = allListings.filter(l => l.search_type === t).length; opt.textContent = `${t} (${count})`; typeSelect.appendChild(opt); });

            const regions = [...new Set(allListings.map(l => l.region).filter(Boolean))].sort();
            const regionSelect = document.getElementById('filter-region');
            regions.forEach(r => { const opt = document.createElement('option'); opt.value = r; opt.textContent = r; regionSelect.appendChild(opt); });
        }

        function applyFilters() {
            const brand = document.getElementById('filter-brand').value;
            const tier = document.getElementById('filter-tier').value;
            const year = document.getElementById('filter-year').value;
            const position = document.getElementById('filter-position').value;
            const dealer = document.getElementById('filter-dealer').value.toLowerCase();
            const thorOnly = document.getElementById('filter-thor').checked;
            const zip = document.getElementById('filter-zip').value;
            const type = document.getElementById('filter-type').value;
            const region = document.getElementById('filter-region').value;

            filteredListings = allListings.filter(l => {
                if (brand !== 'all' && l.make !== brand) return false;
                if (tier !== 'all' && l.tier !== tier) return false;
                if (year !== 'all' && l.year != year) return false;
                if (position !== 'all' && l.position !== position) return false;
                if (dealer && !(l.dealer_name || '').toLowerCase().includes(dealer)) return false;
                if (thorOnly && !l.is_thor) return false;
                if (zip !== 'all' && l.search_zip !== zip) return false;
                if (type !== 'all' && l.search_type !== type) return false;
                if (region !== 'all' && l.region !== region) return false;
                return true;
            });

            const queryCount = document.getElementById('query-count');
            if (queryCount) queryCount.textContent = `${filteredListings.length} listings`;

            renderMeta();
            renderStats();
            renderCurrentView();
        }

        function resetFilters() {
            document.getElementById('filter-brand').value = 'all';
            document.getElementById('filter-tier').value = 'all';
            document.getElementById('filter-year').value = 'all';
            document.getElementById('filter-position').value = 'all';
            document.getElementById('filter-zip').value = 'all';
            document.getElementById('filter-type').value = 'all';
            document.getElementById('filter-region').value = 'all';
            document.getElementById('filter-dealer').value = '';
            document.getElementById('filter-thor').checked = false;
            applyFilters();
        }

        function sortListings(listings) {
            return [...listings].sort((a, b) => {
                let valA = a[sortColumn], valB = b[sortColumn];
                if (valA == null) valA = sortDirection === 'asc' ? Infinity : -Infinity;
                if (valB == null) valB = sortDirection === 'asc' ? Infinity : -Infinity;
                if (typeof valA === 'number' && typeof valB === 'number') return sortDirection === 'asc' ? valA - valB : valB - valA;
                valA = String(valA).toLowerCase(); valB = String(valB).toLowerCase();
                if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
                if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
                return 0;
            });
        }

        function handleSort(column) {
            if (sortColumn === column) sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            else { sortColumn = column; sortDirection = 'asc'; }
            renderTable();
        }

        function setupRowHover() {
            const preview = document.getElementById('image-preview');
            document.querySelectorAll('tr[data-url]').forEach(row => {
                row.addEventListener('mouseenter', (e) => { if (row.dataset.url) { preview.style.display = 'block'; updatePreviewPosition(e); } });
                row.addEventListener('mousemove', updatePreviewPosition);
                row.addEventListener('mouseleave', () => { preview.style.display = 'none'; });
                row.addEventListener('click', (e) => { if (e.target.tagName !== 'A') { const url = row.dataset.url; if (url) window.open(url, '_blank'); } });
                row.style.cursor = 'pointer';
            });
        }

        function updatePreviewPosition(e) {
            const preview = document.getElementById('image-preview');
            preview.style.left = Math.min(e.clientX + 20, window.innerWidth - 370) + 'px';
            preview.style.top = Math.min(e.clientY + 20, window.innerHeight - 300) + 'px';
        }

        function exportCSV() {
            const headers = ['Rank', 'Year', 'Make', 'Model', 'Stock Number', 'VIN', 'Price', 'Relevance', 'Merch', 'Length', 'Photos', 'Floorplan', 'Views', 'Saves', 'Tier', 'Tier Ceiling', 'Position', 'Days Listed', 'Price Drop Date', 'Dealer', 'City', 'State', 'Region', 'Improvements'];
            const rows = filteredListings.map(l => [l.rank, l.year, `"${(l.make || '').replace(/"/g, '""')}"`, `"${(l.model || '').replace(/"/g, '""')}"`, `"${(l.stock_number || '').replace(/"/g, '""')}"`, `"${(l.vin || '').replace(/"/g, '""')}"`, l.price || '', l.relevance_score ? Math.round(l.relevance_score) : '', l.merch_score ? Math.round(l.merch_score) : '', l.length || '', l.photo_count || 0, l.has_floorplan ? 'Yes' : 'No', l.views ?? '', l.saves ?? '', l.tier, l.tier_ceiling || '', l.position, l.days_listed ?? '', l.price_drop_date ? new Date(l.price_drop_date).toISOString().split('T')[0] : '', `"${(l.dealer_name || '').replace(/"/g, '""')}"`, `"${(l.city || '').replace(/"/g, '""')}"`, l.state || '', l.region || '', `"${(l.improvements || []).join('; ').replace(/"/g, '""')}"`]);
            const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\\n');
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `rv_export_${new Date().toISOString().slice(0, 10)}.csv`;
            a.click();
            URL.revokeObjectURL(url);
        }

        function setupEventListeners() {
            document.getElementById('filter-brand').addEventListener('change', applyFilters);
            document.getElementById('filter-tier').addEventListener('change', applyFilters);
            document.getElementById('filter-year').addEventListener('change', applyFilters);
            document.getElementById('filter-position').addEventListener('change', applyFilters);
            document.getElementById('filter-zip').addEventListener('change', applyFilters);
            document.getElementById('filter-type').addEventListener('change', applyFilters);
            document.getElementById('filter-region').addEventListener('change', applyFilters);
            document.getElementById('filter-dealer').addEventListener('input', applyFilters);
            document.getElementById('filter-thor').addEventListener('change', applyFilters);
            document.getElementById('btn-reset').addEventListener('click', resetFilters);
            document.getElementById('btn-export').addEventListener('click', exportCSV);
            document.querySelectorAll('#data-table th[data-sort]').forEach(th => { th.addEventListener('click', () => handleSort(th.dataset.sort)); });
        }

        init();
    </script>
</body>
</html>'''


# =============================================================================
# CLEANUP
# =============================================================================

def cleanup_old_files(output_dir: Path, keep_data: bool = False):
    """Remove old data files, keeping only the latest of each type."""
    if keep_data:
        print("  Keeping all data files (--keep-data)")
        return

    # Find files to clean
    patterns = [
        ('ranked_listings_*.json', 1),  # Keep 1
        ('ranked_listings_*.csv', 0),   # Remove all CSV
        ('engagement_stats_*.json', 1), # Keep 1
    ]

    for pattern, keep_count in patterns:
        files = sorted(output_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        to_delete = files[keep_count:] if keep_count > 0 else files

        for f in to_delete:
            print(f"  Removing: {f.name}")
            f.unlink()


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Build standalone RV dashboard')
    parser.add_argument('--input', '-i', help='Input ranked_listings JSON file')
    parser.add_argument('--keep-data', action='store_true', help='Keep old data files')
    args = parser.parse_args()

    # Paths
    script_dir = Path(__file__).parent
    output_dir = script_dir.parent.parent / 'output'
    reports_dir = output_dir / 'reports'
    reports_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("Building RV Trader Dashboard")
    print("=" * 60)

    # Step 1: Consolidate data
    print("\n1. Loading and consolidating data...")
    data = consolidate(output_dir, args.input)

    # Step 2: Generate HTML with embedded data
    print("\n2. Generating standalone HTML...")
    html_template = get_html_template()
    json_data = json.dumps(data, ensure_ascii=False)
    html_content = html_template.replace('__EMBEDDED_DATA__', json_data)

    output_path = reports_dir / 'rv_dashboard_standalone.html'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"  Output: {output_path}")
    print(f"  Size: {len(html_content) / 1024:.1f} KB")

    # Step 3: Cleanup old files
    print("\n3. Cleaning up old files...")
    cleanup_old_files(output_dir, args.keep_data)

    # Summary
    print("\n" + "=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    print(f"  Dashboard: {output_path}")
    print(f"  Listings: {data['summary']['total_listings']}")
    print(f"  Thor brands: {data['summary']['thor_count']} ({data['summary']['thor_pct']}%)")
    print(f"\n  Open in browser: file:///{output_path.as_posix()}")


if __name__ == '__main__':
    main()
