"""
Flat File Export for Data Loading

Consolidates all RV listing data into a single flat CSV suitable for data warehouse/BI loading.
- Merges ranked_listings CSV + engagement_stats JSON into one file
- Adds metadata columns for tracking/filtering
- Computes derived fields for ALL listings (not just Thor)
- Outputs clean, database-ready CSV (77 columns)

Usage:
    python export_flat_file.py                    # Process latest files
    python export_flat_file.py --append           # Append to master historical file
    python export_flat_file.py --combine-session  # Combine all today's ranked files into one export
    python export_flat_file.py --combine-session --append  # Combine and add to master
    python export_flat_file.py --ranked FILE --engagement FILE  # Explicit inputs
"""

import csv
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any


# =============================================================================
# CONFIGURATION - Export Schema (73 columns)
# =============================================================================

EXPORT_COLUMNS = [
    # Metadata (5)
    'run_id', 'extraction_timestamp', 'source_ranked_file', 'source_engagement_file', 'export_version',

    # Search Context (6)
    'search_zip', 'search_type', 'search_radius', 'search_condition',
    'price_chunk_min', 'price_chunk_max',

    # Identifiers (4)
    'listing_id', 'dealer_id', 'stock_number', 'vin',

    # Vehicle (9)
    'year', 'make', 'model', 'trim', 'class_name', 'class_id', 'condition',
    'length_ft', 'mileage',

    # Pricing (4)
    'price', 'msrp', 'rebate', 'price_vs_msrp_pct',

    # Location (7)
    'city', 'state', 'zip_code', 'region', 'latitude', 'longitude', 'distance_miles',

    # Dealer (6)
    'dealer_name', 'dealer_group', 'dealer_group_id', 'dealer_phone', 'dealer_website', 'seller_type',

    # Ranking (4)
    'rank', 'relevance_score', 'merch_score', 'ad_listing_position',

    # Premium Status (4)
    'is_premium', 'is_top_premium', 'badge_status', 'scheme_code',

    # Quality Indicators (6)
    'photo_count', 'has_floorplan', 'has_price', 'has_vin', 'has_length', 'photos_35_plus',

    # Engagement (3)
    'views', 'saves', 'engagement_fetch_success',

    # Dates (5)
    'create_date', 'days_listed', 'price_drop_date', 'price_drop_days_ago', 'trusted_partner',

    # Tier Analysis (4)
    'tier', 'tier_ceiling', 'is_controllable', 'outperforming_tier',

    # Thor Brand (3)
    'is_thor_brand', 'thor_brand_name', 'thor_parent_company',

    # Improvements (6)
    'estimated_merch_score', 'total_relevance_available', 'total_merch_available',
    'realistic_improvement', 'realistic_new_rank', 'priority_score',

    # URLs (1)
    'listing_url',
]

EXPORT_VERSION = '1.0'


# =============================================================================
# CONSTANTS (reused from other scripts)
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

IMPROVEMENT_FACTORS = {
    'price': {'relevance_pts': 194, 'merch_pts': 5},
    'vin': {'relevance_pts': 165, 'merch_pts': 6},
    'photos_to_35': {'relevance_pts': 195, 'merch_pts': 30},
    'photos_20_to_35': {'relevance_pts': 95, 'merch_pts': 15},
    'floorplan': {'relevance_pts': 50, 'merch_pts': 12},
    'length': {'relevance_pts': 0, 'merch_pts': 8},
}

RELEVANCE_PER_RANK = 15.0
MERCH_BASE_SCORE = 72
MERCH_PHOTO_FACTOR = 0.5
MERCH_PHOTO_CAP = 33


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

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


def safe_bool(val) -> bool:
    """Safely convert to bool."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ('1', 'true', 'yes')
    return bool(val)


# =============================================================================
# FILE DISCOVERY
# =============================================================================

def find_latest_files(output_dir: Path) -> Dict[str, Optional[Path]]:
    """Find most recent ranked_listings and engagement_stats files."""

    # Find latest ranked_listings CSV
    ranked_files = sorted(output_dir.glob('ranked_listings_*.csv'), reverse=True)
    ranked_file = ranked_files[0] if ranked_files else None

    # Find latest engagement_stats JSON
    engagement_files = sorted(output_dir.glob('engagement_stats_*.json'), reverse=True)
    engagement_file = engagement_files[0] if engagement_files else None

    return {
        'ranked': ranked_file,
        'engagement': engagement_file,
    }


def find_session_files(output_dir: Path, hours: int = 24) -> Dict[str, Any]:
    """
    Find all ranked_listings files from current session (last N hours).

    Args:
        output_dir: Directory to search
        hours: Look back this many hours (default 24)

    Returns:
        Dict with 'ranked_files' list and 'engagement' file
    """
    from datetime import timedelta
    import os

    cutoff_time = datetime.now() - timedelta(hours=hours)

    # Find all ranked_listings CSVs modified within the time window
    ranked_files = []
    for f in output_dir.glob('ranked_listings_*.csv'):
        mtime = datetime.fromtimestamp(os.path.getmtime(f))
        if mtime >= cutoff_time:
            ranked_files.append((f, mtime))

    # Sort by modification time (oldest first for consistent ordering)
    ranked_files.sort(key=lambda x: x[1])
    ranked_paths = [f[0] for f in ranked_files]

    # Find latest engagement_stats JSON (engagement data is shared across searches)
    engagement_files = sorted(output_dir.glob('engagement_stats_*.json'), reverse=True)
    engagement_file = engagement_files[0] if engagement_files else None

    return {
        'ranked_files': ranked_paths,
        'engagement': engagement_file,
    }


# =============================================================================
# DATA LOADING
# =============================================================================

def load_ranked_listings(csv_path: Path) -> List[Dict]:
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
            row['rebate'] = safe_float(row.get('rebate'))
            row['latitude'] = safe_float(row.get('latitude'))
            row['longitude'] = safe_float(row.get('longitude'))
            row['distance'] = safe_float(row.get('distance'))

            # Boolean conversions
            row['is_premium'] = safe_bool(row.get('is_premium'))
            row['is_top_premium'] = safe_bool(row.get('is_top_premium'))
            row['trusted_partner'] = safe_bool(row.get('trusted_partner'))

            # Derived booleans
            row['has_price'] = bool(row['price'] and row['price'] > 0)
            row['has_vin'] = bool(row.get('vin'))
            row['has_floorplan'] = bool(row.get('floorplan_id'))
            row['has_length'] = bool(row['length'] and row['length'] > 0)
            row['photos_35_plus'] = row['photo_count'] >= 35

            listings.append(row)

    return listings


def load_engagement_data(json_path: Path) -> Dict[str, Dict]:
    """Load engagement stats and return dict keyed by listing ID."""
    if not json_path or not json_path.exists():
        return {}

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    engagement_map = {}
    for result in data.get('results', []):
        listing_id = str(result.get('id', ''))
        if listing_id:
            engagement_map[listing_id] = {
                'views': result.get('views'),
                'saves': result.get('saves'),
                'success': result.get('success', True),
            }

    return engagement_map


# =============================================================================
# TIER AND IMPROVEMENT CALCULATIONS
# =============================================================================

def calculate_tier_ceilings(listings: List[Dict]) -> Dict[str, int]:
    """Calculate best achievable rank for each tier."""
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


def get_tier(listing: Dict) -> str:
    """Determine listing tier."""
    if listing.get('is_top_premium'):
        return 'top_premium'
    elif listing.get('is_premium'):
        return 'premium'
    return 'standard'


def estimate_merch_score(listing: Dict) -> int:
    """Estimate merch score based on known factors."""
    score = MERCH_BASE_SCORE

    photo_count = listing.get('photo_count', 0)
    photo_pts = min(photo_count * MERCH_PHOTO_FACTOR, MERCH_PHOTO_CAP)
    score += photo_pts

    if listing.get('has_floorplan'):
        score += 12
    if listing.get('has_vin'):
        score += 6
    if listing.get('has_price'):
        score += 5
    if listing.get('has_length'):
        score += 8

    return min(int(score), 125)


def calculate_improvements(listing: Dict, tier_ceilings: Dict) -> Dict:
    """Calculate improvement potential for a listing."""
    total_relevance = 0
    total_merch = 0

    # Price
    if not listing.get('has_price'):
        total_relevance += IMPROVEMENT_FACTORS['price']['relevance_pts']
        total_merch += IMPROVEMENT_FACTORS['price']['merch_pts']

    # VIN
    if not listing.get('has_vin'):
        total_relevance += IMPROVEMENT_FACTORS['vin']['relevance_pts']
        total_merch += IMPROVEMENT_FACTORS['vin']['merch_pts']

    # Photos
    photo_count = listing.get('photo_count', 0)
    if photo_count < 35:
        if photo_count < 20:
            total_relevance += IMPROVEMENT_FACTORS['photos_to_35']['relevance_pts']
            total_merch += IMPROVEMENT_FACTORS['photos_to_35']['merch_pts']
        else:
            total_relevance += IMPROVEMENT_FACTORS['photos_20_to_35']['relevance_pts']
            total_merch += IMPROVEMENT_FACTORS['photos_20_to_35']['merch_pts']

    # Floorplan
    if not listing.get('has_floorplan'):
        total_relevance += IMPROVEMENT_FACTORS['floorplan']['relevance_pts']
        total_merch += IMPROVEMENT_FACTORS['floorplan']['merch_pts']

    # Length
    if not listing.get('has_length'):
        total_merch += IMPROVEMENT_FACTORS['length']['merch_pts']

    # Calculate rank improvement
    current_rank = listing.get('rank') or 999
    tier = get_tier(listing)
    tier_ceiling = tier_ceilings.get(tier, 1)

    unconstrained_improvement = int(total_relevance / RELEVANCE_PER_RANK) if total_relevance > 0 else 0
    unconstrained_new_rank = max(1, current_rank - unconstrained_improvement)

    outperforming_tier = current_rank < tier_ceiling

    if outperforming_tier:
        realistic_new_rank = current_rank
        realistic_improvement = 0
    else:
        realistic_new_rank = max(tier_ceiling, unconstrained_new_rank)
        realistic_improvement = current_rank - realistic_new_rank

    # Priority score (weighted by improvement potential)
    priority_score = total_relevance * 0.5 + total_merch * 0.3 + realistic_improvement * 10

    return {
        'estimated_merch_score': estimate_merch_score(listing),
        'total_relevance_available': total_relevance,
        'total_merch_available': total_merch,
        'realistic_improvement': realistic_improvement,
        'realistic_new_rank': realistic_new_rank,
        'priority_score': round(priority_score, 1),
        'tier': tier,
        'tier_ceiling': tier_ceiling,
        'is_controllable': tier == 'standard',
        'outperforming_tier': outperforming_tier,
    }


def identify_thor_brand(make: str) -> Optional[str]:
    """Check if a make belongs to Thor Industries family."""
    if not make:
        return None
    make_lower = make.lower().strip()
    for pattern, brand_name in THOR_BRANDS.items():
        if pattern in make_lower:
            return brand_name
    return None


def calculate_days_listed(listing: Dict) -> Optional[int]:
    """Calculate days since listing was created."""
    create_date = listing.get('create_date')
    if not create_date:
        return None
    try:
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


# =============================================================================
# ENRICHMENT AND EXPORT
# =============================================================================

def enrich_listing(listing: Dict, engagement_data: Dict, tier_ceilings: Dict,
                   run_id: str, timestamp: str, ranked_file: str, engagement_file: str) -> Dict:
    """Enrich a single listing with all computed columns."""

    listing_id = str(listing.get('id', ''))
    engagement = engagement_data.get(listing_id, {})
    improvements = calculate_improvements(listing, tier_ceilings)
    thor_brand = identify_thor_brand(listing.get('make', ''))

    # Calculate price vs MSRP percentage
    price = listing.get('price')
    msrp = listing.get('msrp')
    price_vs_msrp_pct = None
    if price and msrp and msrp > 0:
        price_vs_msrp_pct = round((price - msrp) / msrp * 100, 1)

    return {
        # Metadata (5)
        'run_id': run_id,
        'extraction_timestamp': timestamp,
        'source_ranked_file': ranked_file,
        'source_engagement_file': engagement_file or '',
        'export_version': EXPORT_VERSION,

        # Search Context (6)
        'search_zip': listing.get('search_zip', ''),
        'search_type': listing.get('search_type', ''),
        'search_radius': listing.get('search_radius', ''),
        'search_condition': listing.get('search_condition', ''),
        'price_chunk_min': listing.get('price_chunk_min', ''),
        'price_chunk_max': listing.get('price_chunk_max', ''),

        # Identifiers (4)
        'listing_id': listing_id,
        'dealer_id': listing.get('dealer_id', ''),
        'stock_number': listing.get('stock_number', ''),
        'vin': listing.get('vin', ''),

        # Vehicle (9)
        'year': listing.get('year', ''),
        'make': listing.get('make', ''),
        'model': listing.get('model', ''),
        'trim': listing.get('trim', ''),
        'class_name': listing.get('class', ''),
        'class_id': listing.get('class_id', ''),
        'condition': listing.get('condition', ''),
        'length_ft': listing.get('length', ''),
        'mileage': listing.get('mileage', ''),

        # Pricing (4)
        'price': listing.get('price', ''),
        'msrp': listing.get('msrp', ''),
        'rebate': listing.get('rebate', ''),
        'price_vs_msrp_pct': price_vs_msrp_pct if price_vs_msrp_pct is not None else '',

        # Location (7)
        'city': listing.get('city', ''),
        'state': listing.get('state', ''),
        'zip_code': listing.get('zip_code', ''),
        'region': STATE_TO_REGION.get(listing.get('state', ''), ''),
        'latitude': listing.get('latitude', ''),
        'longitude': listing.get('longitude', ''),
        'distance_miles': listing.get('distance', ''),

        # Dealer (6)
        'dealer_name': listing.get('dealer_name', ''),
        'dealer_group': listing.get('dealer_group', ''),
        'dealer_group_id': listing.get('dealer_group_id', ''),
        'dealer_phone': listing.get('dealer_phone', ''),
        'dealer_website': listing.get('dealer_website', ''),
        'seller_type': listing.get('seller_type', ''),

        # Ranking (4)
        'rank': listing.get('rank', ''),
        'relevance_score': listing.get('relevance_score', ''),
        'merch_score': listing.get('merch_score', ''),
        'ad_listing_position': listing.get('ad_listing_position', ''),

        # Premium Status (4)
        'is_premium': listing.get('is_premium', False),
        'is_top_premium': listing.get('is_top_premium', False),
        'badge_status': listing.get('badge_status', ''),
        'scheme_code': listing.get('scheme_code', ''),

        # Quality Indicators (6)
        'photo_count': listing.get('photo_count', 0),
        'has_floorplan': listing.get('has_floorplan', False),
        'has_price': listing.get('has_price', False),
        'has_vin': listing.get('has_vin', False),
        'has_length': listing.get('has_length', False),
        'photos_35_plus': listing.get('photos_35_plus', False),

        # Engagement (3)
        'views': engagement.get('views', ''),
        'saves': engagement.get('saves', ''),
        'engagement_fetch_success': engagement.get('success', '') if engagement else '',

        # Dates (5)
        'create_date': listing.get('create_date', ''),
        'days_listed': calculate_days_listed(listing) or '',
        'price_drop_date': listing.get('price_drop_date', ''),
        'price_drop_days_ago': calculate_price_drop_days(listing) or '',
        'trusted_partner': listing.get('trusted_partner', False),

        # Tier Analysis (4)
        'tier': improvements['tier'],
        'tier_ceiling': improvements['tier_ceiling'],
        'is_controllable': improvements['is_controllable'],
        'outperforming_tier': improvements['outperforming_tier'],

        # Thor Brand (3)
        'is_thor_brand': thor_brand is not None,
        'thor_brand_name': thor_brand or '',
        'thor_parent_company': 'Thor Industries' if thor_brand else '',

        # Improvements (6)
        'estimated_merch_score': improvements['estimated_merch_score'],
        'total_relevance_available': improvements['total_relevance_available'],
        'total_merch_available': improvements['total_merch_available'],
        'realistic_improvement': improvements['realistic_improvement'],
        'realistic_new_rank': improvements['realistic_new_rank'],
        'priority_score': improvements['priority_score'],

        # URLs (1)
        'listing_url': listing.get('listing_url', ''),
    }


def export_to_csv(rows: List[Dict], output_path: Path):
    """Write rows to CSV file with proper NULL handling."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS, extrasaction='ignore')
        writer.writeheader()

        for row in rows:
            # Convert None to empty string, booleans to 1/0
            clean_row = {}
            for col in EXPORT_COLUMNS:
                val = row.get(col, '')
                if val is None:
                    clean_row[col] = ''
                elif isinstance(val, bool):
                    clean_row[col] = '1' if val else '0'
                else:
                    clean_row[col] = val
            writer.writerow(clean_row)


def append_to_master(rows: List[Dict], master_path: Path):
    """Append to historical master file, deduplicating by listing_id + extraction_timestamp."""

    existing_keys = set()
    existing_rows = []

    # Load existing data if file exists
    if master_path.exists():
        with open(master_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = f"{row.get('listing_id')}_{row.get('extraction_timestamp')}"
                existing_keys.add(key)
                existing_rows.append(row)

    # Filter new rows to avoid duplicates
    new_rows = []
    for row in rows:
        key = f"{row.get('listing_id')}_{row.get('extraction_timestamp')}"
        if key not in existing_keys:
            new_rows.append(row)
            existing_keys.add(key)

    # Write all rows (existing + new)
    all_rows = existing_rows + new_rows

    with open(master_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS, extrasaction='ignore')
        writer.writeheader()

        for row in all_rows:
            clean_row = {}
            for col in EXPORT_COLUMNS:
                val = row.get(col, '')
                if val is None:
                    clean_row[col] = ''
                elif isinstance(val, bool):
                    clean_row[col] = '1' if val else '0'
                else:
                    clean_row[col] = val
            writer.writerow(clean_row)

    return len(new_rows)


# =============================================================================
# MAIN EXPORT FUNCTION
# =============================================================================

def export_flat_file(ranked_path: Path = None, engagement_path: Path = None,
                     output_path: Path = None, append_master: bool = False,
                     master_path: Path = None) -> Path:
    """
    Main export function.

    Args:
        ranked_path: Path to ranked_listings CSV (optional, auto-detects if not provided)
        engagement_path: Path to engagement_stats JSON (optional)
        output_path: Path for output CSV (optional, auto-named if not provided)
        append_master: Whether to also append to master historical file
        master_path: Path to master file (optional, uses default if not provided)

    Returns:
        Path to output file
    """
    output_dir = Path(__file__).parent.parent.parent / 'output'

    # Find files if not specified
    if not ranked_path:
        latest = find_latest_files(output_dir)
        ranked_path = latest['ranked']
        if not engagement_path:
            engagement_path = latest['engagement']

    if not ranked_path:
        raise FileNotFoundError("No ranked_listings CSV files found in output/")

    print(f"Loading ranked listings: {ranked_path.name}")
    listings = load_ranked_listings(ranked_path)
    print(f"  Loaded {len(listings)} listings")

    # Load engagement data
    engagement_data = {}
    engagement_file_name = ''
    if engagement_path and engagement_path.exists():
        print(f"Loading engagement data: {engagement_path.name}")
        engagement_data = load_engagement_data(engagement_path)
        engagement_file_name = engagement_path.name
        print(f"  Loaded engagement for {len(engagement_data)} listings")
    else:
        print("No engagement data found - Views/Saves columns will be empty")

    # Calculate tier ceilings
    tier_ceilings = calculate_tier_ceilings(listings)
    print(f"Tier ceilings: {tier_ceilings}")

    # Generate metadata
    run_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().isoformat()

    # Enrich all listings
    print("Enriching listings with computed fields...")
    enriched = []
    for listing in listings:
        enriched_row = enrich_listing(
            listing=listing,
            engagement_data=engagement_data,
            tier_ceilings=tier_ceilings,
            run_id=run_id,
            timestamp=timestamp,
            ranked_file=ranked_path.name,
            engagement_file=engagement_file_name
        )
        enriched.append(enriched_row)

    # Determine output filename
    if not output_path:
        # Extract search info from first listing for filename
        search_zip = listings[0].get('search_zip', 'unknown') if listings else 'unknown'
        search_type = listings[0].get('search_type', 'unknown') if listings else 'unknown'
        search_type_clean = search_type.replace(' ', '_').replace('/', '_') if search_type else 'unknown'
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = output_dir / f"rvtrader_export_{search_zip}_{search_type_clean}_{ts}.csv"

    # Export to CSV
    print(f"\nExporting {len(enriched)} listings to: {output_path.name}")
    export_to_csv(enriched, output_path)
    print(f"  Columns: {len(EXPORT_COLUMNS)}")

    # Count Thor listings
    thor_count = sum(1 for r in enriched if r.get('is_thor_brand') in (True, '1', 1))
    print(f"  Thor brand listings: {thor_count}")

    # Append to master if requested
    if append_master:
        if not master_path:
            master_path = output_dir / 'rvtrader_export_master.csv'

        new_count = append_to_master(enriched, master_path)
        print(f"\nAppended {new_count} new rows to master: {master_path.name}")

    return output_path


def export_combined_session(hours: int = 24, output_path: Path = None,
                            append_master: bool = False, master_path: Path = None) -> Path:
    """
    Combine all ranked_listings files from session into single export.

    Tier ceilings are calculated PER SEARCH TYPE since rankings don't cross types.

    Args:
        hours: Look back this many hours (default 24)
        output_path: Path for output CSV (optional, auto-named if not provided)
        append_master: Whether to also append to master historical file
        master_path: Path to master file (optional, uses default if not provided)

    Returns:
        Path to output file
    """
    output_dir = Path(__file__).parent.parent.parent / 'output'

    # Find session files
    session_files = find_session_files(output_dir, hours=hours)
    ranked_files = session_files['ranked_files']
    engagement_path = session_files['engagement']

    if not ranked_files:
        raise FileNotFoundError(f"No ranked_listings CSV files found in last {hours} hours")

    print(f"Found {len(ranked_files)} ranked_listings files from last {hours} hours:")
    for f in ranked_files:
        print(f"  - {f.name}")

    # Load all listings from all files, tracking source file
    all_listings = []
    file_names = []
    for ranked_path in ranked_files:
        print(f"\nLoading: {ranked_path.name}")
        listings = load_ranked_listings(ranked_path)
        # Tag each listing with its source file
        for listing in listings:
            listing['_source_file'] = ranked_path.name
        all_listings.extend(listings)
        file_names.append(ranked_path.name)
        print(f"  Loaded {len(listings)} listings")

    print(f"\nTotal listings: {len(all_listings)}")

    # Load engagement data
    engagement_data = {}
    engagement_file_name = ''
    if engagement_path and engagement_path.exists():
        print(f"Loading engagement data: {engagement_path.name}")
        engagement_data = load_engagement_data(engagement_path)
        engagement_file_name = engagement_path.name
        print(f"  Loaded engagement for {len(engagement_data)} listings")
    else:
        print("No engagement data found - Views/Saves columns will be empty")

    # Group listings by search_type for tier ceiling calculation
    listings_by_type = {}
    for listing in all_listings:
        search_type = listing.get('search_type', 'unknown')
        if search_type not in listings_by_type:
            listings_by_type[search_type] = []
        listings_by_type[search_type].append(listing)

    print(f"\nListings by type:")
    for search_type, type_listings in listings_by_type.items():
        print(f"  {search_type}: {len(type_listings)} listings")

    # Calculate tier ceilings PER TYPE
    tier_ceilings_by_type = {}
    for search_type, type_listings in listings_by_type.items():
        tier_ceilings_by_type[search_type] = calculate_tier_ceilings(type_listings)
        print(f"  {search_type} ceilings: {tier_ceilings_by_type[search_type]}")

    # Generate metadata
    run_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().isoformat()

    # Enrich all listings (using type-specific tier ceilings)
    print("\nEnriching listings with computed fields...")
    enriched = []
    for listing in all_listings:
        search_type = listing.get('search_type', 'unknown')
        tier_ceilings = tier_ceilings_by_type.get(search_type, {'top_premium': 1, 'premium': 1, 'standard': 1})

        enriched_row = enrich_listing(
            listing=listing,
            engagement_data=engagement_data,
            tier_ceilings=tier_ceilings,
            run_id=run_id,
            timestamp=timestamp,
            ranked_file=listing.get('_source_file', ''),
            engagement_file=engagement_file_name
        )
        enriched.append(enriched_row)

    # Determine output filename
    if not output_path:
        # Use first listing's zip or 'combined'
        search_zip = all_listings[0].get('search_zip', 'combined') if all_listings else 'combined'
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        type_count = len(listings_by_type)
        output_path = output_dir / f"rvtrader_export_{search_zip}_{type_count}types_{ts}.csv"

    # Export to CSV
    print(f"\nExporting {len(enriched)} listings to: {output_path.name}")
    export_to_csv(enriched, output_path)
    print(f"  Columns: {len(EXPORT_COLUMNS)}")

    # Summary by type
    print(f"\nSummary:")
    for search_type, type_listings in listings_by_type.items():
        thor_count = sum(1 for l in type_listings if identify_thor_brand(l.get('make', '')))
        print(f"  {search_type}: {len(type_listings)} total, {thor_count} Thor")

    # Total Thor count
    total_thor = sum(1 for r in enriched if r.get('is_thor_brand') in (True, '1', 1))
    print(f"\nTotal Thor brand listings: {total_thor}")

    # Append to master if requested
    if append_master:
        if not master_path:
            master_path = output_dir / 'rvtrader_export_master.csv'

        new_count = append_to_master(enriched, master_path)
        print(f"\nAppended {new_count} new rows to master: {master_path.name}")

    return output_path


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Export RV listing data to flat CSV for data warehouse/BI loading',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python export_flat_file.py                     # Process latest file only
  python export_flat_file.py --append            # Also append to master file
  python export_flat_file.py --combine-session   # Combine all files from last 24h
  python export_flat_file.py --combine-session --hours 48  # Last 48 hours
  python export_flat_file.py --combine-session --append    # Combine and add to master
  python export_flat_file.py --ranked FILE       # Use specific ranked file
        """
    )
    parser.add_argument('--ranked', '-r', type=Path, help='Input ranked_listings CSV')
    parser.add_argument('--engagement', '-e', type=Path, help='Input engagement_stats JSON')
    parser.add_argument('--output', '-o', type=Path, help='Output CSV path')
    parser.add_argument('--append', '-a', action='store_true', help='Append to master historical file')
    parser.add_argument('--master', '-m', type=Path, help='Master file path (default: rvtrader_export_master.csv)')
    parser.add_argument('--combine-session', '-c', action='store_true',
                        help='Combine all ranked_listings files from session into one export')
    parser.add_argument('--hours', type=int, default=24,
                        help='Hours to look back for --combine-session (default: 24)')

    args = parser.parse_args()

    try:
        if args.combine_session:
            # Combine multiple files from session
            output_path = export_combined_session(
                hours=args.hours,
                output_path=args.output,
                append_master=args.append,
                master_path=args.master
            )
        else:
            # Single file export (existing behavior)
            output_path = export_flat_file(
                ranked_path=args.ranked,
                engagement_path=args.engagement,
                output_path=args.output,
                append_master=args.append,
                master_path=args.master
            )

        print(f"\nDone! Export saved to: {output_path}")
        print(f"Open in Excel: {output_path}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == '__main__':
    main()
