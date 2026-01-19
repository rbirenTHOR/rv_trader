"""
Regional Summary Report Generator

Generates hierarchical reports for Thor Industries brands:
  - Manufacturer Report (Jayco, Keystone, Airstream, etc.)
    - Regional Summary (Midwest, Southeast, etc.)
      - Dealer Scorecards
        - Listing Details

Usage:
    python regional_summary.py                    # All manufacturers, all regions
    python regional_summary.py --brand Jayco      # Single manufacturer
    python regional_summary.py --region Midwest   # Single region
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import html

# Current model year for competitive position
CURRENT_MODEL_YEAR = datetime.now().year

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
STATE_TO_REGION = {
    # Midwest
    'IL': 'Midwest', 'IN': 'Midwest', 'IA': 'Midwest', 'KS': 'Midwest',
    'MI': 'Midwest', 'MN': 'Midwest', 'MO': 'Midwest', 'NE': 'Midwest',
    'ND': 'Midwest', 'OH': 'Midwest', 'SD': 'Midwest', 'WI': 'Midwest',
    # Northeast
    'CT': 'Northeast', 'DE': 'Northeast', 'ME': 'Northeast', 'MD': 'Northeast',
    'MA': 'Northeast', 'NH': 'Northeast', 'NJ': 'Northeast', 'NY': 'Northeast',
    'PA': 'Northeast', 'RI': 'Northeast', 'VT': 'Northeast',
    # Southeast
    'AL': 'Southeast', 'AR': 'Southeast', 'FL': 'Southeast', 'GA': 'Southeast',
    'KY': 'Southeast', 'LA': 'Southeast', 'MS': 'Southeast', 'NC': 'Southeast',
    'SC': 'Southeast', 'TN': 'Southeast', 'VA': 'Southeast', 'WV': 'Southeast',
    # Southwest
    'AZ': 'Southwest', 'NM': 'Southwest', 'OK': 'Southwest', 'TX': 'Southwest',
    # West
    'AK': 'West', 'CA': 'West', 'CO': 'West', 'HI': 'West', 'ID': 'West',
    'MT': 'West', 'NV': 'West', 'OR': 'West', 'UT': 'West', 'WA': 'West', 'WY': 'West',
}

# Ranking points (true total impact with merch multiplier)
RANKING_FACTORS = {
    'has_price': {'pts': 295, 'label': 'Price Listed', 'action': 'Add listing price'},
    'has_vin': {'pts': 286, 'label': 'VIN Disclosed', 'action': 'Disclose VIN number'},
    'photos_35': {'pts': 801, 'label': '35+ Photos', 'action': 'Upload more photos'},
    'has_floorplan': {'pts': 292, 'label': 'Floorplan', 'action': 'Add floorplan image'},
    'has_length': {'pts': 162, 'label': 'Length Spec', 'action': 'Add vehicle length'},
}

POINTS_PER_POSITION = 15  # ~15 points = 1 rank position


# =============================================================================
# ENGAGEMENT & HELPER FUNCTIONS
# =============================================================================

def load_engagement_data(output_dir: Path) -> Dict[str, Dict]:
    """Load engagement data (views/saves) from the latest engagement JSON file."""
    engagement_files = sorted(output_dir.glob('engagement_stats_*.json'), reverse=True)
    if not engagement_files:
        return {}

    engagement_path = engagement_files[0]
    print(f"Loading engagement data: {engagement_path.name}")

    try:
        with open(engagement_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        engagement = {}
        if 'results' in data and isinstance(data['results'], list):
            for item in data['results']:
                listing_id = str(item.get('id', ''))
                if listing_id:
                    engagement[listing_id] = {
                        'views': item.get('views', 0),
                        'saves': item.get('saves', 0),
                    }

        print(f"  Loaded engagement for {len(engagement)} listings")
        return engagement
    except Exception as e:
        print(f"  Warning: Could not load engagement data: {e}")
        return {}


def get_tier(listing: Dict) -> str:
    """Get tier abbreviation (TP/P/S)."""
    if listing.get('is_top_premium'):
        return 'TP'
    elif listing.get('is_premium'):
        return 'P'
    return 'S'


def get_competitive_position(listing: Dict) -> str:
    """Get competitive position based on tier and model year."""
    year = listing.get('year')
    if not year:
        return 'Unknown'

    is_top_premium = listing.get('is_top_premium')
    is_premium = listing.get('is_premium')

    if is_top_premium:
        if year >= CURRENT_MODEL_YEAR:
            return 'Dominant'
        elif year == CURRENT_MODEL_YEAR - 1:
            return 'Strong'
        else:
            return 'Disadvantaged'
    elif is_premium:
        if year >= CURRENT_MODEL_YEAR:
            return 'Strong'
        elif year == CURRENT_MODEL_YEAR - 1:
            return 'Neutral'
        else:
            return 'Disadvantaged'
    else:  # Standard
        if year >= CURRENT_MODEL_YEAR:
            return 'Competitive'
        elif year == CURRENT_MODEL_YEAR - 1:
            return 'At Risk'
        else:
            return 'Disadvantaged'


def calculate_days_listed(create_date: str) -> Optional[int]:
    """Calculate days since listing was created."""
    if not create_date:
        return None
    try:
        # Clean the date string - remove timezone suffixes
        clean_date = create_date.split('.')[0].replace('Z', '').split('+')[0].split('-05:00')[0]
        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%m/%d/%Y']:
            try:
                created = datetime.strptime(clean_date, fmt)
                return (datetime.now() - created).days
            except ValueError:
                continue
        return None
    except Exception:
        return None


def parse_price_drop_date(price_drop_date: str) -> Optional[str]:
    """Parse price drop date and return formatted string."""
    if not price_drop_date:
        return None
    try:
        # Clean the date string
        clean_date = price_drop_date.split('.')[0].replace('Z', '').split('+')[0].split('-05:00')[0]
        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
            try:
                dt = datetime.strptime(clean_date, fmt)
                return dt.strftime('%m/%d')
            except ValueError:
                continue
        return None
    except Exception:
        return None


def get_position_badge_class(position: str) -> str:
    """Get CSS class for position badge."""
    return {
        'Dominant': 'badge-a',
        'Strong': 'badge-b',
        'Competitive': 'badge-c',
        'Neutral': 'badge-c',
        'At Risk': 'badge-d',
        'Disadvantaged': 'badge-f',
    }.get(position, 'badge-f')


# Global engagement data (set during report generation)
_engagement_data = {}


# =============================================================================
# DATA LOADING
# =============================================================================

def load_csv(csv_path: str) -> Tuple[List[Dict], Dict]:
    """Load and parse CSV file. Returns (listings, search_metadata)."""
    listings = []
    search_metadata = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Capture search metadata from first row
            if not search_metadata:
                search_metadata = {
                    'zip': row.get('search_zip', ''),
                    'type': row.get('search_type', ''),
                    'radius': row.get('search_radius', ''),
                    'condition': row.get('search_condition', ''),
                }

            # Parse numeric fields
            row['rank'] = safe_int(row.get('rank'))
            row['price'] = safe_float(row.get('price'))
            row['photo_count'] = safe_int(row.get('photo_count')) or 0
            row['length'] = safe_float(row.get('length'))
            row['year'] = safe_int(row.get('year'))
            row['relevance_score'] = safe_float(row.get('relevance_score'))
            row['merch_score'] = safe_float(row.get('merch_score'))

            # Parse boolean fields
            row['is_premium'] = row.get('is_premium') in ('1', 'True', 'true', True)
            row['is_top_premium'] = row.get('is_top_premium') in ('1', 'True', 'true', True)

            # Derived fields
            row['has_price'] = bool(row['price'] and row['price'] > 0)
            row['has_vin'] = bool(row.get('vin'))
            row['has_floorplan'] = bool(row.get('floorplan_id'))
            row['has_length'] = bool(row['length'] and row['length'] > 0)
            row['photos_35'] = row['photo_count'] >= 35

            # Brand and region
            row['thor_brand'] = identify_thor_brand(row.get('make', ''))
            row['region'] = STATE_TO_REGION.get(row.get('state', ''), 'Unknown')

            listings.append(row)
    return listings, search_metadata


def safe_int(val) -> Optional[int]:
    if val is None or val == '':
        return None
    try:
        return int(float(val))
    except:
        return None


def safe_float(val) -> Optional[float]:
    if val is None or val == '':
        return None
    try:
        return float(val)
    except:
        return None


def identify_thor_brand(make: str) -> Optional[str]:
    if not make:
        return None
    make_lower = make.lower().strip()
    for pattern, brand_name in THOR_BRANDS.items():
        if pattern in make_lower:
            return brand_name
    return None


# =============================================================================
# METRICS CALCULATION
# =============================================================================

def calculate_metrics(listings: List[Dict]) -> Dict:
    """Calculate comprehensive metrics for a group of listings."""
    global _engagement_data

    if not listings:
        return {'count': 0}

    total = len(listings)
    ranks = [l['rank'] for l in listings if l.get('rank')]
    photos = [l['photo_count'] for l in listings]

    premium = sum(1 for l in listings if l.get('is_premium'))
    with_price = sum(1 for l in listings if l.get('has_price'))
    with_vin = sum(1 for l in listings if l.get('has_vin'))
    with_floorplan = sum(1 for l in listings if l.get('has_floorplan'))
    with_length = sum(1 for l in listings if l.get('has_length'))
    with_photos_35 = sum(1 for l in listings if l.get('photos_35'))

    # Calculate quality score (% complete)
    quality_score = round((with_price + with_vin + with_floorplan + with_length + with_photos_35) / (total * 5) * 100, 1)

    # Calculate quick wins
    quick_wins = {
        'missing_price': total - with_price,
        'missing_vin': total - with_vin,
        'missing_floorplan': total - with_floorplan,
        'missing_length': total - with_length,
        'missing_photos_35': total - with_photos_35,
    }

    # Estimate total rank gain available
    total_rank_gain = (
        quick_wins['missing_price'] * RANKING_FACTORS['has_price']['pts'] +
        quick_wins['missing_vin'] * RANKING_FACTORS['has_vin']['pts'] +
        quick_wins['missing_floorplan'] * RANKING_FACTORS['has_floorplan']['pts'] +
        quick_wins['missing_length'] * RANKING_FACTORS['has_length']['pts'] +
        quick_wins['missing_photos_35'] * RANKING_FACTORS['photos_35']['pts']
    ) // POINTS_PER_POSITION

    # Calculate engagement metrics
    total_views = 0
    total_saves = 0
    listings_with_engagement = 0
    for l in listings:
        listing_id = str(l.get('id', ''))
        eng = _engagement_data.get(listing_id, {})
        if 'views' in eng:
            total_views += eng.get('views', 0)
            total_saves += eng.get('saves', 0)
            listings_with_engagement += 1

    # Calculate competitive positions
    positions = {'Dominant': 0, 'Strong': 0, 'Competitive': 0, 'Neutral': 0, 'At Risk': 0, 'Disadvantaged': 0}
    for l in listings:
        pos = get_competitive_position(l)
        if pos in positions:
            positions[pos] += 1

    return {
        'count': total,
        'avg_rank': round(sum(ranks) / len(ranks), 1) if ranks else 999,
        'best_rank': min(ranks) if ranks else 999,
        'worst_rank': max(ranks) if ranks else 999,
        'avg_photos': round(sum(photos) / len(photos), 1) if photos else 0,
        'premium_count': premium,
        'pct_premium': round(premium / total * 100, 1),
        'pct_price': round(with_price / total * 100, 1),
        'pct_vin': round(with_vin / total * 100, 1),
        'pct_floorplan': round(with_floorplan / total * 100, 1),
        'pct_length': round(with_length / total * 100, 1),
        'pct_photos_35': round(with_photos_35 / total * 100, 1),
        'quality_score': quality_score,
        'quick_wins': quick_wins,
        'total_rank_gain': total_rank_gain,
        'total_views': total_views,
        'total_saves': total_saves,
        'avg_views': round(total_views / listings_with_engagement, 1) if listings_with_engagement else 0,
        'avg_saves': round(total_saves / listings_with_engagement, 1) if listings_with_engagement else 0,
        'positions': positions,
    }


def calculate_listing_actions(listing: Dict) -> List[Dict]:
    """Calculate specific actions needed for a listing."""
    actions = []

    if not listing.get('has_price'):
        f = RANKING_FACTORS['has_price']
        actions.append({
            'action': f['action'],
            'pts': f['pts'],
            'positions': f['pts'] // POINTS_PER_POSITION,
        })

    if not listing.get('has_vin'):
        f = RANKING_FACTORS['has_vin']
        actions.append({
            'action': f['action'],
            'pts': f['pts'],
            'positions': f['pts'] // POINTS_PER_POSITION,
        })

    if not listing.get('photos_35'):
        f = RANKING_FACTORS['photos_35']
        needed = 35 - listing.get('photo_count', 0)
        actions.append({
            'action': f"{f['action']} ({needed} more needed)",
            'pts': f['pts'],
            'positions': f['pts'] // POINTS_PER_POSITION,
        })

    if not listing.get('has_floorplan'):
        f = RANKING_FACTORS['has_floorplan']
        actions.append({
            'action': f['action'],
            'pts': f['pts'],
            'positions': f['pts'] // POINTS_PER_POSITION,
        })

    if not listing.get('has_length'):
        f = RANKING_FACTORS['has_length']
        actions.append({
            'action': f['action'],
            'pts': f['pts'],
            'positions': f['pts'] // POINTS_PER_POSITION,
        })

    # Sort by points (highest impact first)
    actions.sort(key=lambda x: x['pts'], reverse=True)
    return actions


def calculate_grade(metrics: Dict) -> Tuple[str, str]:
    """Calculate letter grade and color."""
    score = metrics.get('quality_score', 0)
    if score >= 90:
        return 'A', '#22c55e'
    elif score >= 80:
        return 'B', '#84cc16'
    elif score >= 70:
        return 'C', '#eab308'
    elif score >= 60:
        return 'D', '#f97316'
    else:
        return 'F', '#ef4444'


# =============================================================================
# HTML GENERATION
# =============================================================================

def generate_manufacturer_report(brand: str, regions: Dict[str, List[Dict]],
                                  all_listings: List[Dict], search_metadata: Dict = None) -> str:
    """Generate complete manufacturer report with regional breakdown."""

    # Calculate manufacturer-level metrics
    brand_listings = []
    for region_listings in regions.values():
        brand_listings.extend(region_listings)

    brand_metrics = calculate_metrics(brand_listings)
    brand_grade, brand_color = calculate_grade(brand_metrics)

    # Calculate competitor metrics for comparison
    competitor_listings = [l for l in all_listings if not l.get('thor_brand')]
    comp_metrics = calculate_metrics(competitor_listings) if competitor_listings else {'count': 0, 'avg_rank': 0}

    # Generate regional sections
    regional_sections = []
    for region_name in sorted(regions.keys()):
        region_listings = regions[region_name]
        regional_sections.append(generate_region_section(region_name, region_listings, brand_metrics))

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Format search metadata
    search_meta = search_metadata or {}
    total_in_radius = len(all_listings)
    search_info = []
    if search_meta.get('zip'):
        search_info.append(f"Zip: {search_meta['zip']}")
    if search_meta.get('type'):
        search_info.append(f"Type: {search_meta['type']}")
    if search_meta.get('radius'):
        search_info.append(f"Radius: {search_meta['radius']}mi")
    if search_meta.get('condition'):
        cond = 'New' if search_meta['condition'] == 'N' else 'Used' if search_meta['condition'] == 'U' else search_meta['condition']
        search_info.append(f"Condition: {cond}")
    search_info.append(f"<strong>{total_in_radius} total listings in search</strong>")
    search_info_str = " | ".join(search_info) if search_info else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand} - Regional Performance Report</title>
    <style>
        :root {{
            --primary: #0f172a;
            --primary-light: #1e293b;
            --accent: #3b82f6;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --gray-50: #f8fafc;
            --gray-100: #f1f5f9;
            --gray-200: #e2e8f0;
            --gray-300: #cbd5e1;
            --gray-500: #64748b;
            --gray-700: #334155;
            --gray-900: #0f172a;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', sans-serif;
            background: var(--gray-100);
            color: var(--gray-900);
            line-height: 1.5;
            font-size: 14px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}

        /* Header */
        .header {{
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            color: white;
            padding: 28px 32px;
            border-radius: 16px;
            margin-bottom: 24px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }}
        .header-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }}
        .header h1 {{ font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; }}
        .header .subtitle {{ opacity: 0.8; font-size: 0.9rem; margin-top: 4px; }}
        .header .search-meta {{
            margin-top: 8px;
            padding: 8px 12px;
            background: rgba(255,255,255,0.1);
            border-radius: 6px;
            font-size: 0.8rem;
            display: inline-block;
        }}
        .grade-badge {{
            min-width: 72px;
            height: 72px;
            border-radius: 16px;
            background: {brand_color};
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }}
        .grade-letter {{ font-size: 1.75rem; line-height: 1; }}
        .grade-label {{ font-size: 0.65rem; opacity: 0.9; margin-top: 2px; }}

        /* Summary Stats */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 12px;
            margin-top: 20px;
        }}
        .summary-stat {{
            background: rgba(255,255,255,0.08);
            padding: 14px 12px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .stat-value {{ font-size: 1.5rem; font-weight: 700; line-height: 1.2; }}
        .stat-label {{ font-size: 0.7rem; opacity: 0.75; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.05em; }}
        .stat-compare {{ font-size: 0.7rem; margin-top: 4px; font-weight: 500; }}
        .stat-compare.positive {{ color: #86efac; }}
        .stat-compare.negative {{ color: #fca5a5; }}

        /* Cards */
        .card {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            margin-bottom: 20px;
            border: 1px solid var(--gray-200);
        }}
        .card-header {{
            background: var(--primary);
            color: white;
            padding: 14px 20px;
            font-size: 0.95rem;
            font-weight: 600;
            border-radius: 12px 12px 0 0;
        }}
        .card-body {{ padding: 20px; }}

        /* Quick Wins */
        .quick-wins-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 12px;
        }}
        .quick-win {{
            background: #fffbeb;
            border: 1px solid #fcd34d;
            border-radius: 10px;
            padding: 16px 12px;
            text-align: center;
        }}
        .quick-win.complete {{
            background: #ecfdf5;
            border-color: #6ee7b7;
        }}
        .qw-count {{ font-size: 1.5rem; font-weight: 700; color: #b45309; line-height: 1; }}
        .quick-win.complete .qw-count {{ color: #047857; }}
        .qw-label {{ font-size: 0.75rem; color: var(--gray-500); margin-top: 6px; }}
        .qw-gain {{ font-size: 0.7rem; color: var(--success); margin-top: 4px; font-weight: 500; }}

        /* Region Section */
        .region-section {{ margin-bottom: 24px; }}
        .region-header {{
            background: var(--gray-50);
            padding: 16px 20px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            border: 1px solid var(--gray-200);
        }}
        .region-title {{ font-weight: 700; font-size: 1.1rem; color: var(--gray-900); }}
        .region-stats {{ display: flex; gap: 16px; font-size: 0.85rem; color: var(--gray-500); }}
        .region-stats strong {{ color: var(--gray-700); }}

        /* Dealer Card */
        .dealer-card {{
            background: white;
            border: 1px solid var(--gray-200);
            border-radius: 10px;
            margin-bottom: 16px;
            overflow: hidden;
        }}
        .dealer-header {{
            background: var(--gray-50);
            padding: 14px 16px;
            border-bottom: 1px solid var(--gray-200);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .dealer-name {{
            font-weight: 600;
            font-size: 0.95rem;
            color: var(--gray-900);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .dealer-metrics {{
            display: flex;
            gap: 16px;
            font-size: 0.8rem;
            color: var(--gray-500);
        }}
        .dealer-metrics .metric {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .dealer-metrics .value {{ font-weight: 600; color: var(--gray-700); }}
        .dealer-metrics .diff {{ font-size: 0.75rem; }}
        .dealer-metrics .diff.positive {{ color: var(--success); }}
        .dealer-metrics .diff.negative {{ color: var(--danger); }}

        /* Tables */
        .listing-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8rem;
        }}
        .listing-table th {{
            background: var(--gray-100);
            padding: 10px 8px;
            text-align: left;
            font-size: 0.65rem;
            font-weight: 600;
            color: var(--gray-500);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 2px solid var(--gray-200);
            white-space: nowrap;
        }}
        .listing-table th.center {{ text-align: center; }}
        .listing-table td {{
            padding: 10px 8px;
            border-bottom: 1px solid var(--gray-100);
            vertical-align: middle;
        }}
        .listing-table td.center {{ text-align: center; }}
        .listing-table td.mono {{ font-family: 'SF Mono', Monaco, monospace; font-size: 0.75rem; }}
        .listing-table tbody tr:hover {{ background: var(--gray-50); }}
        .listing-table tbody tr:last-child td {{ border-bottom: none; }}

        /* Column widths */
        .col-rank {{ width: 50px; }}
        .col-year {{ width: 50px; }}
        .col-model {{ min-width: 140px; }}
        .col-price {{ width: 85px; }}
        .col-tiny {{ width: 40px; }}
        .col-small {{ width: 50px; }}
        .col-actions {{ min-width: 200px; }}

        /* Status indicators */
        .indicator {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 22px;
            height: 22px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 600;
        }}
        .indicator.yes {{ background: #dcfce7; color: #166534; }}
        .indicator.no {{ background: #fee2e2; color: #991b1b; }}
        .indicator.neutral {{ background: var(--gray-100); color: var(--gray-500); }}

        /* Badges */
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.65rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }}
        .badge-a {{ background: #dcfce7; color: #166534; }}
        .badge-b {{ background: #ecfccb; color: #3f6212; }}
        .badge-c {{ background: #fef9c3; color: #854d0e; }}
        .badge-d {{ background: #ffedd5; color: #9a3412; }}
        .badge-f {{ background: #fee2e2; color: #991b1b; }}
        .badge-tier {{ background: var(--gray-100); color: var(--gray-700); }}
        .badge-tier.premium {{ background: #fef3c7; color: #92400e; }}
        .badge-tier.top {{ background: #dbeafe; color: #1e40af; }}

        /* Position badges */
        .pos-badge {{
            display: inline-block;
            padding: 3px 6px;
            border-radius: 4px;
            font-size: 0.6rem;
            font-weight: 600;
            white-space: nowrap;
        }}
        .pos-dominant {{ background: #dbeafe; color: #1e40af; }}
        .pos-strong {{ background: #dcfce7; color: #166534; }}
        .pos-competitive {{ background: #ecfccb; color: #3f6212; }}
        .pos-neutral {{ background: #fef9c3; color: #854d0e; }}
        .pos-atrisk {{ background: #ffedd5; color: #9a3412; }}
        .pos-disadvantaged {{ background: #fee2e2; color: #991b1b; }}

        /* Photo count coloring */
        .photos-good {{ color: var(--success); font-weight: 600; }}
        .photos-ok {{ color: var(--gray-700); }}
        .photos-bad {{ color: var(--danger); font-weight: 600; }}

        /* Action chips */
        .actions-cell {{ display: flex; flex-wrap: wrap; gap: 4px; }}
        .action-chip {{
            background: #eff6ff;
            color: #1d4ed8;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.65rem;
            white-space: nowrap;
            border: 1px solid #bfdbfe;
        }}
        .action-chip .pts {{ color: var(--success); font-weight: 600; margin-left: 3px; }}
        .optimized {{ color: var(--success); font-weight: 500; font-size: 0.75rem; }}

        /* Model link */
        .model-link {{
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
        }}
        .model-link:hover {{ text-decoration: underline; }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 24px;
            color: var(--gray-500);
            font-size: 0.75rem;
        }}

        @media print {{
            body {{ background: white; }}
            .card, .dealer-card {{ box-shadow: none; }}
        }}
        @media (max-width: 768px) {{
            .summary-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .quick-wins-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .dealer-metrics {{ flex-wrap: wrap; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-top">
                <div>
                    <h1>{html.escape(brand)}</h1>
                    <div class="subtitle">{timestamp[:10]}</div>
                    {f'<div class="search-meta">{search_info_str}</div>' if search_info_str else ''}
                </div>
                <div class="grade-badge">
                    <span class="grade-letter">{brand_grade}</span>
                    <span class="grade-label">Quality</span>
                </div>
            </div>
            <div class="summary-grid">
                <div class="summary-stat">
                    <div class="stat-value">{brand_metrics['count']}</div>
                    <div class="stat-label">Total Listings</div>
                    {generate_compare_html(brand_metrics['count'], comp_metrics.get('count', 0), lower_is_better=False)}
                </div>
                <div class="summary-stat">
                    <div class="stat-value">{brand_metrics['avg_rank']}</div>
                    <div class="stat-label">Avg Rank</div>
                    {generate_compare_html(brand_metrics['avg_rank'], comp_metrics.get('avg_rank', 0), lower_is_better=True)}
                </div>
                <div class="summary-stat">
                    <div class="stat-value">{brand_metrics['avg_views']}</div>
                    <div class="stat-label">Avg Views/Unit</div>
                    {generate_compare_html(brand_metrics['avg_views'], comp_metrics.get('avg_views', 0), lower_is_better=False)}
                </div>
                <div class="summary-stat">
                    <div class="stat-value">{brand_metrics['avg_saves']}</div>
                    <div class="stat-label">Avg Saves/Unit</div>
                    {generate_compare_html(brand_metrics['avg_saves'], comp_metrics.get('avg_saves', 0), lower_is_better=False)}
                </div>
                <div class="summary-stat">
                    <div class="stat-value">{brand_metrics['avg_photos']}</div>
                    <div class="stat-label">Avg Photos</div>
                    {generate_compare_html(brand_metrics['avg_photos'], comp_metrics.get('avg_photos', 0), lower_is_better=False)}
                </div>
            </div>
            <div class="summary-grid" style="margin-top: 10px;">
                <div class="summary-stat">
                    <div class="stat-value">{brand_metrics['pct_premium']}%</div>
                    <div class="stat-label">Premium Tier</div>
                    {generate_compare_html(brand_metrics['pct_premium'], comp_metrics.get('pct_premium', 0), lower_is_better=False)}
                </div>
                <div class="summary-stat">
                    <div class="stat-value">{brand_metrics['quality_score']}%</div>
                    <div class="stat-label">Quality Score</div>
                    {generate_compare_html(brand_metrics['quality_score'], comp_metrics.get('quality_score', 0), lower_is_better=False)}
                </div>
                <div class="summary-stat" style="background: rgba(34,197,94,0.2);">
                    <div class="stat-value">{brand_metrics['positions'].get('Dominant', 0) + brand_metrics['positions'].get('Strong', 0)}</div>
                    <div class="stat-label">Strong/Dominant</div>
                </div>
                <div class="summary-stat" style="background: rgba(234,179,8,0.2);">
                    <div class="stat-value">{brand_metrics['positions'].get('Competitive', 0) + brand_metrics['positions'].get('Neutral', 0)}</div>
                    <div class="stat-label">Competitive/Neutral</div>
                </div>
                <div class="summary-stat" style="background: rgba(239,68,68,0.2);">
                    <div class="stat-value">{brand_metrics['positions'].get('At Risk', 0) + brand_metrics['positions'].get('Disadvantaged', 0)}</div>
                    <div class="stat-label">At Risk</div>
                </div>
            </div>
        </div>

        <!-- Quick Wins Summary -->
        <div class="card">
            <div class="card-header">Quick Wins Available</div>
            <div class="card-body">
                <div class="quick-wins-grid">
                    {generate_quick_win_box('Price', brand_metrics['quick_wins']['missing_price'], brand_metrics['count'], RANKING_FACTORS['has_price']['pts'])}
                    {generate_quick_win_box('VIN', brand_metrics['quick_wins']['missing_vin'], brand_metrics['count'], RANKING_FACTORS['has_vin']['pts'])}
                    {generate_quick_win_box('Floorplan', brand_metrics['quick_wins']['missing_floorplan'], brand_metrics['count'], RANKING_FACTORS['has_floorplan']['pts'])}
                    {generate_quick_win_box('Length', brand_metrics['quick_wins']['missing_length'], brand_metrics['count'], RANKING_FACTORS['has_length']['pts'])}
                    {generate_quick_win_box('35+ Photos', brand_metrics['quick_wins']['missing_photos_35'], brand_metrics['count'], RANKING_FACTORS['photos_35']['pts'])}
                </div>
            </div>
        </div>

        <!-- Regional Breakdown -->
        <div class="card">
            <div class="card-header">Regional Performance</div>
            <div class="card-body">
                {''.join(regional_sections)}
            </div>
        </div>

        <div class="footer">
            Generated {timestamp} | Thor Industries Dealer Performance System
        </div>
    </div>
</body>
</html>"""


def generate_compare_html(our_val: float, their_val: float, lower_is_better: bool = False) -> str:
    """Generate comparison indicator."""
    if their_val == 0:
        return ''
    diff = their_val - our_val if lower_is_better else our_val - their_val
    if diff > 0:
        return f'<div class="stat-compare positive">+{abs(diff):.1f} vs comp</div>'
    elif diff < 0:
        return f'<div class="stat-compare negative">{diff:.1f} vs comp</div>'
    return '<div class="stat-compare">= comp</div>'


def generate_quick_win_box(label: str, missing: int, total: int, pts: int) -> str:
    """Generate quick win summary box."""
    complete = missing == 0
    status_class = 'complete' if complete else ''
    gain = (missing * pts) // POINTS_PER_POSITION

    return f"""
    <div class="quick-win {status_class}">
        <div class="qw-count">{missing}</div>
        <div class="qw-label">Missing {label}</div>
        <div class="qw-gain">{f'+{gain} positions' if missing > 0 else 'Complete!'}</div>
    </div>
    """


def generate_region_section(region: str, listings: List[Dict], brand_metrics: Dict) -> str:
    """Generate a regional section with dealers and listings."""
    metrics = calculate_metrics(listings)
    grade, color = calculate_grade(metrics)

    # Group by dealer
    by_dealer = defaultdict(list)
    for l in listings:
        dealer = l.get('dealer_name', 'Unknown')
        by_dealer[dealer].append(l)

    # Generate dealer cards
    dealer_cards = []
    for dealer_name in sorted(by_dealer.keys()):
        dealer_listings = by_dealer[dealer_name]
        d_metrics = calculate_metrics(dealer_listings)
        d_grade, d_color = calculate_grade(d_metrics)

        # Generate listing rows for this dealer
        listing_rows = generate_listing_rows(dealer_listings)

        # Calculate vs brand average comparisons
        rank_diff = d_metrics['avg_rank'] - brand_metrics['avg_rank']
        rank_diff_html = f'<span class="diff {"positive" if rank_diff < 0 else "negative"}">{rank_diff:+.1f}</span>' if rank_diff != 0 else ""

        quality_diff = d_metrics['quality_score'] - brand_metrics['quality_score']
        quality_diff_html = f'<span class="diff {"positive" if quality_diff > 0 else "negative"}">{quality_diff:+.1f}%</span>' if quality_diff != 0 else ""

        # Views comparison (avg per listing)
        views_diff = d_metrics['avg_views'] - brand_metrics['avg_views']
        views_diff_html = f'<span class="diff {"positive" if views_diff > 0 else "negative"}">{views_diff:+.1f}</span>' if views_diff != 0 else ""

        # Saves comparison (avg per listing)
        saves_diff = d_metrics['avg_saves'] - brand_metrics['avg_saves']
        saves_diff_html = f'<span class="diff {"positive" if saves_diff > 0 else "negative"}">{saves_diff:+.1f}</span>' if saves_diff != 0 else ""

        # Photos comparison
        photos_diff = d_metrics['avg_photos'] - brand_metrics['avg_photos']
        photos_diff_html = f'<span class="diff {"positive" if photos_diff > 0 else "negative"}">{photos_diff:+.1f}</span>' if photos_diff != 0 else ""

        # Premium % comparison
        premium_diff = d_metrics['pct_premium'] - brand_metrics['pct_premium']
        premium_diff_html = f'<span class="diff {"positive" if premium_diff > 0 else "negative"}">{premium_diff:+.1f}%</span>' if premium_diff != 0 else ""

        dealer_cards.append(f"""
        <div class="dealer-card">
            <div class="dealer-header">
                <div class="dealer-name">
                    {html.escape(dealer_name)}
                    <span class="badge badge-{d_grade.lower()}">{d_grade}</span>
                </div>
                <div class="dealer-metrics">
                    <div class="metric"><span class="value">{d_metrics['count']}</span> units</div>
                    <div class="metric">Rank: <span class="value">{d_metrics['avg_rank']}</span> {rank_diff_html}</div>
                    <div class="metric">Quality: <span class="value">{d_metrics['quality_score']}%</span> {quality_diff_html}</div>
                    <div class="metric">Views: <span class="value">{d_metrics['avg_views']}</span>/unit {views_diff_html}</div>
                    <div class="metric">Saves: <span class="value">{d_metrics['avg_saves']}</span>/unit {saves_diff_html}</div>
                    <div class="metric">Photos: <span class="value">{d_metrics['avg_photos']}</span> {photos_diff_html}</div>
                    <div class="metric">Premium: <span class="value">{d_metrics['pct_premium']}%</span> {premium_diff_html}</div>
                </div>
            </div>
            <table class="listing-table">
                <thead>
                    <tr>
                        <th class="col-rank">Rank</th>
                        <th class="col-year">Year</th>
                        <th class="col-model">Model</th>
                        <th class="col-price">Price</th>
                        <th class="col-tiny center">VIN</th>
                        <th class="col-small center">Pics</th>
                        <th class="col-tiny center">FP</th>
                        <th class="col-tiny center">Len</th>
                        <th class="col-small center">Views</th>
                        <th class="col-small center">Saves</th>
                        <th class="col-small center">Merch</th>
                        <th class="col-small">Days</th>
                        <th class="col-small">Drop</th>
                        <th class="col-tiny center">Tier</th>
                        <th class="col-small">Position</th>
                        <th class="col-actions">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {listing_rows}
                </tbody>
            </table>
        </div>
        """)

    return f"""
    <div class="region-section">
        <div class="region-header">
            <div class="region-title">{html.escape(region)}</div>
            <div class="region-stats">
                <span><strong>{metrics['count']}</strong> listings</span>
                <span>Avg Rank: <strong>{metrics['avg_rank']}</strong></span>
                <span>Quality: <strong>{metrics['quality_score']}%</strong></span>
                <span class="badge badge-{grade.lower()}">{grade}</span>
            </div>
        </div>
        {''.join(dealer_cards)}
    </div>
    """


def generate_listing_rows(listings: List[Dict]) -> str:
    """Generate table rows for listings with action details."""
    global _engagement_data
    rows = []
    sorted_listings = sorted(listings, key=lambda x: x.get('rank') or 999)

    for l in sorted_listings:
        rank = l.get('rank', '-')
        year = l.get('year', '-')
        model_text = html.escape(str(l.get('model', 'Unknown'))[:20])

        # Make model hyperlinked if URL available
        url = l.get('listing_url', '') or l.get('url', '')
        if url:
            model_html = f'<a href="{html.escape(url)}" target="_blank" class="model-link">{model_text}</a>'
        else:
            model_html = model_text

        price = f"${l.get('price', 0):,.0f}" if l.get('has_price') else '<span style="color:var(--gray-300)">—</span>'

        # VIN indicator
        has_vin = l.get('has_vin')
        vin_html = '<span class="indicator yes">Y</span>' if has_vin else '<span class="indicator no">N</span>'

        # Photos with color coding
        photos = l.get('photo_count', 0)
        if photos >= 35:
            photos_html = f'<span class="photos-good">{photos}</span>'
        elif photos < 20:
            photos_html = f'<span class="photos-bad">{photos}</span>'
        else:
            photos_html = f'<span class="photos-ok">{photos}</span>'

        # Floorplan indicator
        has_floorplan = l.get('has_floorplan')
        fp_html = '<span class="indicator yes">Y</span>' if has_floorplan else '<span class="indicator no">N</span>'

        # Length
        length = l.get('length')
        length_str = f"{length:.0f}" if length else '<span style="color:var(--gray-300)">—</span>'

        # Get engagement data
        listing_id = str(l.get('id', ''))
        eng = _engagement_data.get(listing_id, {})
        views = eng.get('views', 0)
        saves = eng.get('saves', 0)

        # Merch score
        merch = l.get('merch_score')
        merch_str = f"{merch:.0f}" if merch else '—'

        # Days listed
        days = calculate_days_listed(l.get('create_date'))
        days_str = f"{days}d" if days is not None else '—'

        # Price drop date
        price_drop = parse_price_drop_date(l.get('price_drop_date'))
        price_drop_str = price_drop if price_drop else '—'

        # Tier badge
        tier = get_tier(l)
        if tier == 'TP':
            tier_html = '<span class="badge badge-tier top">TP</span>'
        elif tier == 'P':
            tier_html = '<span class="badge badge-tier premium">P</span>'
        else:
            tier_html = '<span class="badge badge-tier">S</span>'

        # Position badge
        position = get_competitive_position(l)
        pos_class = {
            'Dominant': 'pos-dominant',
            'Strong': 'pos-strong',
            'Competitive': 'pos-competitive',
            'Neutral': 'pos-neutral',
            'At Risk': 'pos-atrisk',
            'Disadvantaged': 'pos-disadvantaged',
        }.get(position, 'pos-neutral')
        pos_short = {
            'Dominant': 'Dom',
            'Strong': 'Strong',
            'Competitive': 'Comp',
            'Neutral': 'Neut',
            'At Risk': 'Risk',
            'Disadvantaged': 'Disadv',
        }.get(position, position[:6])
        position_html = f'<span class="pos-badge {pos_class}">{pos_short}</span>'

        # Actions
        actions = calculate_listing_actions(l)
        if actions:
            action_items = []
            # Show year penalty for older standard listings
            if year and year < CURRENT_MODEL_YEAR and position in ('At Risk', 'Disadvantaged'):
                year_penalty = (CURRENT_MODEL_YEAR - year) * 24
                action_items.append(f'<span class="action-chip" style="background:#fee2e2;border-color:#fca5a5;color:#991b1b">-{year_penalty}pts yr</span>')
            for a in actions[:2]:
                short_action = a["action"].replace("Add ", "+").replace("Upload more photos", "+photos").replace("Disclose VIN number", "+VIN").replace("Add listing price", "+price").replace("Add floorplan image", "+FP").replace("Add vehicle length", "+len")[:18]
                action_items.append(f'<span class="action-chip">{short_action}<span class="pts">+{a["positions"]}</span></span>')
            actions_html = f'<div class="actions-cell">{" ".join(action_items)}</div>'
        else:
            actions_html = '<span class="optimized">✓ Complete</span>'

        rows.append(f"""
        <tr>
            <td class="mono">{rank}</td>
            <td>{year}</td>
            <td>{model_html}</td>
            <td class="mono">{price}</td>
            <td class="center">{vin_html}</td>
            <td class="center">{photos_html}</td>
            <td class="center">{fp_html}</td>
            <td class="center">{length_str}</td>
            <td class="center">{views}</td>
            <td class="center">{saves}</td>
            <td class="center">{merch_str}</td>
            <td>{days_str}</td>
            <td>{price_drop_str}</td>
            <td class="center">{tier_html}</td>
            <td>{position_html}</td>
            <td>{actions_html}</td>
        </tr>
        """)

    return ''.join(rows)


# =============================================================================
# MAIN
# =============================================================================

def generate_reports(csv_path: str, output_dir: str = None,
                     brand_filter: str = None, region_filter: str = None) -> List[str]:
    """Generate all manufacturer reports."""
    global _engagement_data

    print(f"\nLoading data from: {csv_path}")
    listings, search_metadata = load_csv(csv_path)
    print(f"Total listings: {len(listings)}")
    if search_metadata.get('type'):
        print(f"Search: {search_metadata.get('type')} | Zip: {search_metadata.get('zip')} | Radius: {search_metadata.get('radius')}mi")

    # Load engagement data
    csv_dir = Path(csv_path).parent
    _engagement_data = load_engagement_data(csv_dir)

    thor_listings = [l for l in listings if l.get('thor_brand')]
    print(f"Thor listings: {len(thor_listings)}")

    if not thor_listings:
        print("No Thor brand listings found!")
        return []

    # Group by brand, then by region
    by_brand = defaultdict(lambda: defaultdict(list))
    for l in thor_listings:
        brand = l.get('thor_brand', 'Unknown')
        region = l.get('region', 'Unknown')

        if brand_filter and brand.lower() != brand_filter.lower():
            continue
        if region_filter and region.lower() != region_filter.lower():
            continue

        by_brand[brand][region].append(l)

    # Setup output directory
    if output_dir is None:
        output_dir = Path(__file__).parent.parent.parent / 'output' / 'reports'
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Generate per-manufacturer reports
    for brand in sorted(by_brand.keys()):
        regions = by_brand[brand]
        if not regions:
            continue

        print(f"\nGenerating report for: {brand}")
        print(f"  Regions: {', '.join(sorted(regions.keys()))}")
        print(f"  Total listings: {sum(len(r) for r in regions.values())}")

        html = generate_manufacturer_report(brand, dict(regions), listings, search_metadata)

        safe_brand = brand.replace(' ', '_').replace('/', '_')[:30]
        file_path = output_dir / f"{safe_brand}_regional_{timestamp}.html"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)

        generated.append(str(file_path))
        print(f"  Created: {file_path.name}")

    return generated


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate manufacturer regional reports')
    parser.add_argument('--input', '-i', help='Input ranked_listings CSV')
    parser.add_argument('--output', '-o', help='Output directory')
    parser.add_argument('--brand', '-b', help='Filter to specific brand')
    parser.add_argument('--region', '-r', help='Filter to specific region')
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

    generated = generate_reports(
        str(csv_path),
        output_dir=args.output,
        brand_filter=args.brand,
        region_filter=args.region,
    )

    print(f"\nDone! Generated {len(generated)} reports.")
    if generated:
        print(f"Open in browser: file://{generated[0]}")


if __name__ == '__main__':
    main()
