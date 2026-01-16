"""
Efficient detail page spec scraper for RVTrader listings.
Extracts ALL spec fields from detail pages to analyze correlation with scores.

Usage:
    python src/spec_scraper.py
    python src/spec_scraper.py --limit 50
"""

import json
import sys
import asyncio
import aiohttp
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

# ScraperAPI key (same as rank_listings.py)
SCRAPER_API_KEY = "ca5e06e617ff7b8869dc378d591511d4"
SCRAPER_API_URL = "http://api.scraperapi.com"

# Concurrency settings
MAX_CONCURRENT = 5  # Lower for detail pages to avoid rate limits
TIMEOUT = 45


def resolve_nuxt_data(data: list, val, depth: int = 0):
    """Recursively resolve Nuxt's reference-based data format."""
    if depth > 25:
        return val

    if isinstance(val, int) and 0 <= val < len(data):
        return resolve_nuxt_data(data, data[val], depth + 1)

    if isinstance(val, list):
        return [resolve_nuxt_data(data, v, depth + 1) for v in val]

    if isinstance(val, dict):
        resolved = {}
        for k, v in val.items():
            resolved[k] = resolve_nuxt_data(data, v, depth + 1)
        return resolved

    return val


def extract_specs_from_html(html: str) -> dict:
    """Extract all spec fields from detail page HTML."""

    result = {
        'success': False,
        'specs': {},
        'description': None,
        'description_length': 0,
        'error': None
    }

    # Find NUXT_DATA script
    pattern = r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)

    if not match:
        result['error'] = 'No NUXT_DATA found'
        return result

    try:
        nuxt_content = match.group(1)
        nuxt_data = json.loads(nuxt_content)

        # Find the adDetails object (vehicleSpecs) - usually around index 149
        # and the details object (displaySpecs) - usually around index 107
        ad_details = None
        display_details = None
        description = None

        for i, item in enumerate(nuxt_data):
            if isinstance(item, dict):
                keys = set(item.keys())

                # adDetails has these specific keys
                if 'sleepingCapacity' in keys or 'waterCapacity' in keys or 'slideouts' in keys:
                    ad_details = resolve_nuxt_data(nuxt_data, item)

                # displaySpecs has title-case keys like "Sleeping Capacity"
                if 'Sleeping Capacity' in keys or 'Water Capacity' in keys:
                    display_details = resolve_nuxt_data(nuxt_data, item)

                # Main listing object has description
                if 'description' in keys and 'adId' in keys:
                    resolved = resolve_nuxt_data(nuxt_data, item)
                    if isinstance(resolved.get('description'), str):
                        description = resolved['description']

                # Alternative: find description in listing data
                if 'description' in keys and 'dealerId' in keys:
                    resolved = resolve_nuxt_data(nuxt_data, item)
                    desc = resolved.get('description')
                    if isinstance(desc, str) and len(desc) > 100:
                        description = desc

        # Extract all spec fields from adDetails
        specs = {}
        if ad_details:
            spec_fields = [
                'sleepingCapacity', 'isBunkhouse', 'hasFloorplan', 'slideouts',
                'numAirConditioners', 'awnings', 'waterCapacity', 'levelingJacks',
                'selfContained', 'horsePower', 'fuelType', 'grossVehicleWeight',
                'axles', 'realAxles', 'suspension', 'driveTrain', 'engineSize',
                'engineType', 'engineManufacturer', 'transmissionMake',
                'transmissionSpeed', 'primaryColor', 'secondaryColor',
                'exteriorColor', 'interiorColor', 'length', 'mileage',
                'condition', 'year', 'sleepOption', 'propellerHours',
                'airframeTime', 'hours'
            ]

            for field in spec_fields:
                val = ad_details.get(field)
                if val is not None and val != '' and val != 'null':
                    specs[field] = val

        # Also extract from display details if available
        if display_details:
            for key, val in display_details.items():
                if val is not None and val != '' and val != 'null':
                    # Convert to snake_case
                    snake_key = key.lower().replace(' ', '_')
                    if snake_key not in specs:
                        specs[f'display_{snake_key}'] = val

        # Clean description HTML
        if description:
            description = re.sub(r'<[^>]+>', ' ', description)
            description = re.sub(r'\s+', ' ', description).strip()

        result['success'] = True
        result['specs'] = specs
        result['description'] = description
        result['description_length'] = len(description) if description else 0

    except Exception as e:
        result['error'] = str(e)

    return result


async def fetch_detail_page(session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore) -> dict:
    """Fetch a single detail page via ScraperAPI."""

    async with semaphore:
        result = {
            'url': url,
            'success': False,
            'specs': {},
            'description_length': 0,
            'error': None
        }

        try:
            # Build ScraperAPI URL
            api_url = f"{SCRAPER_API_URL}?api_key={SCRAPER_API_KEY}&url={quote(url, safe='')}"

            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as response:
                if response.status == 200:
                    html = await response.text()
                    extracted = extract_specs_from_html(html)

                    result['success'] = extracted['success']
                    result['specs'] = extracted['specs']
                    result['description'] = extracted.get('description')
                    result['description_length'] = extracted['description_length']
                    result['error'] = extracted.get('error')
                else:
                    result['error'] = f'HTTP {response.status}'

        except asyncio.TimeoutError:
            result['error'] = 'Timeout'
        except Exception as e:
            result['error'] = str(e)

        return result


async def scrape_all_details(listings: list, max_concurrent: int = MAX_CONCURRENT) -> list:
    """Scrape detail pages for all listings."""

    semaphore = asyncio.Semaphore(max_concurrent)

    connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=max_concurrent)
    async with aiohttp.ClientSession(connector=connector) as session:

        tasks = []
        for listing in listings:
            url = listing.get('listing_url')
            if url:
                task = fetch_detail_page(session, url, semaphore)
                tasks.append((listing, task))

        results = []
        total = len(tasks)

        for i, (listing, task) in enumerate(tasks):
            detail = await task

            # Merge listing data with detail specs
            combined = {
                'id': listing.get('id'),
                'rank': listing.get('rank'),
                'merch_score': listing.get('merch_score'),
                'relevance_score': listing.get('relevance_score'),
                'is_premium': listing.get('is_premium'),
                'is_top_premium': listing.get('is_top_premium'),
                'photo_count': listing.get('photo_count'),
                'has_floorplan': 1 if listing.get('floorplan_id') else 0,
                'has_price': 1 if listing.get('price') else 0,
                'has_vin': 1 if listing.get('vin') else 0,
                'has_length_search': 1 if listing.get('length') else 0,
                'price': listing.get('price'),
                'make': listing.get('make'),
                'model': listing.get('model'),
                'year': listing.get('year'),
                'listing_url': listing.get('listing_url'),

                # Detail page data
                'detail_success': detail['success'],
                'detail_error': detail.get('error'),
                'description_length': detail['description_length'],
                **{f'spec_{k}': v for k, v in detail['specs'].items()}
            }

            results.append(combined)

            status = 'OK' if detail['success'] else f"FAIL: {detail.get('error', 'unknown')[:30]}"
            print(f"  [{i+1}/{total}] {listing.get('make', '?')} {listing.get('model', '?')[:20]}: {status}")

            # Small delay between requests
            await asyncio.sleep(0.5)

        return results


async def main():
    # Parse arguments
    limit = 56  # Default to all
    for i, arg in enumerate(sys.argv):
        if arg == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    # Find most recent ranked_listings file
    output_dir = Path('output')
    json_files = list(output_dir.glob('ranked_listings_*.json'))

    if not json_files:
        print("ERROR: No ranked_listings JSON files found in output/")
        sys.exit(1)

    latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
    print(f"Loading listings from: {latest_file}")

    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    listings = data['listings'][:limit]
    print(f"Scraping {len(listings)} detail pages...")
    print("-" * 60)

    # Run scraper
    results = await scrape_all_details(listings)

    # Summary
    success_count = sum(1 for r in results if r['detail_success'])
    print("-" * 60)
    print(f"Success: {success_count}/{len(results)}")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f'detail_specs_{timestamp}.json'

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'source_file': str(latest_file),
            'count': len(results),
            'success_count': success_count,
            'results': results
        }, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to: {output_file}")

    # Quick stats on specs found
    all_spec_keys = set()
    for r in results:
        for k in r.keys():
            if k.startswith('spec_'):
                all_spec_keys.add(k)

    print(f"\nSpec fields found: {len(all_spec_keys)}")
    for key in sorted(all_spec_keys):
        count = sum(1 for r in results if r.get(key) is not None)
        print(f"  {key}: {count}/{len(results)} listings")

    return results


if __name__ == "__main__":
    asyncio.run(main())
