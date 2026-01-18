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
# DATA LOADING
# =============================================================================

def load_csv(csv_path: str) -> List[Dict]:
    """Load and parse CSV file."""
    listings = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
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
    return listings


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
                                  all_listings: List[Dict]) -> str:
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

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand} - Regional Performance Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #1f2937;
            line-height: 1.5;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

        /* Header */
        .header {{
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 20px;
        }}
        .header-top {{ display: flex; justify-content: space-between; align-items: center; }}
        .header h1 {{ font-size: 2rem; margin-bottom: 5px; }}
        .header .subtitle {{ opacity: 0.9; }}
        .grade-badge {{
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: {brand_color};
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-weight: bold;
        }}
        .grade-letter {{ font-size: 2rem; }}
        .grade-label {{ font-size: 0.7rem; }}

        /* Summary Stats */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 15px;
            margin-top: 20px;
        }}
        .summary-stat {{
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{ font-size: 1.8rem; font-weight: bold; }}
        .stat-label {{ font-size: 0.8rem; opacity: 0.9; }}
        .stat-compare {{ font-size: 0.75rem; margin-top: 5px; }}
        .stat-compare.positive {{ color: #86efac; }}
        .stat-compare.negative {{ color: #fca5a5; }}

        /* Cards */
        .card {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            overflow: hidden;
        }}
        .card-header {{
            background: #1e3a5f;
            color: white;
            padding: 15px 20px;
            font-size: 1.1rem;
            font-weight: 600;
        }}
        .card-body {{ padding: 20px; }}

        /* Quick Wins */
        .quick-wins-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 10px;
        }}
        .quick-win {{
            background: #fef3c7;
            border: 1px solid #fcd34d;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        .quick-win.complete {{
            background: #dcfce7;
            border-color: #86efac;
        }}
        .qw-count {{ font-size: 1.5rem; font-weight: bold; color: #92400e; }}
        .quick-win.complete .qw-count {{ color: #166534; }}
        .qw-label {{ font-size: 0.8rem; color: #78716c; margin-top: 5px; }}
        .qw-gain {{ font-size: 0.7rem; color: #059669; margin-top: 5px; }}

        /* Regional Section */
        .region-section {{
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            margin-bottom: 15px;
        }}
        .region-header {{
            background: #f8fafc;
            padding: 15px 20px;
            border-bottom: 1px solid #e5e7eb;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
        }}
        .region-title {{ font-weight: 600; font-size: 1.1rem; }}
        .region-stats {{ display: flex; gap: 20px; font-size: 0.9rem; color: #6b7280; }}
        .region-body {{ padding: 15px 20px; }}

        /* Tables */
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
        th {{
            background: #f1f5f9;
            padding: 10px 8px;
            text-align: left;
            font-size: 0.7rem;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
        }}
        td {{ padding: 10px 8px; border-bottom: 1px solid #e5e7eb; }}
        tr:hover {{ background: #f9fafb; }}

        /* Status badges */
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 500;
        }}
        .badge-a {{ background: #dcfce7; color: #166534; }}
        .badge-b {{ background: #ecfccb; color: #3f6212; }}
        .badge-c {{ background: #fef9c3; color: #854d0e; }}
        .badge-d {{ background: #ffedd5; color: #9a3412; }}
        .badge-f {{ background: #fee2e2; color: #991b1b; }}
        .badge-premium {{ background: #fef3c7; color: #92400e; }}

        .check {{ color: #22c55e; }}
        .cross {{ color: #ef4444; }}

        /* Listing detail */
        .listing-detail {{
            background: #f8fafc;
            border-radius: 8px;
            padding: 15px;
            margin-top: 10px;
        }}
        .listing-actions {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }}
        .action-chip {{
            background: #dbeafe;
            color: #1e40af;
            padding: 4px 10px;
            border-radius: 15px;
            font-size: 0.75rem;
        }}
        .action-chip .gain {{ color: #059669; font-weight: 600; }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 20px;
            color: #9ca3af;
            font-size: 0.8rem;
        }}

        @media print {{
            body {{ background: white; }}
            .card {{ box-shadow: none; border: 1px solid #e5e7eb; }}
            .region-section {{ page-break-inside: avoid; }}
        }}
        @media (max-width: 768px) {{
            .summary-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .quick-wins-grid {{ grid-template-columns: repeat(2, 1fr); }}
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
                    <div class="subtitle">Regional Performance Report - Week of {timestamp[:10]}</div>
                </div>
                <div class="grade-badge">
                    <span class="grade-letter">{brand_grade}</span>
                    <span class="grade-label">Overall</span>
                </div>
            </div>
            <div class="summary-grid">
                <div class="summary-stat">
                    <div class="stat-value">{brand_metrics['count']}</div>
                    <div class="stat-label">Total Listings</div>
                </div>
                <div class="summary-stat">
                    <div class="stat-value">{brand_metrics['avg_rank']}</div>
                    <div class="stat-label">Avg Rank</div>
                    {generate_compare_html(brand_metrics['avg_rank'], comp_metrics.get('avg_rank', 0), lower_is_better=True)}
                </div>
                <div class="summary-stat">
                    <div class="stat-value">{brand_metrics['pct_premium']}%</div>
                    <div class="stat-label">Premium</div>
                </div>
                <div class="summary-stat">
                    <div class="stat-value">{brand_metrics['quality_score']}%</div>
                    <div class="stat-label">Quality Score</div>
                </div>
                <div class="summary-stat">
                    <div class="stat-value">+{brand_metrics['total_rank_gain']}</div>
                    <div class="stat-label">Positions Available</div>
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

    # Generate dealer tables
    dealer_rows = []
    for dealer_name in sorted(by_dealer.keys()):
        dealer_listings = by_dealer[dealer_name]
        d_metrics = calculate_metrics(dealer_listings)
        d_grade, d_color = calculate_grade(d_metrics)

        # Generate listing rows for this dealer
        listing_rows = generate_listing_rows(dealer_listings)

        dealer_rows.append(f"""
        <tr class="dealer-row">
            <td colspan="11" style="background: #f1f5f9; font-weight: 600; padding: 12px 8px;">
                {html.escape(dealer_name)}
                <span class="badge badge-{d_grade.lower()}" style="margin-left: 10px;">{d_grade}</span>
                <span style="float: right; font-weight: normal; color: #6b7280;">
                    {d_metrics['count']} listings | Avg Rank: {d_metrics['avg_rank']} | Quality: {d_metrics['quality_score']}%
                </span>
            </td>
        </tr>
        {listing_rows}
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
        <div class="region-body">
            <table>
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>Stock #</th>
                        <th>Year</th>
                        <th>Model</th>
                        <th>Price</th>
                        <th>Photos</th>
                        <th>VIN</th>
                        <th>FP</th>
                        <th>Len</th>
                        <th>Status</th>
                        <th>Actions Needed</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(dealer_rows)}
                </tbody>
            </table>
        </div>
    </div>
    """


def generate_listing_rows(listings: List[Dict]) -> str:
    """Generate table rows for listings with action details."""
    rows = []
    sorted_listings = sorted(listings, key=lambda x: x.get('rank') or 999)

    for l in sorted_listings:
        rank = l.get('rank', '-')
        stock_num = html.escape(str(l.get('stock_number', '-'))[:15]) if l.get('stock_number') else '-'
        year = l.get('year', '-')
        model = html.escape(str(l.get('model', 'Unknown'))[:25])
        price = f"${l.get('price', 0):,.0f}" if l.get('has_price') else '<span class="cross">Missing</span>'
        photos = l.get('photo_count', 0)
        photo_class = 'check' if photos >= 35 else 'cross' if photos < 20 else ''

        vin = '<span class="check">Y</span>' if l.get('has_vin') else '<span class="cross">N</span>'
        fp = '<span class="check">Y</span>' if l.get('has_floorplan') else '<span class="cross">N</span>'
        length = '<span class="check">Y</span>' if l.get('has_length') else '<span class="cross">N</span>'

        # Status
        actions = calculate_listing_actions(l)
        if l.get('is_premium'):
            status = '<span class="badge badge-premium">Premium</span>'
        elif len(actions) == 0:
            status = '<span class="badge badge-a">Complete</span>'
        else:
            status = f'<span class="badge badge-d">{len(actions)} fixes</span>'

        # Actions
        if actions:
            actions_html = ' '.join(
                f'<span class="action-chip">{a["action"][:30]} <span class="gain">+{a["positions"]}</span></span>'
                for a in actions[:3]
            )
        else:
            actions_html = '<span style="color: #22c55e;">Fully optimized</span>'

        rows.append(f"""
        <tr>
            <td>{rank}</td>
            <td><code>{stock_num}</code></td>
            <td>{year}</td>
            <td>{model}</td>
            <td>{price}</td>
            <td><span class="{photo_class}">{photos}</span></td>
            <td>{vin}</td>
            <td>{fp}</td>
            <td>{length}</td>
            <td>{status}</td>
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

    print(f"\nLoading data from: {csv_path}")
    listings = load_csv(csv_path)
    print(f"Total listings: {len(listings)}")

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

        html = generate_manufacturer_report(brand, dict(regions), listings)

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
