"""
Weekly Tracking System - Item-level history and week-over-week comparison

Stores historical data for each listing and tracks changes over time:
- Rank changes (improved/declined/unchanged)
- Quality score changes
- Actions completed
- New listings / Sold listings

Usage:
    python weekly_tracker.py                     # Process latest data, update history
    python weekly_tracker.py --report            # Generate WoW change report
    python weekly_tracker.py --brand Jayco       # Filter to specific brand
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
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

STATE_TO_REGION = {
    'IL': 'Midwest', 'IN': 'Midwest', 'IA': 'Midwest', 'KS': 'Midwest',
    'MI': 'Midwest', 'MN': 'Midwest', 'MO': 'Midwest', 'NE': 'Midwest',
    'ND': 'Midwest', 'OH': 'Midwest', 'SD': 'Midwest', 'WI': 'Midwest',
    'CT': 'Northeast', 'DE': 'Northeast', 'ME': 'Northeast', 'MD': 'Northeast',
    'MA': 'Northeast', 'NH': 'Northeast', 'NJ': 'Northeast', 'NY': 'Northeast',
    'PA': 'Northeast', 'RI': 'Northeast', 'VT': 'Northeast',
    'AL': 'Southeast', 'AR': 'Southeast', 'FL': 'Southeast', 'GA': 'Southeast',
    'KY': 'Southeast', 'LA': 'Southeast', 'MS': 'Southeast', 'NC': 'Southeast',
    'SC': 'Southeast', 'TN': 'Southeast', 'VA': 'Southeast', 'WV': 'Southeast',
    'AZ': 'Southwest', 'NM': 'Southwest', 'OK': 'Southwest', 'TX': 'Southwest',
    'AK': 'West', 'CA': 'West', 'CO': 'West', 'HI': 'West', 'ID': 'West',
    'MT': 'West', 'NV': 'West', 'OR': 'West', 'UT': 'West', 'WA': 'West', 'WY': 'West',
}

HISTORY_FILE = 'listing_history.json'


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
            row['photo_count'] = safe_int(row.get('photo_count')) or 0
            row['length'] = safe_float(row.get('length'))
            row['year'] = safe_int(row.get('year'))
            row['relevance_score'] = safe_float(row.get('relevance_score'))
            row['merch_score'] = safe_float(row.get('merch_score'))

            row['is_premium'] = row.get('is_premium') in ('1', 'True', 'true', True)
            row['is_top_premium'] = row.get('is_top_premium') in ('1', 'True', 'true', True)

            row['has_price'] = bool(row['price'] and row['price'] > 0)
            row['has_vin'] = bool(row.get('vin'))
            row['has_floorplan'] = bool(row.get('floorplan_id'))
            row['has_length'] = bool(row['length'] and row['length'] > 0)
            row['photos_35'] = row['photo_count'] >= 35

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


def get_listing_key(listing: Dict) -> str:
    """Generate unique key for a listing. Prefer stock_number, fall back to id."""
    stock = listing.get('stock_number', '').strip()
    if stock and stock != '-':
        return f"stock:{stock}"
    listing_id = listing.get('id', '')
    if listing_id:
        return f"id:{listing_id}"
    # Fallback: year+model+dealer
    return f"ymk:{listing.get('year', '')}_{listing.get('model', '')}_{listing.get('dealer_name', '')}"


def calculate_quality_score(listing: Dict) -> int:
    """Calculate quality score (0-100) for a listing."""
    score = 0
    if listing.get('has_price'):
        score += 20
    if listing.get('has_vin'):
        score += 20
    if listing.get('has_floorplan'):
        score += 20
    if listing.get('has_length'):
        score += 20
    if listing.get('photos_35'):
        score += 20
    return score


# =============================================================================
# HISTORY MANAGEMENT
# =============================================================================

def load_history(history_dir: Path) -> Dict:
    """Load listing history from JSON file."""
    history_file = history_dir / HISTORY_FILE
    if history_file.exists():
        with open(history_file, 'r') as f:
            return json.load(f)
    return {'listings': {}, 'weeks': []}


def save_history(history: Dict, history_dir: Path):
    """Save listing history to JSON file."""
    history_file = history_dir / HISTORY_FILE
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=2, default=str)


def update_history(listings: List[Dict], history: Dict, week_date: str) -> Dict:
    """Update history with new week's data."""

    if week_date not in history['weeks']:
        history['weeks'].append(week_date)
        history['weeks'] = sorted(history['weeks'])[-52:]  # Keep last 52 weeks

    # Track which listings we've seen this week
    seen_keys = set()

    for listing in listings:
        key = get_listing_key(listing)
        seen_keys.add(key)

        quality = calculate_quality_score(listing)

        # Create or update listing record
        if key not in history['listings']:
            history['listings'][key] = {
                'first_seen': week_date,
                'last_seen': week_date,
                'stock_number': listing.get('stock_number'),
                'id': listing.get('id'),
                'dealer_name': listing.get('dealer_name'),
                'thor_brand': listing.get('thor_brand'),
                'region': listing.get('region'),
                'year': listing.get('year'),
                'make': listing.get('make'),
                'model': listing.get('model'),
                'weekly_data': {}
            }

        record = history['listings'][key]
        record['last_seen'] = week_date

        # Store this week's snapshot
        record['weekly_data'][week_date] = {
            'rank': listing.get('rank'),
            'price': listing.get('price'),
            'photo_count': listing.get('photo_count'),
            'quality_score': quality,
            'has_price': listing.get('has_price'),
            'has_vin': listing.get('has_vin'),
            'has_floorplan': listing.get('has_floorplan'),
            'has_length': listing.get('has_length'),
            'photos_35': listing.get('photos_35'),
            'is_premium': listing.get('is_premium'),
            'merch_score': listing.get('merch_score'),
            'relevance_score': listing.get('relevance_score'),
        }

        # Trim old weekly data (keep last 12 weeks)
        weeks_to_keep = sorted(record['weekly_data'].keys())[-12:]
        record['weekly_data'] = {w: record['weekly_data'][w] for w in weeks_to_keep}

    return history


def calculate_wow_changes(history: Dict, current_week: str) -> Dict:
    """Calculate week-over-week changes for all listings."""

    weeks = sorted(history['weeks'])
    if current_week not in weeks:
        return {'changes': [], 'new': [], 'sold': [], 'summary': {}}

    current_idx = weeks.index(current_week)
    prev_week = weeks[current_idx - 1] if current_idx > 0 else None

    changes = []
    new_listings = []
    sold_listings = []

    for key, record in history['listings'].items():
        weekly = record.get('weekly_data', {})

        current_data = weekly.get(current_week)
        prev_data = weekly.get(prev_week) if prev_week else None

        if current_data and not prev_data:
            # New listing
            new_listings.append({
                'key': key,
                'stock_number': record.get('stock_number'),
                'dealer_name': record.get('dealer_name'),
                'thor_brand': record.get('thor_brand'),
                'year': record.get('year'),
                'model': record.get('model'),
                'rank': current_data.get('rank'),
                'quality_score': current_data.get('quality_score'),
            })
        elif prev_data and not current_data:
            # Sold/removed listing
            sold_listings.append({
                'key': key,
                'stock_number': record.get('stock_number'),
                'dealer_name': record.get('dealer_name'),
                'thor_brand': record.get('thor_brand'),
                'year': record.get('year'),
                'model': record.get('model'),
                'last_rank': prev_data.get('rank'),
                'last_quality': prev_data.get('quality_score'),
            })
        elif current_data and prev_data:
            # Existing listing - calculate changes
            rank_change = (prev_data.get('rank') or 999) - (current_data.get('rank') or 999)
            quality_change = (current_data.get('quality_score') or 0) - (prev_data.get('quality_score') or 0)

            # Track which actions were completed
            actions_completed = []
            if current_data.get('has_price') and not prev_data.get('has_price'):
                actions_completed.append('Added price')
            if current_data.get('has_vin') and not prev_data.get('has_vin'):
                actions_completed.append('Added VIN')
            if current_data.get('has_floorplan') and not prev_data.get('has_floorplan'):
                actions_completed.append('Added floorplan')
            if current_data.get('has_length') and not prev_data.get('has_length'):
                actions_completed.append('Added length')
            if current_data.get('photos_35') and not prev_data.get('photos_35'):
                actions_completed.append('Added photos (35+)')

            if rank_change != 0 or quality_change != 0 or actions_completed:
                changes.append({
                    'key': key,
                    'stock_number': record.get('stock_number'),
                    'dealer_name': record.get('dealer_name'),
                    'thor_brand': record.get('thor_brand'),
                    'region': record.get('region'),
                    'year': record.get('year'),
                    'model': record.get('model'),
                    'prev_rank': prev_data.get('rank'),
                    'current_rank': current_data.get('rank'),
                    'rank_change': rank_change,
                    'prev_quality': prev_data.get('quality_score'),
                    'current_quality': current_data.get('quality_score'),
                    'quality_change': quality_change,
                    'actions_completed': actions_completed,
                })

    # Sort by rank improvement (biggest improvements first)
    changes.sort(key=lambda x: x.get('rank_change', 0), reverse=True)

    # Calculate summary
    improved = sum(1 for c in changes if c.get('rank_change', 0) > 0)
    declined = sum(1 for c in changes if c.get('rank_change', 0) < 0)
    unchanged = len(changes) - improved - declined
    total_rank_improvement = sum(c.get('rank_change', 0) for c in changes if c.get('rank_change', 0) > 0)
    actions_completed_count = sum(len(c.get('actions_completed', [])) for c in changes)

    return {
        'changes': changes,
        'new': new_listings,
        'sold': sold_listings,
        'summary': {
            'total_tracked': len(history['listings']),
            'improved': improved,
            'declined': declined,
            'unchanged': unchanged,
            'new_listings': len(new_listings),
            'sold_listings': len(sold_listings),
            'total_rank_improvement': total_rank_improvement,
            'actions_completed': actions_completed_count,
        }
    }


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_wow_report(wow_data: Dict, current_week: str, brand_filter: str = None) -> str:
    """Generate HTML week-over-week report."""

    summary = wow_data['summary']
    changes = wow_data['changes']
    new_listings = wow_data['new']
    sold_listings = wow_data['sold']

    # Filter by brand if specified
    if brand_filter:
        changes = [c for c in changes if c.get('thor_brand', '').lower() == brand_filter.lower()]
        new_listings = [n for n in new_listings if n.get('thor_brand', '').lower() == brand_filter.lower()]
        sold_listings = [s for s in sold_listings if s.get('thor_brand', '').lower() == brand_filter.lower()]

    # Generate improvements table
    improvements_rows = []
    for c in changes[:20]:  # Top 20 improvements
        if c.get('rank_change', 0) <= 0:
            continue
        rank_change = c.get('rank_change', 0)
        stock = html.escape(str(c.get('stock_number') or '-'))
        dealer = html.escape(str(c.get('dealer_name', 'Unknown'))[:30])
        brand = html.escape(str(c.get('thor_brand') or '-'))
        year = c.get('year', '-')
        model = html.escape(str(c.get('model', 'Unknown'))[:20])
        prev_rank = c.get('prev_rank', '-')
        curr_rank = c.get('current_rank', '-')
        actions = ', '.join(c.get('actions_completed', [])) or '-'

        improvements_rows.append(f"""
        <tr>
            <td><code>{stock}</code></td>
            <td>{dealer}</td>
            <td>{brand}</td>
            <td>{year} {model}</td>
            <td>{prev_rank}</td>
            <td>{curr_rank}</td>
            <td class="improved">+{rank_change}</td>
            <td>{actions}</td>
        </tr>
        """)

    # Generate declines table
    declines_rows = []
    for c in sorted(changes, key=lambda x: x.get('rank_change', 0))[:10]:
        if c.get('rank_change', 0) >= 0:
            continue
        rank_change = c.get('rank_change', 0)
        stock = html.escape(str(c.get('stock_number') or '-'))
        dealer = html.escape(str(c.get('dealer_name', 'Unknown'))[:30])
        brand = html.escape(str(c.get('thor_brand') or '-'))
        year = c.get('year', '-')
        model = html.escape(str(c.get('model', 'Unknown'))[:20])
        prev_rank = c.get('prev_rank', '-')
        curr_rank = c.get('current_rank', '-')

        declines_rows.append(f"""
        <tr>
            <td><code>{stock}</code></td>
            <td>{dealer}</td>
            <td>{brand}</td>
            <td>{year} {model}</td>
            <td>{prev_rank}</td>
            <td>{curr_rank}</td>
            <td class="declined">{rank_change}</td>
        </tr>
        """)

    # Generate new listings table
    new_rows = []
    for n in new_listings[:15]:
        stock = html.escape(str(n.get('stock_number') or '-'))
        dealer = html.escape(str(n.get('dealer_name', 'Unknown'))[:30])
        brand = html.escape(str(n.get('thor_brand') or '-'))
        year = n.get('year', '-')
        model = html.escape(str(n.get('model', 'Unknown'))[:20])
        rank = n.get('rank', '-')
        quality = n.get('quality_score', '-')

        new_rows.append(f"""
        <tr>
            <td><code>{stock}</code></td>
            <td>{dealer}</td>
            <td>{brand}</td>
            <td>{year} {model}</td>
            <td>{rank}</td>
            <td>{quality}%</td>
        </tr>
        """)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    brand_title = f" - {brand_filter}" if brand_filter else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Week-over-Week Report{brand_title} - {current_week}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #1f2937;
            line-height: 1.5;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

        .header {{
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 20px;
        }}
        .header h1 {{ font-size: 1.8rem; margin-bottom: 5px; }}
        .header .subtitle {{ opacity: 0.9; }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-top: 20px;
        }}
        .summary-stat {{
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{ font-size: 2rem; font-weight: bold; }}
        .stat-value.positive {{ color: #86efac; }}
        .stat-value.negative {{ color: #fca5a5; }}
        .stat-label {{ font-size: 0.8rem; opacity: 0.9; }}

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

        .improved {{ color: #16a34a; font-weight: 600; }}
        .declined {{ color: #dc2626; font-weight: 600; }}

        code {{
            background: #f1f5f9;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.8rem;
        }}

        .empty-state {{
            text-align: center;
            padding: 40px;
            color: #6b7280;
        }}

        .footer {{
            text-align: center;
            padding: 20px;
            color: #9ca3af;
            font-size: 0.8rem;
        }}

        @media print {{
            body {{ background: white; }}
            .card {{ box-shadow: none; border: 1px solid #e5e7eb; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Week-over-Week Performance Report{brand_title}</h1>
            <div class="subtitle">Week of {current_week}</div>
            <div class="summary-grid">
                <div class="summary-stat">
                    <div class="stat-value positive">+{summary.get('improved', 0)}</div>
                    <div class="stat-label">Listings Improved</div>
                </div>
                <div class="summary-stat">
                    <div class="stat-value negative">{summary.get('declined', 0)}</div>
                    <div class="stat-label">Listings Declined</div>
                </div>
                <div class="summary-stat">
                    <div class="stat-value">{summary.get('new_listings', 0)}</div>
                    <div class="stat-label">New Listings</div>
                </div>
                <div class="summary-stat">
                    <div class="stat-value positive">+{summary.get('total_rank_improvement', 0)}</div>
                    <div class="stat-label">Total Positions Gained</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">Top Improvements This Week</div>
            <div class="card-body">
                {'<table><thead><tr><th>Stock #</th><th>Dealer</th><th>Brand</th><th>Vehicle</th><th>Prev Rank</th><th>New Rank</th><th>Change</th><th>Actions Completed</th></tr></thead><tbody>' + ''.join(improvements_rows) + '</tbody></table>' if improvements_rows else '<div class="empty-state">No improvements this week</div>'}
            </div>
        </div>

        <div class="card">
            <div class="card-header">Listings That Declined</div>
            <div class="card-body">
                {'<table><thead><tr><th>Stock #</th><th>Dealer</th><th>Brand</th><th>Vehicle</th><th>Prev Rank</th><th>New Rank</th><th>Change</th></tr></thead><tbody>' + ''.join(declines_rows) + '</tbody></table>' if declines_rows else '<div class="empty-state">No declines this week</div>'}
            </div>
        </div>

        <div class="card">
            <div class="card-header">New Listings Added</div>
            <div class="card-body">
                {'<table><thead><tr><th>Stock #</th><th>Dealer</th><th>Brand</th><th>Vehicle</th><th>Rank</th><th>Quality</th></tr></thead><tbody>' + ''.join(new_rows) + '</tbody></table>' if new_rows else '<div class="empty-state">No new listings this week</div>'}
            </div>
        </div>

        <div class="footer">
            Generated {timestamp} | Thor Industries Weekly Tracking System
        </div>
    </div>
</body>
</html>"""


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Weekly tracking and WoW comparison')
    parser.add_argument('--input', '-i', help='Input ranked_listings CSV')
    parser.add_argument('--report', action='store_true', help='Generate WoW report only (no data update)')
    parser.add_argument('--brand', '-b', help='Filter to specific brand')
    parser.add_argument('--week', '-w', help='Week date (YYYY-MM-DD), defaults to today')
    args = parser.parse_args()

    # Setup paths
    output_dir = Path(__file__).parent.parent.parent / 'output'
    history_dir = output_dir / 'history'
    history_dir.mkdir(parents=True, exist_ok=True)

    # Load history
    history = load_history(history_dir)

    # Determine week date
    week_date = args.week or datetime.now().strftime('%Y-%m-%d')

    if not args.report:
        # Load new data and update history
        if args.input:
            csv_path = Path(args.input)
        else:
            csv_files = sorted(output_dir.glob('ranked_listings*.csv'), reverse=True)
            if not csv_files:
                print("Error: No ranked_listings CSV files found in output/")
                return
            csv_path = csv_files[0]

        print(f"Loading data from: {csv_path}")
        listings = load_csv(str(csv_path))

        thor_listings = [l for l in listings if l.get('thor_brand')]
        print(f"Total listings: {len(listings)}, Thor listings: {len(thor_listings)}")

        print(f"Updating history for week: {week_date}")
        history = update_history(thor_listings, history, week_date)
        save_history(history, history_dir)
        print(f"History saved: {len(history['listings'])} listings tracked across {len(history['weeks'])} weeks")

    # Generate WoW report
    print(f"\nGenerating week-over-week report...")
    wow_data = calculate_wow_changes(history, week_date)

    summary = wow_data['summary']
    print(f"\nSummary for {week_date}:")
    print(f"  Improved: {summary.get('improved', 0)}")
    print(f"  Declined: {summary.get('declined', 0)}")
    print(f"  New listings: {summary.get('new_listings', 0)}")
    print(f"  Sold/removed: {summary.get('sold_listings', 0)}")
    print(f"  Total rank improvement: +{summary.get('total_rank_improvement', 0)} positions")
    print(f"  Actions completed: {summary.get('actions_completed', 0)}")

    # Generate HTML report
    report_html = generate_wow_report(wow_data, week_date, args.brand)

    report_dir = output_dir / 'reports'
    report_dir.mkdir(parents=True, exist_ok=True)

    brand_suffix = f"_{args.brand}" if args.brand else ""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f"wow_report{brand_suffix}_{timestamp}.html"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_html)

    print(f"\nReport saved: {report_path}")
    print(f"Open in browser: file://{report_path}")


if __name__ == '__main__':
    main()
