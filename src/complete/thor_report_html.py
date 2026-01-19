"""
Thor Industries Brand Analysis - Interactive HTML Report
Generates an interactive HTML report with:
- Search metadata (zip, type, radius)
- Properly aligned tables
- Hyperlinked RV names
- Spec completion percentage
- Age info (days listed, price drop)
- Image preview on hover/click
- Views and Saves from engagement data (when available)
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
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

# Spec fields available from search API (only 2!)
# Other specs (sleeps, slides, fuel, water capacity, etc.) require detail page scraping
SPEC_FIELDS = [
    ('length', 'Length'),
    ('mileage', 'Mileage'),
]

RELEVANCE_PER_RANK = 15.0

# Year impact on ranking
CURRENT_MODEL_YEAR = 2026
YEAR_PENALTY_POINTS = 24  # ~24 relevance points per year older

# Competitive position definitions
# Based on analysis: Top Premium adds ~60 pts, Premium adds ~20 pts, each year adds ~24 pts
COMPETITIVE_POSITIONS = {
    'dominant': {'label': 'Dominant', 'class': 'bg-success', 'desc': 'Top Premium + current year'},
    'strong': {'label': 'Strong', 'class': 'bg-primary', 'desc': 'Premium + current year OR Top Premium + 1yr old'},
    'competitive': {'label': 'Competitive', 'class': 'bg-info', 'desc': 'Standard + current year (equals 1yr Premium)'},
    'neutral': {'label': 'Neutral', 'class': 'bg-secondary', 'desc': 'Premium + 1yr old (equals current Standard)'},
    'at_risk': {'label': 'At Risk', 'class': 'bg-warning text-dark', 'desc': 'Standard + 1yr old'},
    'disadvantaged': {'label': 'Disadvantaged', 'class': 'bg-danger', 'desc': '2+ years old or Standard + old'},
}

# =============================================================================
# DATA LOADING
# =============================================================================

def load_engagement_data(output_dir: Path) -> Dict[str, Dict]:
    """Load most recent engagement stats and return as dict keyed by listing ID."""
    json_files = sorted(output_dir.glob('engagement_stats_*.json'), reverse=True)
    if not json_files:
        print("No engagement data found - Views/Saves columns will be empty")
        return {}

    latest = json_files[0]
    print(f"Loading engagement data: {latest.name}")

    with open(latest, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Build lookup by listing ID
    engagement_map = {}
    for result in data.get('results', []):
        listing_id = str(result.get('id', ''))
        if listing_id:
            engagement_map[listing_id] = {
                'views': result.get('views'),
                'saves': result.get('saves'),
            }

    print(f"Loaded engagement data for {len(engagement_map)} listings")
    return engagement_map


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

def load_ranked_listings(csv_path: str) -> List[Dict]:
    """Load ranked listings from CSV file."""
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
            row['mileage'] = safe_int(row.get('mileage'))
            row['year'] = safe_int(row.get('year'))
            row['is_premium'] = row.get('is_premium') in ('1', 'True', 'true', True)
            row['is_top_premium'] = row.get('is_top_premium') in ('1', 'True', 'true', True)
            row['has_price'] = bool(row['price'] and row['price'] > 0)
            row['has_vin'] = bool(row.get('vin'))
            row['has_floorplan'] = bool(row.get('floorplan_id'))
            row['has_length'] = bool(row['length'] and row['length'] > 0)
            listings.append(row)
    return listings

def identify_thor_brand(make: str) -> Optional[str]:
    if not make:
        return None
    make_lower = make.lower().strip()
    for pattern, brand_name in THOR_BRANDS.items():
        if pattern in make_lower:
            return brand_name
    return None

# =============================================================================
# CALCULATIONS
# =============================================================================

def calculate_spec_completion(listing: Dict) -> Dict:
    """Calculate spec completion for length and mileage (only specs from search API)."""
    has_length = bool(listing.get('length') and float(listing.get('length') or 0) > 0)
    has_mileage = bool(listing.get('mileage') and int(float(listing.get('mileage') or 0)) > 0)

    filled = sum([has_length, has_mileage])
    total = 2

    return {
        'filled': filled,
        'total': total,
        'pct': round(filled / total * 100, 1) if total > 0 else 0,
        'has_length': has_length,
        'has_mileage': has_mileage,
        'length_val': listing.get('length'),
        'mileage_val': listing.get('mileage'),
    }

def calculate_days_listed(listing: Dict) -> Optional[int]:
    """Calculate days since listing was created."""
    create_date = listing.get('create_date')
    if not create_date:
        return None
    try:
        # Try parsing various date formats
        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%m/%d/%Y']:
            try:
                created = datetime.strptime(create_date[:19], fmt)
                return (datetime.now() - created).days
            except ValueError:
                continue
        return None
    except Exception:
        return None

def calculate_price_drop_days(listing: Dict) -> Optional[int]:
    """Calculate days since last price drop."""
    price_drop = listing.get('price_drop_date')
    if not price_drop:
        return None
    try:
        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%m/%d/%Y']:
            try:
                drop_date = datetime.strptime(price_drop[:19], fmt)
                return (datetime.now() - drop_date).days
            except ValueError:
                continue
        return None
    except Exception:
        return None

def get_tier(listing: Dict) -> str:
    if listing.get('is_top_premium'):
        return 'top_premium'
    elif listing.get('is_premium'):
        return 'premium'
    return 'standard'


def get_competitive_position(listing: Dict) -> str:
    """
    Calculate competitive position based on year + tier.

    Key findings from analysis:
    - Top Premium adds ~60 pts over Premium
    - Premium adds ~20 pts over Standard
    - Each model year adds ~24 pts
    - 2026 Standard roughly equals 2025 Premium
    - Need Top Premium to really break through
    """
    year = listing.get('year') or 0
    years_old = CURRENT_MODEL_YEAR - year
    is_top_premium = listing.get('is_top_premium')
    is_premium = listing.get('is_premium')

    # Top Premium tier - dominant regardless of year (up to 2 years)
    if is_top_premium:
        if years_old <= 0:
            return 'dominant'
        elif years_old == 1:
            return 'strong'
        else:
            return 'competitive'

    # Premium tier
    if is_premium:
        if years_old <= 0:
            return 'strong'
        elif years_old == 1:
            return 'neutral'  # 2025 Premium = 2026 Standard
        else:
            return 'at_risk'

    # Standard tier
    if years_old <= 0:
        return 'competitive'  # 2026 Standard can compete
    elif years_old == 1:
        return 'at_risk'
    else:
        return 'disadvantaged'


def get_year_penalty(listing: Dict) -> int:
    """Calculate relevance point penalty due to model year."""
    year = listing.get('year') or CURRENT_MODEL_YEAR
    years_old = CURRENT_MODEL_YEAR - year
    return max(0, years_old * YEAR_PENALTY_POINTS)

def calculate_tier_ceilings(listings: List[Dict]) -> Dict[str, int]:
    top_premium_ranks = [l['rank'] for l in listings if l.get('is_top_premium') and l.get('rank')]
    premium_ranks = [l['rank'] for l in listings if l.get('is_premium') and l.get('rank')]

    top_premium_ceiling = 1
    premium_ceiling = max(top_premium_ranks) + 1 if top_premium_ranks else 1
    standard_ceiling = max(premium_ranks) + 1 if premium_ranks else 1

    return {
        'top_premium': top_premium_ceiling,
        'premium': premium_ceiling,
        'standard': standard_ceiling,
    }

def get_image_url(listing: Dict) -> str:
    """Construct image URL for listing."""
    listing_id = listing.get('id', '')
    if listing_id:
        # RVTrader CDN pattern
        return f"https://cdn-p.tradercdn.com/images/rvtrader/{listing_id}/0.jpg"
    return ""

def calculate_improvements(listing: Dict) -> List[str]:
    """Get list of improvement actions needed, including year-aware recommendations."""
    actions = []

    # Standard merch improvements
    if not listing.get('has_price'):
        actions.append('Add price (+194 rel)')
    if not listing.get('has_vin'):
        actions.append('Add VIN (+165 rel)')
    photo_count = listing.get('photo_count', 0)
    if photo_count < 35:
        actions.append(f'Add {35 - photo_count} photos (+195 rel)')
    if not listing.get('has_floorplan'):
        actions.append('Add floorplan (+50 rel)')
    if not listing.get('has_length'):
        actions.append('Add length (+8 merch)')

    # Year-aware recommendations
    year = listing.get('year') or 0
    years_old = CURRENT_MODEL_YEAR - year
    is_top_premium = listing.get('is_top_premium')
    is_premium = listing.get('is_premium')

    if years_old >= 1 and not is_top_premium:
        year_penalty = years_old * YEAR_PENALTY_POINTS
        if not is_premium:
            # Standard + old year = needs Premium to compete
            actions.append(f'Year penalty: -{year_penalty} pts. Upgrade to Premium')
        else:
            # Premium + old year = needs Top Premium to break through
            actions.append(f'Year penalty: -{year_penalty} pts. Consider Top Premium')

    return actions

# =============================================================================
# HTML GENERATION
# =============================================================================

def generate_html_report(listings: List[Dict], output_path: str, engagement_data: Dict[str, Dict] = None):
    """Generate interactive HTML report."""

    # Get search metadata from first listing
    search_zip = listings[0].get('search_zip', 'N/A') if listings else 'N/A'
    search_type = listings[0].get('search_type', 'N/A') if listings else 'N/A'
    search_radius = '200 miles'  # Default, could be extracted if stored

    # Merge engagement data with listings
    if engagement_data:
        for listing in listings:
            listing_id = str(listing.get('id', ''))
            if listing_id in engagement_data:
                listing['views'] = engagement_data[listing_id].get('views')
                listing['saves'] = engagement_data[listing_id].get('saves')
            else:
                listing['views'] = None
                listing['saves'] = None
    else:
        for listing in listings:
            listing['views'] = None
            listing['saves'] = None

    # Identify Thor brands
    for listing in listings:
        listing['thor_brand'] = identify_thor_brand(listing.get('make', ''))

    thor_listings = [l for l in listings if l.get('thor_brand')]
    tier_ceilings = calculate_tier_ceilings(listings)

    # Enrich listings with calculations
    for listing in thor_listings:
        listing['spec_completion'] = calculate_spec_completion(listing)
        listing['days_listed'] = calculate_days_listed(listing)
        listing['price_drop_days'] = calculate_price_drop_days(listing)
        listing['image_url'] = get_image_url(listing)
        listing['improvements'] = calculate_improvements(listing)
        listing['tier'] = get_tier(listing)
        listing['competitive_position'] = get_competitive_position(listing)
        listing['year_penalty'] = get_year_penalty(listing)

    # Group by brand
    by_brand = defaultdict(list)
    for l in thor_listings:
        by_brand[l['thor_brand']].append(l)

    # Generate HTML
    html_content = generate_html_template(
        listings=listings,
        thor_listings=thor_listings,
        by_brand=by_brand,
        tier_ceilings=tier_ceilings,
        search_zip=search_zip,
        search_type=search_type,
        search_radius=search_radius
    )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML report saved: {output_path}")
    return output_path

def generate_html_template(listings, thor_listings, by_brand, tier_ceilings,
                           search_zip, search_type, search_radius) -> str:
    """Generate full HTML content."""

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    total_thor = len(thor_listings)
    total_all = len(listings)
    thor_pct = round(total_thor / total_all * 100, 1) if total_all > 0 else 0

    # Calculate summary stats
    top_premium_count = len([l for l in thor_listings if l.get('is_top_premium')])
    premium_count = len([l for l in thor_listings if l.get('is_premium') and not l.get('is_top_premium')])
    standard_count = total_thor - top_premium_count - premium_count

    # Year breakdown stats
    current_year_count = len([l for l in thor_listings if l.get('year') == CURRENT_MODEL_YEAR])
    one_year_old_count = len([l for l in thor_listings if l.get('year') == CURRENT_MODEL_YEAR - 1])
    older_count = len([l for l in thor_listings if (l.get('year') or 0) < CURRENT_MODEL_YEAR - 1])

    current_year_pct = round(current_year_count / total_thor * 100) if total_thor > 0 else 0
    one_year_pct = round(one_year_old_count / total_thor * 100) if total_thor > 0 else 0
    older_pct = round(older_count / total_thor * 100) if total_thor > 0 else 0

    # Competitive position breakdown
    position_counts = {}
    for pos in COMPETITIVE_POSITIONS.keys():
        position_counts[pos] = len([l for l in thor_listings if l.get('competitive_position') == pos])

    # Brand summary rows
    brand_rows = []
    for brand in sorted(by_brand.keys()):
        brand_list = by_brand[brand]
        ranks = [l['rank'] for l in brand_list if l.get('rank')]
        avg_rank = sum(ranks) / len(ranks) if ranks else 0
        merch_scores = [l['merch_score'] for l in brand_list if l.get('merch_score')]
        avg_merch = sum(merch_scores) / len(merch_scores) if merch_scores else 0
        has_length = len([l for l in brand_list if l.get('length') and float(l.get('length') or 0) > 0])
        length_pct = round(has_length / len(brand_list) * 100) if brand_list else 0

        brand_rows.append(f"""
            <tr>
                <td><strong>{html.escape(brand)}</strong></td>
                <td class="text-center">{len(brand_list)}</td>
                <td class="text-center">{avg_rank:.1f}</td>
                <td class="text-center">{avg_merch:.0f}</td>
                <td class="text-center">{length_pct}%</td>
            </tr>
        """)

    # Listing rows by brand
    listing_sections = []
    for brand in sorted(by_brand.keys()):
        brand_list = sorted(by_brand[brand], key=lambda x: x.get('rank') or 999)

        rows = []
        for l in brand_list:
            rank = l.get('rank', '-')
            year = l.get('year', '')
            model = html.escape(l.get('model', '') or '')[:30]
            price = f"${l['price']:,.0f}" if l.get('price') else '<span class="text-danger">NO PRICE</span>'
            photos = l.get('photo_count', 0)
            photo_class = 'text-success' if photos >= 35 else 'text-warning' if photos >= 20 else 'text-danger'
            length_val = l.get('length')
            length_str = f"{length_val:.0f}ft" if length_val else '<span class="text-danger">-</span>'
            merch = l.get('merch_score') or 0

            # Mileage (the other spec from search API, length already shown)
            mileage_val = l.get('mileage')
            mileage_str = f"{int(mileage_val):,}" if mileage_val else '-'

            # Age info
            days = l.get('days_listed')
            days_str = f"{days}d" if days is not None else '-'
            days_class = 'text-success' if days and days < 30 else 'text-warning' if days and days < 90 else 'text-danger' if days else ''

            price_drop = l.get('price_drop_days')
            drop_str = f"{price_drop}d ago" if price_drop is not None else '-'

            # Competitive position badge (combines tier + year)
            position = l.get('competitive_position', 'disadvantaged')
            pos_info = COMPETITIVE_POSITIONS.get(position, COMPETITIVE_POSITIONS['disadvantaged'])
            position_badge = f'<span class="badge {pos_info["class"]}">{pos_info["label"]}</span>'

            # Also show tier for clarity
            tier = l.get('tier', 'standard')
            tier_abbrev = {'top_premium': 'TP', 'premium': 'P', 'standard': 'S'}.get(tier, 'S')

            # Actions
            improvements = l.get('improvements', [])
            actions_str = '<br>'.join(improvements[:3]) if improvements else '<span class="text-success">Complete</span>'

            # Image URL and listing URL
            image_url = l.get('image_url', '')
            listing_url = l.get('listing_url', '#')
            listing_id = l.get('id', '')

            # Engagement data (views/saves)
            views = l.get('views')
            saves = l.get('saves')
            views_str = f"{int(views):,}" if views is not None else '-'
            saves_str = str(saves) if saves is not None else '-'
            # Color code views: green if high, yellow if medium, red if low
            views_class = 'text-success' if views and views >= 100 else 'text-warning' if views and views >= 30 else 'text-danger' if views is not None else ''

            rows.append(f"""
                <tr class="listing-row" data-image="{html.escape(image_url)}" data-id="{listing_id}">
                    <td class="text-center fw-bold">{rank}</td>
                    <td>{year}</td>
                    <td>
                        <a href="{html.escape(listing_url)}" target="_blank" class="listing-link"
                           data-image="{html.escape(image_url)}">
                            {model}
                        </a>
                    </td>
                    <td class="text-end">{price}</td>
                    <td class="text-center {photo_class}">{photos}</td>
                    <td class="text-center">{length_str}</td>
                    <td class="text-center {views_class}">{views_str}</td>
                    <td class="text-center">{saves_str}</td>
                    <td class="text-center">{merch:.0f}</td>
                    <td class="text-center {days_class}">{days_str}</td>
                    <td class="text-center"><span class="text-muted">{tier_abbrev}</span></td>
                    <td class="text-center">{position_badge}</td>
                    <td class="small">{actions_str}</td>
                </tr>
            """)

        listing_sections.append(f"""
            <div class="card mb-4">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">{html.escape(brand)} ({len(brand_list)} listings)</h5>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-striped table-hover mb-0">
                            <thead class="table-dark">
                                <tr>
                                    <th class="text-center" style="width:60px">Rank</th>
                                    <th style="width:60px">Year</th>
                                    <th>Model</th>
                                    <th class="text-end" style="width:100px">Price</th>
                                    <th class="text-center" style="width:70px">Photos</th>
                                    <th class="text-center" style="width:70px">Length</th>
                                    <th class="text-center" style="width:70px">Views</th>
                                    <th class="text-center" style="width:60px">Saves</th>
                                    <th class="text-center" style="width:60px">Merch</th>
                                    <th class="text-center" style="width:70px">Listed</th>
                                    <th class="text-center" style="width:50px">Tier</th>
                                    <th class="text-center" style="width:110px">Position</th>
                                    <th style="width:220px">Actions Needed</th>
                                </tr>
                            </thead>
                            <tbody>
                                {''.join(rows)}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        """)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thor Industries Brand Analysis Report</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .stat-card {{ border-left: 4px solid; padding: 1rem; background: #f8f9fa; margin-bottom: 1rem; }}
        .stat-card.primary {{ border-color: #0d6efd; }}
        .stat-card.success {{ border-color: #198754; }}
        .stat-card.warning {{ border-color: #ffc107; }}
        .stat-card.info {{ border-color: #0dcaf0; }}
        .stat-value {{ font-size: 2rem; font-weight: bold; }}
        .stat-label {{ color: #6c757d; font-size: 0.875rem; }}
        .listing-link {{ text-decoration: none; color: #0d6efd; }}
        .listing-link:hover {{ text-decoration: underline; }}
        .table th {{ white-space: nowrap; }}
        .table td {{ vertical-align: middle; }}

        /* Image preview popup */
        #image-preview {{
            display: none;
            position: fixed;
            z-index: 9999;
            background: white;
            border: 2px solid #333;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            padding: 8px;
            max-width: 400px;
        }}
        #image-preview img {{
            max-width: 100%;
            border-radius: 4px;
        }}
        #image-preview .caption {{
            text-align: center;
            padding-top: 8px;
            font-size: 0.875rem;
            color: #666;
        }}

        .listing-row {{ cursor: pointer; }}
        .listing-row:hover {{ background-color: #e3f2fd !important; }}

        .search-meta {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
        }}
        .search-meta h1 {{ margin-bottom: 0.5rem; }}
        .search-meta .meta-item {{
            display: inline-block;
            margin-right: 2rem;
            padding: 0.5rem 1rem;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
        }}
        .search-meta .meta-label {{ font-size: 0.75rem; opacity: 0.8; }}
        .search-meta .meta-value {{ font-size: 1.1rem; font-weight: bold; }}
    </style>
</head>
<body>
    <!-- Image Preview Popup -->
    <div id="image-preview">
        <img src="" alt="RV Preview">
        <div class="caption">Click listing to open on RVTrader</div>
    </div>

    <div class="container-fluid py-4">
        <!-- Header with Search Metadata -->
        <div class="search-meta">
            <h1>Thor Industries Brand Analysis Report</h1>
            <p class="mb-3">Generated: {timestamp}</p>
            <div class="meta-item">
                <div class="meta-label">Search Location</div>
                <div class="meta-value">{html.escape(str(search_zip))}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">RV Type</div>
                <div class="meta-value">{html.escape(str(search_type))}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Radius</div>
                <div class="meta-value">{html.escape(search_radius)}</div>
            </div>
        </div>

        <!-- Summary Stats -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="stat-card primary">
                    <div class="stat-value">{total_thor}</div>
                    <div class="stat-label">Thor Brand Listings ({thor_pct}% of market)</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card success">
                    <div class="stat-value">{top_premium_count} / {premium_count} / {standard_count}</div>
                    <div class="stat-label">Top Premium / Premium / Standard</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card warning">
                    <div class="stat-value">{current_year_count} / {one_year_old_count} / {older_count}</div>
                    <div class="stat-label">{CURRENT_MODEL_YEAR} ({current_year_pct}%) / {CURRENT_MODEL_YEAR-1} ({one_year_pct}%) / Older ({older_pct}%)</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card info">
                    <div class="stat-value">{tier_ceilings['standard']}</div>
                    <div class="stat-label">Standard Tier Ceiling (Best Rank)</div>
                </div>
            </div>
        </div>

        <!-- Competitive Position Summary -->
        <div class="card mb-4">
            <div class="card-header">
                <h5 class="mb-0">Competitive Position Breakdown</h5>
            </div>
            <div class="card-body">
                <div class="row text-center">
                    <div class="col">
                        <span class="badge bg-success fs-5">{position_counts.get('dominant', 0)}</span>
                        <div class="small text-muted mt-1">Dominant</div>
                        <div class="small">TP + {CURRENT_MODEL_YEAR}</div>
                    </div>
                    <div class="col">
                        <span class="badge bg-primary fs-5">{position_counts.get('strong', 0)}</span>
                        <div class="small text-muted mt-1">Strong</div>
                        <div class="small">P + {CURRENT_MODEL_YEAR}</div>
                    </div>
                    <div class="col">
                        <span class="badge bg-info fs-5">{position_counts.get('competitive', 0)}</span>
                        <div class="small text-muted mt-1">Competitive</div>
                        <div class="small">S + {CURRENT_MODEL_YEAR}</div>
                    </div>
                    <div class="col">
                        <span class="badge bg-secondary fs-5">{position_counts.get('neutral', 0)}</span>
                        <div class="small text-muted mt-1">Neutral</div>
                        <div class="small">P + {CURRENT_MODEL_YEAR-1}</div>
                    </div>
                    <div class="col">
                        <span class="badge bg-warning text-dark fs-5">{position_counts.get('at_risk', 0)}</span>
                        <div class="small text-muted mt-1">At Risk</div>
                        <div class="small">S + {CURRENT_MODEL_YEAR-1}</div>
                    </div>
                    <div class="col">
                        <span class="badge bg-danger fs-5">{position_counts.get('disadvantaged', 0)}</span>
                        <div class="small text-muted mt-1">Disadvantaged</div>
                        <div class="small">2+ yrs old</div>
                    </div>
                </div>
                <div class="mt-3 small text-muted">
                    <strong>Key insight:</strong> {CURRENT_MODEL_YEAR} Standard = {CURRENT_MODEL_YEAR-1} Premium (year bonus ~24 pts = Premium boost ~20 pts).
                    Need <strong>Top Premium</strong> to truly dominate rankings.
                </div>
            </div>
        </div>

        <!-- Brand Summary Table -->
        <div class="card mb-4">
            <div class="card-header">
                <h5 class="mb-0">Brand Performance Summary</h5>
            </div>
            <div class="card-body">
                <table class="table table-bordered">
                    <thead class="table-light">
                        <tr>
                            <th>Brand</th>
                            <th class="text-center">Listings</th>
                            <th class="text-center">Avg Rank</th>
                            <th class="text-center">Avg Merch</th>
                            <th class="text-center">Has Length</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(brand_rows)}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Listings by Brand -->
        <h4 class="mb-3">Detailed Listings by Brand</h4>
        <p class="text-muted mb-4">
            <strong>Tip:</strong> Hover over any listing row to preview the RV image. Click the model name to open on RVTrader.
        </p>

        {''.join(listing_sections)}

        <!-- Legend -->
        <div class="card mt-4">
            <div class="card-header">
                <h6 class="mb-0">Legend & Point Values</h6>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-4">
                        <h6>Competitive Positions</h6>
                        <ul class="list-unstyled small">
                            <li><span class="badge bg-success">Dominant</span> Top Premium + current year</li>
                            <li><span class="badge bg-primary">Strong</span> Premium + current year</li>
                            <li><span class="badge bg-info">Competitive</span> Standard + current year</li>
                            <li><span class="badge bg-secondary">Neutral</span> Premium + 1yr old</li>
                            <li><span class="badge bg-warning text-dark">At Risk</span> Standard + 1yr old</li>
                            <li><span class="badge bg-danger">Disadvantaged</span> 2+ years old</li>
                        </ul>
                    </div>
                    <div class="col-md-4">
                        <h6>Tier Abbreviations</h6>
                        <ul class="list-unstyled small">
                            <li><strong>TP</strong> = Top Premium (~60 pts above Premium)</li>
                            <li><strong>P</strong> = Premium (~20 pts above Standard)</li>
                            <li><strong>S</strong> = Standard (free listing)</li>
                        </ul>
                        <h6 class="mt-3">Year Impact</h6>
                        <ul class="list-unstyled small">
                            <li>Each year older: <strong>-24</strong> relevance points</li>
                            <li>2026 Standard = 2025 Premium (roughly equal)</li>
                        </ul>
                    </div>
                    <div class="col-md-4">
                        <h6>Improvement Point Values</h6>
                        <ul class="list-unstyled small">
                            <li>Add price: <strong>+194</strong> relevance</li>
                            <li>Add VIN: <strong>+165</strong> relevance</li>
                            <li>Add 35+ photos: <strong>+195</strong> relevance</li>
                            <li>Add floorplan: <strong>+50</strong> relevance</li>
                            <li>~15 relevance points = 1 rank position</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Image preview functionality
        const preview = document.getElementById('image-preview');
        const previewImg = preview.querySelector('img');

        document.querySelectorAll('.listing-row').forEach(row => {{
            row.addEventListener('mouseenter', (e) => {{
                const imageUrl = row.dataset.image;
                if (imageUrl) {{
                    previewImg.src = imageUrl;
                    preview.style.display = 'block';
                    updatePreviewPosition(e);
                }}
            }});

            row.addEventListener('mousemove', updatePreviewPosition);

            row.addEventListener('mouseleave', () => {{
                preview.style.display = 'none';
            }});
        }});

        function updatePreviewPosition(e) {{
            const x = e.clientX + 20;
            const y = e.clientY + 20;

            // Keep preview in viewport
            const previewRect = preview.getBoundingClientRect();
            const maxX = window.innerWidth - 420;
            const maxY = window.innerHeight - 350;

            preview.style.left = Math.min(x, maxX) + 'px';
            preview.style.top = Math.min(y, maxY) + 'px';
        }}

        // Handle image load errors
        previewImg.addEventListener('error', () => {{
            previewImg.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200"><rect fill="%23ddd" width="300" height="200"/><text x="50%" y="50%" text-anchor="middle" fill="%23999">Image not available</text></svg>';
        }});
    </script>
</body>
</html>"""


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate interactive HTML Thor analysis report')
    parser.add_argument('--input', '-i', help='Input ranked_listings CSV')
    parser.add_argument('--output', '-o', help='Output HTML path')
    args = parser.parse_args()

    # Find input file
    if args.input:
        csv_path = Path(args.input)
    else:
        output_dir = Path(__file__).parent.parent.parent / 'output'
        csv_files = sorted(output_dir.glob('ranked_listings_*.csv'), reverse=True)
        if not csv_files:
            print("Error: No ranked_listings CSV files found")
            return
        csv_path = csv_files[0]

    print(f"Loading: {csv_path}")
    listings = load_ranked_listings(str(csv_path))
    print(f"Loaded {len(listings)} listings")

    # Load engagement data (views/saves)
    output_dir = Path(__file__).parent.parent.parent / 'output'
    engagement_data = load_engagement_data(output_dir)

    # Output path
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    reports_dir = output_dir / 'reports'
    reports_dir.mkdir(exist_ok=True)

    output_path = args.output or str(reports_dir / f'thor_interactive_{timestamp}.html')

    generate_html_report(listings, output_path, engagement_data)
    print(f"\nOpen in browser: file://{output_path}")


if __name__ == '__main__':
    main()
