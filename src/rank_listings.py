"""
Rank RV listings by zip code and type using async HTTP.
Extracts all listings with search position ranks (~5 seconds per zip).

Usage:
    python src/rank_listings.py
    python src/rank_listings.py --zip 60616
    python src/rank_listings.py --type "Class B"
    python src/rank_listings.py --zip 60616 --condition U --radius 100
"""

import json
import sys
import asyncio
import csv
import aiohttp
from pathlib import Path
from datetime import datetime
from urllib.parse import urlencode, quote

# ScraperAPI configuration
SCRAPER_API_KEY = 'ef66e965591986214ea474407eb0adc8'
SCRAPER_API_BASE = 'http://api.scraperapi.com'
USE_SCRAPER_API = True  # Set to False to use direct requests

# RV Type mappings
RV_TYPES = {
    'Class A': '198066',
    'Class B': '198068',
    'Class C': '198067',
    'Fifth Wheel': '198069',
    'Toy Hauler': '198074',
    'Travel Trailer': '198073',
    'Truck Camper': '198072',
    'Pop-Up Camper': '198071',
    'Park Model': '198070',
    'Destination Trailer': '671069',
    'Teardrop Trailer': '764498',
}

# Config
RESULTS_PER_PAGE = 36
MAX_PAGES = 10
MAX_RESULTS = RESULTS_PER_PAGE * MAX_PAGES  # 360
DEFAULT_RADIUS = 50
DEFAULT_CONDITION = 'N'

# Parallelization - reduced when using ScraperAPI due to rate limits
MAX_CONCURRENT_REQUESTS = 10 if USE_SCRAPER_API else 50

# Price breakpoints for chunking
PRICE_BREAKS = [
    0, 5000, 10000, 15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000,
    55000, 60000, 65000, 70000, 75000, 80000, 85000, 90000, 95000, 100000,
    125000, 150000, 175000, 200000, 250000, 300000, 400000, 500000, 750000, 1000000, None
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}


def wrap_with_scraper_api(url: str) -> str:
    """Wrap a URL to route through ScraperAPI."""
    if not USE_SCRAPER_API:
        return url
    return f"{SCRAPER_API_BASE}?api_key={SCRAPER_API_KEY}&url={quote(url, safe='')}"


def load_zip_codes(filepath: str = 'zip_codes.txt') -> list:
    path = Path(filepath)
    if not path.exists():
        return ['60616']
    with open(path, 'r') as f:
        return [line.strip() for line in f if line.strip()]


def build_api_url(rv_type: str, page: int, zip_code: str,
                  radius: int = DEFAULT_RADIUS, condition: str = DEFAULT_CONDITION,
                  price_min: int = None, price_max: int = None) -> str:
    type_code = RV_TYPES.get(rv_type, '198068')
    params = {
        'type': f'{rv_type}|{type_code}',
        'page': page,
        'zip': zip_code,
        'radius': radius,
        'condition': condition,
    }
    if price_min is not None or price_max is not None:
        min_str = str(price_min) if price_min else '*'
        max_str = str(price_max) if price_max else '*'
        params['price'] = f'{min_str}:{max_str}'

    return f"https://www.rvtrader.com/ssr-api/search-results?{urlencode(params, safe='|:*')}"


def extract_raw(val):
    if val is None:
        return None
    if isinstance(val, dict) and 'raw' in val:
        raw = val['raw']
        if isinstance(raw, list) and len(raw) == 1:
            return raw[0]
        return raw
    return val


def parse_json_field(val) -> dict:
    """Parse a JSON string field, returning empty dict on failure."""
    # Handle wrapped {'raw': '...'} format
    if isinstance(val, dict) and 'raw' in val:
        val = val['raw']
    if not val or not isinstance(val, str):
        return {}
    try:
        return json.loads(val)
    except:
        return {}


def flatten_listing(listing: dict, rank: int, zip_code: str, rv_type: str,
                    price_min: int = None, price_max: int = None) -> dict:
    # Parse JSON string fields
    ad_attribs = parse_json_field(listing.get('ad_attribs'))
    ad_features = parse_json_field(listing.get('ad_features'))
    dealer_features = parse_json_field(listing.get('dealer_features'))

    # Get dealer_phone list (may be wrapped in raw dict or direct list)
    dealer_phone_raw = listing.get('dealer_phone')
    if isinstance(dealer_phone_raw, dict) and 'raw' in dealer_phone_raw:
        dealer_phone_list = dealer_phone_raw['raw'] or []
    elif isinstance(dealer_phone_raw, list):
        dealer_phone_list = dealer_phone_raw
    else:
        dealer_phone_list = []
    primary_phone = dealer_phone_list[0].split('|')[0] if dealer_phone_list else extract_raw(listing.get('phone'))

    # Get photo_ids as comma-separated string
    photo_ids = listing.get('photo_ids', [])
    photo_ids_str = ','.join(photo_ids) if photo_ids else None

    return {
        # Search context
        'rank': rank,
        'search_zip': zip_code,
        'search_type': rv_type,
        'price_chunk_min': price_min,
        'price_chunk_max': price_max,

        # Identifiers
        'id': extract_raw(listing.get('ad_id')),
        'dealer_id': extract_raw(listing.get('dealer_id')),
        'customer_id': extract_raw(listing.get('customer_id')),
        'vin': extract_raw(listing.get('mfr_serial_num')),
        'stock_number': extract_raw(listing.get('stock_number')),

        # Vehicle info
        'year': extract_raw(listing.get('year')),
        'make': extract_raw(listing.get('make_name')),
        'make_id': extract_raw(listing.get('make_id')),
        'model': extract_raw(listing.get('model_name')),
        'model_group_id': extract_raw(listing.get('model_group_id')),
        'model_group_name': extract_raw(listing.get('model_group_name')),
        'trim': extract_raw(listing.get('trim_name')),
        'class': extract_raw(listing.get('class_name')),
        'class_id': extract_raw(listing.get('class_id')),
        'condition': extract_raw(listing.get('condition')),
        'length': extract_raw(listing.get('length')),
        'mileage': extract_raw(listing.get('mileage')),
        'description': extract_raw(listing.get('description')),

        # Pricing
        'price': extract_raw(listing.get('price')),
        'msrp': extract_raw(listing.get('msrp')),
        'rebate': extract_raw(listing.get('rebate')),
        'price_drop_date': extract_raw(listing.get('date_price_drop')),

        # Location
        'city': extract_raw(listing.get('city')),
        'state': extract_raw(listing.get('state_code')),
        'zip_code': extract_raw(listing.get('zip_code')),
        'latitude': extract_raw(listing.get('latitude')),
        'longitude': extract_raw(listing.get('longitude')),

        # Dealer info
        'dealer_name': extract_raw(listing.get('company_name')),
        'dealer_group_id': extract_raw(listing.get('dealer_group_id')),
        'dealer_group': extract_raw(listing.get('dealer_group_name')),
        'dealer_website': extract_raw(listing.get('dealer_website_url')),
        'dealer_phone': primary_phone,
        'dealer_phone_all': '|'.join(dealer_phone_list) if dealer_phone_list else None,
        'seller_type': extract_raw(listing.get('seller_type')),
        'trusted_partner': extract_raw(listing.get('trusted_partner')),

        # Photos
        'photo_count': extract_raw(listing.get('photo_count')) or 0,
        'photo_ids': photo_ids_str,
        'floorplan_id': extract_raw(listing.get('floorplan_mediaid')),

        # Dates
        'create_date': extract_raw(listing.get('create_date')),
        'create_date_formatted': extract_raw(listing.get('create_date_formatted')),

        # Ranking/scoring
        'ad_listing_position': extract_raw(listing.get('ad_listing_position')),
        'relevance_score': extract_raw(listing.get('_score')),
        'merch_score': extract_raw(listing.get('lcs_merch_score')),

        # Premium/badge status
        'is_premium': extract_raw(listing.get('is_premium')),
        'is_top_premium': extract_raw(listing.get('is_toppremium')),
        'badge_status': extract_raw(listing.get('badge_status')),
        'scheme_code': extract_raw(listing.get('scheme_code')),

        # Features from ad_features JSON
        'has_vhr': ad_features.get('VHR'),
        'buy_now': ad_features.get('buyNow'),
        'featured_homepage': ad_features.get('featuredHomepage'),
        'featured_search': ad_features.get('featuredSearch'),
        'hide_floor_plans': ad_features.get('hideFloorPlans'),

        # Extra from ad_attribs JSON
        'attribs_msrp': ad_attribs.get('msrp'),
        'attribs_item_url': ad_attribs.get('itemUrl'),

        # Dealer features
        'dealer_has_video': dealer_features.get('hasVideo'),
        'dealer_contact_deactivated': dealer_features.get('deactivateContactDealer'),

        # URLs
        'listing_url': extract_raw(listing.get('ad_detail_url')),
    }


async def fetch_page(session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore) -> dict:
    """Fetch a single API page, optionally through ScraperAPI."""
    async with semaphore:
        try:
            fetch_url = wrap_with_scraper_api(url)
            # Longer timeout for ScraperAPI (they process the request on their end)
            timeout = aiohttp.ClientTimeout(total=60 if USE_SCRAPER_API else 15)
            async with session.get(fetch_url, headers=HEADERS, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 403:
                    print(f"  [WARN] 403 Forbidden - may need ScraperAPI")
        except Exception as e:
            if USE_SCRAPER_API:
                print(f"  [ERR] ScraperAPI request failed: {type(e).__name__}")
        return None


async def extract_type(session: aiohttp.ClientSession, semaphore: asyncio.Semaphore,
                       rv_type: str, zip_code: str, radius: int, condition: str) -> list:
    """Extract all listings for an RV type, using chunking if needed."""

    # Fetch page 1 to get total (this IS our probe - no separate probe step)
    url = build_api_url(rv_type, 1, zip_code, radius, condition)
    data = await fetch_page(session, url, semaphore)

    if not data or 'data' not in data:
        return []

    total = data['data'].get('total_results', 0)
    if total == 0:
        return []

    # Extract listings from page 1 we already have
    page1_listings = []
    raw = data['data'].get('results', [])
    for i, listing in enumerate(raw):
        page1_listings.append(flatten_listing(listing, i + 1, zip_code, rv_type))

    if total <= RESULTS_PER_PAGE:
        # Only 1 page needed, we already have it
        print(f"  [{rv_type}] {total} done")
        return page1_listings

    if total <= MAX_RESULTS:
        # Fetch remaining pages in parallel (we have page 1)
        print(f"  [{rv_type}] {total} - fetching pages 2-{min((total + 35) // 36, 10)}...")
        remaining = await fetch_remaining_pages(session, semaphore, rv_type, zip_code, radius, condition, total)
        return page1_listings + remaining
    else:
        # Need chunking - fire ALL chunks at once, no probing
        print(f"  [{rv_type}] {total} - blasting all price chunks...")
        return await fetch_all_chunks_parallel(session, semaphore, rv_type, zip_code, radius, condition)


async def fetch_remaining_pages(session: aiohttp.ClientSession, semaphore: asyncio.Semaphore,
                                 rv_type: str, zip_code: str, radius: int, condition: str,
                                 total: int, price_min: int = None, price_max: int = None,
                                 rank_offset: int = 0) -> list:
    """Fetch pages 2+ in parallel (when we already have page 1)."""
    num_pages = min((total + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE, MAX_PAGES)

    if num_pages <= 1:
        return []

    # Build URLs for pages 2+
    urls = [
        (page, build_api_url(rv_type, page, zip_code, radius, condition, price_min, price_max))
        for page in range(2, num_pages + 1)
    ]

    # Fetch all in parallel
    tasks = [fetch_page(session, url, semaphore) for page, url in urls]
    results = await asyncio.gather(*tasks)

    all_listings = []
    for idx, data in enumerate(results):
        page_num = urls[idx][0]
        if data and 'data' in data:
            raw_listings = data['data'].get('results', [])
            base_rank = rank_offset + (page_num - 1) * RESULTS_PER_PAGE
            for i, listing in enumerate(raw_listings):
                flat = flatten_listing(listing, base_rank + i + 1, zip_code, rv_type, price_min, price_max)
                all_listings.append(flat)

    return all_listings


async def fetch_all_chunks_parallel(session: aiohttp.ClientSession, semaphore: asyncio.Semaphore,
                                     rv_type: str, zip_code: str, radius: int, condition: str) -> list:
    """Fire ALL price chunk page 1s at once, then all remaining pages. No probing."""

    # Step 1: Fire page 1 of ALL price chunks simultaneously
    chunk_urls = []
    for i in range(len(PRICE_BREAKS) - 1):
        price_min = PRICE_BREAKS[i]
        price_max = PRICE_BREAKS[i + 1]
        url = build_api_url(rv_type, 1, zip_code, radius, condition, price_min, price_max)
        chunk_urls.append((price_min, price_max, url))

    # Fetch all page 1s in parallel
    page1_tasks = [fetch_page(session, url, semaphore) for _, _, url in chunk_urls]
    page1_results = await asyncio.gather(*page1_tasks)

    # Collect page 1 results and determine what else to fetch
    chunks_data = []
    remaining_urls = []

    for idx, data in enumerate(page1_results):
        price_min, price_max, _ = chunk_urls[idx]
        if data and 'data' in data:
            total = data['data'].get('total_results', 0)
            raw = data['data'].get('results', [])
            if total > 0:
                chunks_data.append((price_min, price_max, total, raw))

                # Queue up remaining pages if needed
                num_pages = min((total + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE, MAX_PAGES)
                for page in range(2, num_pages + 1):
                    url = build_api_url(rv_type, page, zip_code, radius, condition, price_min, price_max)
                    remaining_urls.append((price_min, price_max, page, url))

    # Step 2: Fetch all remaining pages in parallel
    remaining_tasks = [fetch_page(session, url, semaphore) for _, _, _, url in remaining_urls]
    remaining_data = await asyncio.gather(*remaining_tasks)

    remaining_results = []
    for idx, data in enumerate(remaining_data):
        price_min, price_max, page, _ = remaining_urls[idx]
        if data and 'data' in data:
            remaining_results.append((price_min, price_max, page, data['data'].get('results', [])))

    # Step 3: Combine everything with proper ranks
    all_listings = []
    rank_offset = 0

    for price_min, price_max, total, page1_raw in chunks_data:
        # Add page 1 listings
        for i, listing in enumerate(page1_raw):
            flat = flatten_listing(listing, rank_offset + i + 1, zip_code, rv_type, price_min, price_max)
            all_listings.append(flat)

        # Add remaining pages for this chunk
        chunk_remaining = [(p, r) for pm, px, p, r in remaining_results if pm == price_min and px == price_max]
        chunk_remaining.sort(key=lambda x: x[0])

        for page, raw in chunk_remaining:
            base = rank_offset + (page - 1) * RESULTS_PER_PAGE
            for i, listing in enumerate(raw):
                flat = flatten_listing(listing, base + i + 1, zip_code, rv_type, price_min, price_max)
                all_listings.append(flat)

        rank_offset += min(total, MAX_RESULTS)

    print(f"    [{rv_type}] {len(chunks_data)} chunks, {len(all_listings)} listings done")
    return all_listings


async def run_extraction(zip_codes: list = None, rv_types: list = None,
                         radius: int = DEFAULT_RADIUS, condition: str = DEFAULT_CONDITION):
    """Main extraction - all types in parallel."""
    if zip_codes is None:
        zip_codes = load_zip_codes()
    if rv_types is None:
        rv_types = list(RV_TYPES.keys())

    print(f"Starting extraction (async HTTP)")
    print(f"  ScraperAPI: {'ENABLED' if USE_SCRAPER_API else 'DISABLED'}")
    print(f"  Zip codes: {zip_codes}")
    print(f"  RV types: {len(rv_types)}")
    print(f"  Max concurrent requests: {MAX_CONCURRENT_REQUESTS}")
    print("-" * 60)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    all_listings = []

    async with aiohttp.ClientSession() as session:
        for zip_code in zip_codes:
            print(f"\nZip code: {zip_code}")

            # Run all types in parallel
            tasks = [
                extract_type(session, semaphore, rv_type, zip_code, radius, condition)
                for rv_type in rv_types
            ]

            results = await asyncio.gather(*tasks)

            for listings in results:
                all_listings.extend(listings)

            print(f"\nZip {zip_code} complete: {sum(len(r) for r in results)} listings")

    return all_listings


def save_results(listings: list, output_dir: str = 'output'):
    Path(output_dir).mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    csv_path = Path(output_dir) / f'ranked_listings_{timestamp}.csv'
    if listings:
        fieldnames = listings[0].keys()
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(listings)
        print(f"\nCSV saved: {csv_path}")

    json_path = Path(output_dir) / f'ranked_listings_{timestamp}.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({'timestamp': datetime.now().isoformat(), 'count': len(listings), 'listings': listings},
                  f, indent=2, ensure_ascii=False)
    print(f"JSON saved: {json_path}")

    return csv_path, json_path


async def main():
    import argparse
    parser = argparse.ArgumentParser(description='Fast rank RV listings')
    parser.add_argument('--zip', type=str, help='Single zip code')
    parser.add_argument('--type', type=str, help='Single RV type')
    parser.add_argument('--radius', type=int, default=DEFAULT_RADIUS)
    parser.add_argument('--condition', type=str, default=DEFAULT_CONDITION, choices=['N', 'U'])
    args = parser.parse_args()

    zip_codes = [args.zip] if args.zip else None
    rv_types = [args.type] if args.type else None

    listings = await run_extraction(zip_codes, rv_types, args.radius, args.condition)

    print(f"\n{'=' * 60}")
    print(f"TOTAL LISTINGS EXTRACTED: {len(listings)}")

    if listings:
        save_results(listings)
        print("\nSummary by type:")
        type_counts = {}
        for l in listings:
            t = l['search_type']
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")


if __name__ == "__main__":
    asyncio.run(main())
