"""
Detail page scraper for RVTrader listings.
Extracts description and specs from individual listing pages.

Uses sequential HTTP requests with cookies to avoid rate limiting.

Usage:
    python src/description_scraper.py                    # All listings from latest ranked_listings
    python src/description_scraper.py --limit 20         # Limit to 20 listings
    python src/description_scraper.py --delay 0.5        # 0.5s delay between requests (default: 0.3)
"""

import json
import sys
import re
import time
import requests
from pathlib import Path
from datetime import datetime

COOKIE_CACHE_FILE = Path(__file__).parent.parent / ".cookie_cache.json"
DEFAULT_DELAY = 0.3


def load_cookie_string() -> str | None:
    """Load cookie string from cache file."""
    if not COOKIE_CACHE_FILE.exists():
        return None
    try:
        with open(COOKIE_CACHE_FILE, 'r') as f:
            data = json.load(f)
        return data.get('cookie_string')
    except (json.JSONDecodeError, KeyError):
        return None


def get_headers(cookie_string: str = None) -> dict:
    """Build headers with cookie string."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    if cookie_string:
        headers['Cookie'] = cookie_string
    return headers


def resolve_nuxt_data(data: list, val, depth: int = 0):
    """Recursively resolve Nuxt's reference-based data format."""
    if depth > 25:
        return val
    if isinstance(val, int) and 0 <= val < len(data):
        return resolve_nuxt_data(data, data[val], depth + 1)
    if isinstance(val, list):
        return [resolve_nuxt_data(data, v, depth + 1) for v in val]
    if isinstance(val, dict):
        return {k: resolve_nuxt_data(data, v, depth + 1) for k, v in val.items()}
    return val


def extract_detail_data(nuxt_data: list) -> dict:
    """Extract description and specs from NUXT data."""
    result = {
        'description': None,
        'description_length': 0,
        'specs': {},
    }

    ad_details = None
    description = None

    for item in nuxt_data:
        if not isinstance(item, dict):
            continue

        keys = set(item.keys())

        # adDetails object (has vehicle specs)
        if 'sleepingCapacity' in keys or ('waterCapacity' in keys and 'slideouts' in keys):
            ad_details = resolve_nuxt_data(nuxt_data, item)

        # Main listing object with description
        if 'description' in keys and ('adId' in keys or 'dealerId' in keys):
            resolved = resolve_nuxt_data(nuxt_data, item)
            desc = resolved.get('description')
            if isinstance(desc, str) and len(desc) > 50:
                description = desc

    # Extract specs
    if ad_details:
        spec_fields = [
            'sleepingCapacity', 'isBunkhouse', 'hasFloorplan', 'slideouts',
            'numAirConditioners', 'awnings', 'waterCapacity', 'levelingJacks',
            'selfContained', 'horsePower', 'fuelType', 'grossVehicleWeight',
            'length', 'mileage', 'condition', 'year', 'freshWaterCapacity',
            'grayWaterCapacity', 'blackWaterCapacity', 'lpgCapacity',
        ]
        for field in spec_fields:
            val = ad_details.get(field)
            if val is not None and val != '' and str(val) != 'null':
                result['specs'][field] = val

    # Clean description HTML
    if description:
        description = re.sub(r'<[^>]+>', ' ', description)
        description = re.sub(r'\s+', ' ', description).strip()
        result['description'] = description
        result['description_length'] = len(description)

    return result


def fetch_detail(listing: dict, headers: dict) -> dict:
    """Fetch a single detail page and extract data."""
    ad_id = str(listing.get('id'))
    url = listing.get('listing_url')

    result = {
        'id': ad_id,
        'success': False,
        'error': None,
        'description': None,
        'description_length': 0,
        'specs': {},
    }

    if not url:
        result['error'] = 'no_url'
        return result

    try:
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            result['error'] = f'http_{response.status_code}'
            return result

        html = response.text

        # Check for DataDome blocking (captcha page)
        if 'geo.captcha-delivery' in html:
            result['error'] = 'blocked'
            return result

        # Extract NUXT_DATA
        match = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not match:
            result['error'] = 'no_nuxt_data'
            return result

        nuxt_data = json.loads(match.group(1))
        extracted = extract_detail_data(nuxt_data)

        result['success'] = True
        result['description'] = extracted['description']
        result['description_length'] = extracted['description_length']
        result['specs'] = extracted['specs']

    except requests.Timeout:
        result['error'] = 'timeout'
    except Exception as e:
        result['error'] = str(e)[:50]

    return result


def main():
    # Parse arguments
    limit = None
    delay = DEFAULT_DELAY

    for i, arg in enumerate(sys.argv):
        if arg == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        if arg == '--delay' and i + 1 < len(sys.argv):
            delay = float(sys.argv[i + 1])

    # Find most recent ranked_listings file
    output_dir = Path('output')
    json_files = list(output_dir.glob('ranked_listings_*.json'))

    if not json_files:
        print("ERROR: No ranked_listings JSON files found in output/")
        sys.exit(1)

    latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
    print(f"Source: {latest_file}")

    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    listings = data['listings'][:limit] if limit else data['listings']

    # Load cookies
    cookie_string = load_cookie_string()
    if not cookie_string or 'datadome' not in cookie_string:
        print("ERROR: No valid cookies. Run: python src/complete/engagement_scraper.py --refresh-cookies")
        sys.exit(1)

    print(f"Cookies loaded (datadome present)")
    headers = get_headers(cookie_string)

    print(f"Scraping {len(listings)} listings (delay: {delay}s)...")
    print("-" * 60)

    # Sequential scraping (no session - session interferes with cookies)
    results = []
    start_time = time.time()

    for i, listing in enumerate(listings):
        result = fetch_detail(listing, headers)
        results.append(result)

        # Progress
        status = 'OK' if result['success'] else f"FAIL:{result['error']}"
        desc_len = result['description_length']
        print(f"  [{i+1}/{len(listings)}] {listing.get('make','?')[:10]} {listing.get('model','?')[:12]}: {status} (desc:{desc_len})")

        # Delay between requests
        if i < len(listings) - 1:
            time.sleep(delay)

    elapsed = time.time() - start_time

    # Merge results
    detail_by_id = {r['id']: r for r in results}
    merged = []

    for listing in listings:
        ad_id = str(listing.get('id'))
        detail = detail_by_id.get(ad_id, {})

        merged.append({
            'id': ad_id,
            'rank': listing.get('rank'),
            'make': listing.get('make'),
            'model': listing.get('model'),
            'year': listing.get('year'),
            'price': listing.get('price'),
            'merch_score': listing.get('merch_score'),
            'relevance_score': listing.get('relevance_score'),
            'is_premium': listing.get('is_premium'),
            'listing_url': listing.get('listing_url'),
            'detail_success': detail.get('success', False),
            'description': detail.get('description'),
            'description_length': detail.get('description_length', 0),
            'specs': detail.get('specs', {}),
        })

    # Summary
    success = sum(1 for r in results if r['success'])
    print("-" * 60)
    print(f"Success: {success}/{len(results)}")
    print(f"Time: {elapsed:.1f}s ({elapsed/len(listings):.2f}s per listing)")

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f'detail_data_{timestamp}.json'

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'source_file': str(latest_file),
            'count': len(merged),
            'success_count': success,
            'elapsed_seconds': elapsed,
            'results': merged
        }, f, indent=2, ensure_ascii=False)

    print(f"\nSaved: {output_file}")

    # Stats
    desc_lengths = [r['description_length'] for r in merged if r['description_length'] > 0]
    if desc_lengths:
        print(f"Description lengths: min={min(desc_lengths)}, max={max(desc_lengths)}, avg={sum(desc_lengths)//len(desc_lengths)}")


if __name__ == "__main__":
    main()
