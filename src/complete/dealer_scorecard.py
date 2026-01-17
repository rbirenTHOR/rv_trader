"""
Dealer Scorecard Generator - Visual HTML Reports for Thor Dealers

Generates beautiful, shareable HTML scorecards that dealers can easily understand.
Each dealer gets a one-page scorecard showing:
- Overall listing quality grade (A-F)
- Visual metrics with icons
- Comparison to market average
- Top 3-5 actionable improvements with estimated rank gains
- Per-listing breakdown with status indicators

Usage:
    python dealer_scorecard.py                    # Uses latest ranked_listings CSV
    python dealer_scorecard.py -i input.csv      # Specific input file
    python dealer_scorecard.py --brand Jayco     # Filter to specific Thor brand
    python dealer_scorecard.py --dealer "Thor Motor Coach of Chicago"  # Single dealer
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, List, Any
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

# Point values from ranking algorithm
IMPROVEMENT_FACTORS = {
    'price': {'relevance': 194, 'merch': 5, 'label': 'Add listing price'},
    'vin': {'relevance': 165, 'merch': 6, 'label': 'Add VIN number'},
    'photos_35': {'relevance': 195, 'merch': 30, 'label': 'Add photos to reach 35'},
    'floorplan': {'relevance': 50, 'merch': 12, 'label': 'Add floorplan image'},
    'length': {'relevance': 0, 'merch': 8, 'label': 'Add vehicle length'},
}

RELEVANCE_PER_RANK = 15.0


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
            'action': f"{f['label']} ({needed} more needed)",
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


def calculate_dealer_grade(dealer_listings: List[Dict], market_avg_rank: float) -> Dict:
    """Calculate dealer grade and metrics."""
    if not dealer_listings:
        return {'grade': 'N/A', 'score': 0}

    # Calculate metrics
    total = len(dealer_listings)
    ranks = [l['rank'] for l in dealer_listings if l.get('rank')]
    avg_rank = sum(ranks) / len(ranks) if ranks else 999

    # Quality metrics
    with_price = sum(1 for l in dealer_listings if l.get('has_price'))
    with_vin = sum(1 for l in dealer_listings if l.get('has_vin'))
    with_floorplan = sum(1 for l in dealer_listings if l.get('has_floorplan'))
    avg_photos = sum(l.get('photo_count', 0) for l in dealer_listings) / total if total > 0 else 0
    photos_35_plus = sum(1 for l in dealer_listings if l.get('photo_count', 0) >= 35)

    # Calculate score (0-100)
    price_score = (with_price / total * 25) if total > 0 else 0
    vin_score = (with_vin / total * 25) if total > 0 else 0
    floorplan_score = (with_floorplan / total * 15) if total > 0 else 0
    photo_score = min(avg_photos / 35 * 25, 25)
    rank_score = max(0, 10 - (avg_rank - market_avg_rank) / 5) if market_avg_rank > 0 else 5

    total_score = price_score + vin_score + floorplan_score + photo_score + rank_score

    # Grade thresholds
    if total_score >= 90:
        grade = 'A'
        grade_color = '#22c55e'  # green
    elif total_score >= 80:
        grade = 'B'
        grade_color = '#84cc16'  # lime
    elif total_score >= 70:
        grade = 'C'
        grade_color = '#eab308'  # yellow
    elif total_score >= 60:
        grade = 'D'
        grade_color = '#f97316'  # orange
    else:
        grade = 'F'
        grade_color = '#ef4444'  # red

    return {
        'grade': grade,
        'grade_color': grade_color,
        'score': round(total_score, 1),
        'avg_rank': round(avg_rank, 1),
        'rank_vs_market': round(avg_rank - market_avg_rank, 1),
        'total_listings': total,
        'with_price': with_price,
        'with_price_pct': round(with_price / total * 100, 1) if total > 0 else 0,
        'with_vin': with_vin,
        'with_vin_pct': round(with_vin / total * 100, 1) if total > 0 else 0,
        'with_floorplan': with_floorplan,
        'with_floorplan_pct': round(with_floorplan / total * 100, 1) if total > 0 else 0,
        'avg_photos': round(avg_photos, 1),
        'photos_35_plus': photos_35_plus,
        'photos_35_pct': round(photos_35_plus / total * 100, 1) if total > 0 else 0,
    }


def calculate_total_improvement(dealer_listings: List[Dict], tier_ceiling: int) -> Dict:
    """Calculate total improvement potential for dealer."""
    total_actions = 0
    total_rank_gain = 0
    top_opportunities = []

    for listing in dealer_listings:
        if listing.get('is_premium'):
            continue  # Skip premium listings

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

    # Sort by realistic gain
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
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #1f2937;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
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
            padding: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header-left h1 {{
            font-size: 1.8rem;
            margin-bottom: 8px;
        }}
        .header-left .brand-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
        }}
        .header-left .location {{
            margin-top: 8px;
            opacity: 0.9;
            font-size: 0.95rem;
        }}
        .grade-circle {{
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: {grade_color};
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }}
        .grade-letter {{
            font-size: 3rem;
            font-weight: bold;
            line-height: 1;
        }}
        .grade-label {{
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1px;
            background: #e5e7eb;
            padding: 1px;
        }}
        .metric {{
            background: white;
            padding: 20px;
            text-align: center;
        }}
        .metric-value {{
            font-size: 2rem;
            font-weight: bold;
            color: #1e3a5f;
        }}
        .metric-value.good {{
            color: #22c55e;
        }}
        .metric-value.warning {{
            color: #f97316;
        }}
        .metric-value.bad {{
            color: #ef4444;
        }}
        .metric-label {{
            font-size: 0.85rem;
            color: #6b7280;
            margin-top: 4px;
        }}
        .metric-icon {{
            font-size: 1.5rem;
            margin-bottom: 8px;
        }}
        .section {{
            padding: 25px;
            border-bottom: 1px solid #e5e7eb;
        }}
        .section:last-child {{
            border-bottom: none;
        }}
        .section-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: #1e3a5f;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .quick-wins {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }}
        .quick-win {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .quick-win.complete {{
            background: #f0fdf4;
            border-color: #86efac;
        }}
        .quick-win.incomplete {{
            background: #fef3c7;
            border-color: #fcd34d;
        }}
        .quick-win-icon {{
            font-size: 1.5rem;
        }}
        .quick-win-text {{
            flex: 1;
        }}
        .quick-win-label {{
            font-weight: 500;
            color: #374151;
        }}
        .quick-win-stat {{
            font-size: 0.85rem;
            color: #6b7280;
        }}
        .opportunity {{
            background: #f8fafc;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 12px;
        }}
        .opportunity:last-child {{
            margin-bottom: 0;
        }}
        .opp-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
        }}
        .opp-title {{
            font-weight: 600;
            color: #1f2937;
        }}
        .opp-rank {{
            background: #1e3a5f;
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85rem;
        }}
        .opp-gain {{
            background: #22c55e;
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85rem;
            margin-left: 8px;
        }}
        .opp-actions {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .action-chip {{
            background: #e0e7ff;
            color: #4338ca;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.8rem;
        }}
        .listing-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .listing-table th {{
            background: #f1f5f9;
            padding: 12px 8px;
            text-align: left;
            font-size: 0.8rem;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
        }}
        .listing-table td {{
            padding: 12px 8px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 0.9rem;
        }}
        .status-badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
        }}
        .status-premium {{
            background: #fef3c7;
            color: #92400e;
        }}
        .status-good {{
            background: #dcfce7;
            color: #166534;
        }}
        .status-needs-work {{
            background: #fee2e2;
            color: #991b1b;
        }}
        .check {{
            color: #22c55e;
        }}
        .cross {{
            color: #ef4444;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #9ca3af;
            font-size: 0.85rem;
        }}
        .summary-box {{
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
        }}
        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            text-align: center;
        }}
        .summary-stat-value {{
            font-size: 1.8rem;
            font-weight: bold;
        }}
        .summary-stat-label {{
            font-size: 0.85rem;
            opacity: 0.9;
        }}
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .card {{
                box-shadow: none;
                border: 1px solid #e5e7eb;
            }}
        }}
        @media (max-width: 768px) {{
            .header {{
                flex-direction: column;
                text-align: center;
                gap: 20px;
            }}
            .metrics-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            .quick-wins {{
                grid-template-columns: 1fr;
            }}
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
                    <div class="location">{location} | {phone}</div>
                </div>
                <div class="grade-circle">
                    <span class="grade-letter">{grade}</span>
                    <span class="grade-label">Score: {score}</span>
                </div>
            </div>

            <div class="metrics-grid">
                <div class="metric">
                    <div class="metric-icon">📊</div>
                    <div class="metric-value {rank_class}">{avg_rank}</div>
                    <div class="metric-label">Avg Rank ({rank_vs_market})</div>
                </div>
                <div class="metric">
                    <div class="metric-icon">📝</div>
                    <div class="metric-value">{total_listings}</div>
                    <div class="metric-label">Total Listings</div>
                </div>
                <div class="metric">
                    <div class="metric-icon">📸</div>
                    <div class="metric-value {photo_class}">{avg_photos}</div>
                    <div class="metric-label">Avg Photos</div>
                </div>
                <div class="metric">
                    <div class="metric-icon">🎯</div>
                    <div class="metric-value good">+{total_rank_gain}</div>
                    <div class="metric-label">Positions to Gain</div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">📋 Quick Quality Check</div>
                <div class="quick-wins">
                    <div class="quick-win {price_status}">
                        <div class="quick-win-icon">{price_icon}</div>
                        <div class="quick-win-text">
                            <div class="quick-win-label">Listing Prices</div>
                            <div class="quick-win-stat">{with_price}/{total_listings} listings ({with_price_pct}%)</div>
                        </div>
                    </div>
                    <div class="quick-win {vin_status}">
                        <div class="quick-win-icon">{vin_icon}</div>
                        <div class="quick-win-text">
                            <div class="quick-win-label">VIN Numbers</div>
                            <div class="quick-win-stat">{with_vin}/{total_listings} listings ({with_vin_pct}%)</div>
                        </div>
                    </div>
                    <div class="quick-win {floorplan_status}">
                        <div class="quick-win-icon">{floorplan_icon}</div>
                        <div class="quick-win-text">
                            <div class="quick-win-label">Floorplan Images</div>
                            <div class="quick-win-stat">{with_floorplan}/{total_listings} listings ({with_floorplan_pct}%)</div>
                        </div>
                    </div>
                    <div class="quick-win {photos_status}">
                        <div class="quick-win-icon">{photos_icon}</div>
                        <div class="quick-win-text">
                            <div class="quick-win-label">35+ Photos</div>
                            <div class="quick-win-stat">{photos_35_plus}/{total_listings} listings ({photos_35_pct}%)</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">🚀 Top Improvement Opportunities</div>
                <div class="summary-box">
                    <div class="summary-stats">
                        <div>
                            <div class="summary-stat-value">{total_actions}</div>
                            <div class="summary-stat-label">Actions Needed</div>
                        </div>
                        <div>
                            <div class="summary-stat-value">+{total_rank_gain}</div>
                            <div class="summary-stat-label">Rank Positions</div>
                        </div>
                        <div>
                            <div class="summary-stat-value">{opportunities_count}</div>
                            <div class="summary-stat-label">Listings to Fix</div>
                        </div>
                    </div>
                </div>
                {opportunities_html}
            </div>

            <div class="section">
                <div class="section-title">📋 All Listings</div>
                <table class="listing-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Year</th>
                            <th>Model</th>
                            <th>Price</th>
                            <th>Photos</th>
                            <th>VIN</th>
                            <th>Floorplan</th>
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


def generate_opportunity_html(opp: Dict) -> str:
    """Generate HTML for a single opportunity."""
    listing = opp['listing']
    actions = opp['actions']

    year = listing.get('year', 'N/A')
    model = listing.get('model', 'Unknown')[:30]
    rank = listing.get('rank', 'N/A')
    gain = opp['realistic_gain']

    actions_html = ''.join(
        f'<span class="action-chip">{html.escape(a["action"][:40])}</span>'
        for a in actions[:3]
    )

    gain_html = f'<span class="opp-gain">+{gain} positions</span>' if gain > 0 else ''

    return f"""
    <div class="opportunity">
        <div class="opp-header">
            <div class="opp-title">{year} {html.escape(model)}</div>
            <div>
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
    model = html.escape(str(listing.get('model', 'Unknown'))[:25])
    price = f"${listing.get('price', 0):,.0f}" if listing.get('has_price') else '<span class="cross">Missing</span>'
    photos = listing.get('photo_count', 0)

    vin_icon = '<span class="check">&#10004;</span>' if listing.get('has_vin') else '<span class="cross">&#10008;</span>'
    fp_icon = '<span class="check">&#10004;</span>' if listing.get('has_floorplan') else '<span class="cross">&#10008;</span>'

    # Determine status
    actions = calculate_listing_actions(listing)
    if listing.get('is_premium'):
        status = '<span class="status-badge status-premium">Premium</span>'
    elif len(actions) == 0:
        status = '<span class="status-badge status-good">Complete</span>'
    else:
        status = '<span class="status-badge status-needs-work">Needs Work</span>'

    photo_class = 'good' if photos >= 35 else 'warning' if photos >= 20 else 'bad'

    return f"""
    <tr>
        <td>{rank}</td>
        <td>{year}</td>
        <td>{model}</td>
        <td>{price}</td>
        <td><span class="{photo_class}">{photos}</span></td>
        <td>{vin_icon}</td>
        <td>{fp_icon}</td>
        <td>{status}</td>
    </tr>
    """


def generate_dealer_scorecard(dealer_name: str, dealer_listings: List[Dict],
                               market_avg_rank: float, tier_ceiling: int,
                               thor_brand: str) -> str:
    """Generate complete HTML scorecard for a dealer."""

    # Calculate metrics
    metrics = calculate_dealer_grade(dealer_listings, market_avg_rank)
    improvement = calculate_total_improvement(dealer_listings, tier_ceiling)

    # Get location and phone from first listing
    first = dealer_listings[0] if dealer_listings else {}
    location = f"{first.get('city', 'Unknown')}, {first.get('state', 'XX')}"
    phone = first.get('dealer_phone', 'N/A')

    # Generate opportunities HTML
    opportunities_html = ''.join(
        generate_opportunity_html(opp) for opp in improvement['top_opportunities']
    )
    if not opportunities_html:
        opportunities_html = '<p style="color: #6b7280; text-align: center;">All listings are fully optimized!</p>'

    # Generate listings HTML
    sorted_listings = sorted(dealer_listings, key=lambda x: x.get('rank') or 999)
    listings_html = ''.join(generate_listing_row_html(l) for l in sorted_listings)

    # Determine status classes
    def get_status(pct):
        return 'complete' if pct >= 90 else 'incomplete'

    def get_icon(pct):
        return '&#10004;' if pct >= 90 else '&#9888;'

    # Rank comparison
    rank_diff = metrics['rank_vs_market']
    rank_vs_market = f"{rank_diff:+.1f} vs avg" if rank_diff != 0 else "at avg"
    rank_class = 'good' if rank_diff < 0 else 'warning' if rank_diff < 5 else 'bad'

    photo_class = 'good' if metrics['avg_photos'] >= 35 else 'warning' if metrics['avg_photos'] >= 20 else 'bad'

    return HTML_TEMPLATE.format(
        dealer_name=html.escape(dealer_name),
        thor_brand=html.escape(thor_brand),
        location=html.escape(location),
        phone=html.escape(phone),
        grade=metrics['grade'],
        grade_color=metrics['grade_color'],
        score=metrics['score'],
        avg_rank=metrics['avg_rank'],
        rank_vs_market=rank_vs_market,
        rank_class=rank_class,
        total_listings=metrics['total_listings'],
        avg_photos=metrics['avg_photos'],
        photo_class=photo_class,
        total_rank_gain=improvement['total_rank_gain'],
        total_actions=improvement['total_actions'],
        opportunities_count=len(improvement['top_opportunities']),
        with_price=metrics['with_price'],
        with_price_pct=metrics['with_price_pct'],
        price_status=get_status(metrics['with_price_pct']),
        price_icon=get_icon(metrics['with_price_pct']),
        with_vin=metrics['with_vin'],
        with_vin_pct=metrics['with_vin_pct'],
        vin_status=get_status(metrics['with_vin_pct']),
        vin_icon=get_icon(metrics['with_vin_pct']),
        with_floorplan=metrics['with_floorplan'],
        with_floorplan_pct=metrics['with_floorplan_pct'],
        floorplan_status=get_status(metrics['with_floorplan_pct']),
        floorplan_icon=get_icon(metrics['with_floorplan_pct']),
        photos_35_plus=metrics['photos_35_plus'],
        photos_35_pct=metrics['photos_35_pct'],
        photos_status=get_status(metrics['photos_35_pct']),
        photos_icon=get_icon(metrics['photos_35_pct']),
        opportunities_html=opportunities_html,
        listings_html=listings_html,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M'),
    )


# =============================================================================
# MAIN
# =============================================================================

def generate_scorecards(csv_path: str, output_dir: str = None,
                        brand_filter: str = None, dealer_filter: str = None) -> List[str]:
    """
    Generate dealer scorecards from ranked listings CSV.

    Returns list of generated file paths.
    """
    print(f"\nLoading data from: {csv_path}")
    listings = load_csv(csv_path)
    print(f"Total listings loaded: {len(listings)}")

    # Identify Thor brands
    for listing in listings:
        listing['thor_brand'] = identify_thor_brand(listing.get('make', ''))

    thor_listings = [l for l in listings if l.get('thor_brand')]
    print(f"Thor brand listings: {len(thor_listings)}")

    # Apply filters
    if brand_filter:
        thor_listings = [l for l in thor_listings if l['thor_brand'].lower() == brand_filter.lower()]
        print(f"After brand filter '{brand_filter}': {len(thor_listings)}")

    if dealer_filter:
        thor_listings = [l for l in thor_listings if dealer_filter.lower() in l.get('dealer_name', '').lower()]
        print(f"After dealer filter '{dealer_filter}': {len(thor_listings)}")

    if not thor_listings:
        print("No listings found matching filters!")
        return []

    # Calculate market averages
    all_ranks = [l['rank'] for l in listings if l.get('rank')]
    market_avg_rank = sum(all_ranks) / len(all_ranks) if all_ranks else 50
    tier_ceilings = calculate_tier_ceilings(listings)
    tier_ceiling = tier_ceilings.get('standard', 1)

    print(f"Market avg rank: {market_avg_rank:.1f}, Tier ceiling: {tier_ceiling}")

    # Group by dealer
    by_dealer = defaultdict(list)
    for listing in thor_listings:
        dealer = listing.get('dealer_name') or 'Unknown Dealer'
        by_dealer[dealer].append(listing)

    print(f"Generating scorecards for {len(by_dealer)} dealers...")

    # Output directory
    if output_dir is None:
        output_dir = Path(__file__).parent.parent.parent / 'output' / 'scorecards'
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate scorecards
    generated = []
    for dealer_name, dealer_listings in sorted(by_dealer.items()):
        # Get primary Thor brand for this dealer
        brand_counts = defaultdict(int)
        for l in dealer_listings:
            brand_counts[l.get('thor_brand', 'Unknown')] += 1
        primary_brand = max(brand_counts.items(), key=lambda x: x[1])[0]

        html = generate_dealer_scorecard(
            dealer_name=dealer_name,
            dealer_listings=dealer_listings,
            market_avg_rank=market_avg_rank,
            tier_ceiling=tier_ceiling,
            thor_brand=primary_brand,
        )

        # Save file
        safe_name = dealer_name.replace(' ', '_').replace('/', '_').replace('\\', '_')[:50]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = output_dir / f"scorecard_{safe_name}_{timestamp}.html"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)

        generated.append(str(file_path))
        print(f"  Created: {file_path.name}")

    # Generate index page
    index_html = generate_index_page(by_dealer, listings, output_dir)
    index_path = output_dir / f"index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_html)
    generated.append(str(index_path))
    print(f"  Created: {index_path.name} (index)")

    return generated


def generate_index_page(by_dealer: Dict, all_listings: List[Dict], output_dir: Path) -> str:
    """Generate an index page linking all dealer scorecards."""

    # Calculate market stats
    all_ranks = [l['rank'] for l in all_listings if l.get('rank')]
    market_avg = sum(all_ranks) / len(all_ranks) if all_ranks else 50

    rows = []
    for dealer_name, listings in sorted(by_dealer.items()):
        metrics = calculate_dealer_grade(listings, market_avg)

        brand_counts = defaultdict(int)
        for l in listings:
            brand_counts[l.get('thor_brand', 'Unknown')] += 1
        primary_brand = max(brand_counts.items(), key=lambda x: x[1])[0]

        safe_name = dealer_name.replace(' ', '_').replace('/', '_').replace('\\', '_')[:50]

        rows.append(f"""
        <tr>
            <td><a href="scorecard_{safe_name}_*.html" style="color: #2563eb; text-decoration: none;">{html.escape(dealer_name)}</a></td>
            <td>{html.escape(primary_brand)}</td>
            <td>{metrics['total_listings']}</td>
            <td><span style="font-weight: bold; color: {metrics['grade_color']};">{metrics['grade']}</span></td>
            <td>{metrics['avg_rank']}</td>
            <td>{metrics['with_price_pct']}%</td>
            <td>{metrics['avg_photos']}</td>
        </tr>
        """)

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Dealer Scorecards Index</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; background: #f5f5f5; }}
            .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #1e3a5f; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ background: #1e3a5f; color: white; padding: 12px; text-align: left; }}
            td {{ padding: 12px; border-bottom: 1px solid #e5e7eb; }}
            tr:hover {{ background: #f9fafb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Thor Dealer Scorecards</h1>
            <p style="color: #6b7280; margin-bottom: 20px;">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | {len(by_dealer)} dealers | Market avg rank: {market_avg:.1f}</p>
            <table>
                <thead>
                    <tr>
                        <th>Dealer</th>
                        <th>Brand</th>
                        <th>Listings</th>
                        <th>Grade</th>
                        <th>Avg Rank</th>
                        <th>Has Price</th>
                        <th>Avg Photos</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate visual HTML dealer scorecards'
    )
    parser.add_argument('--input', '-i', help='Input ranked_listings CSV (default: latest)')
    parser.add_argument('--output', '-o', help='Output directory for scorecards')
    parser.add_argument('--brand', '-b', help='Filter to specific Thor brand')
    parser.add_argument('--dealer', '-d', help='Filter to specific dealer (partial match)')
    args = parser.parse_args()

    # Find input file
    if args.input:
        csv_path = Path(args.input)
    else:
        output_dir = Path(__file__).parent.parent.parent / 'output'
        csv_files = sorted(output_dir.glob('ranked_listings*.csv'), reverse=True)
        if not csv_files:
            print("Error: No ranked_listings CSV files found in output/")
            return
        csv_path = csv_files[0]

    # Generate scorecards
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
