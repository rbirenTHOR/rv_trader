"""
Spec scraper for RVTrader listings using Playwright.
Extracts detailed specifications from listing detail pages.

Usage:
    python src/complete/spec_scraper.py                    # All Thor listings
    python src/complete/spec_scraper.py --limit 10         # Limit to 10 listings
    python src/complete/spec_scraper.py --thor-only        # Only Thor brands (default)
"""

import json
import sys
import re
import asyncio
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

# Thor brands for filtering
THOR_BRANDS = ['thor', 'jayco', 'airstream', 'tiffin', 'entegra', 'heartland', 'cruiser', 'keystone', 'dutchmen']

# Spec fields to extract
SPEC_FIELDS = [
    'sleepingCapacity', 'slideouts', 'numAirConditioners', 'awnings',
    'freshWaterCapacity', 'grayWaterCapacity', 'blackWaterCapacity', 'lpgCapacity',
    'horsePower', 'fuelType', 'grossVehicleWeight', 'length', 'mileage',
    'levelingJacks', 'selfContained', 'isBunkhouse', 'hasFloorplan',
    'interiorColor', 'exteriorColor', 'numAxles', 'hitchWeight',
    'cargoWeight', 'dryWeight', 'width', 'height'
]


def is_thor_brand(make: str) -> bool:
    """Check if make is a Thor brand."""
    if not make:
        return False
    make_lower = make.lower()
    return any(brand in make_lower for brand in THOR_BRANDS)


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


def extract_specs_from_nuxt(nuxt_data: list) -> dict:
    """Extract specs from NUXT data."""
    specs = {}

    for item in nuxt_data:
        if not isinstance(item, dict):
            continue

        # Look for the adDetails object with specs
        if 'sleepingCapacity' in item or 'slideouts' in item or 'grossVehicleWeight' in item:
            resolved = resolve_nuxt_data(nuxt_data, item)
            for field in SPEC_FIELDS:
                val = resolved.get(field)
                if val is not None and val != '' and str(val) != 'null':
                    specs[field] = val
            break

    return specs


async def scrape_listing(page, listing: dict) -> dict:
    """Scrape specs from a single listing."""
    result = {
        'id': str(listing.get('id')),
        'success': False,
        'error': None,
        'specs': {},
        'spec_count': 0
    }

    url = listing.get('listing_url')
    if not url:
        result['error'] = 'no_url'
        return result

    try:
        await page.goto(url, wait_until='networkidle', timeout=30000)

        # Wait for page to load
        await page.wait_for_timeout(1000)

        # Check for blocking
        content = await page.content()
        if 'geo.captcha-delivery' in content:
            result['error'] = 'blocked'
            return result

        # Extract NUXT_DATA
        match = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', content, re.DOTALL)
        if not match:
            result['error'] = 'no_nuxt_data'
            return result

        nuxt_data = json.loads(match.group(1))
        specs = extract_specs_from_nuxt(nuxt_data)

        result['success'] = True
        result['specs'] = specs
        result['spec_count'] = len(specs)

    except Exception as e:
        result['error'] = str(e)[:50]

    return result


async def main():
    # Parse arguments
    limit = None
    thor_only = True

    for i, arg in enumerate(sys.argv):
        if arg == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        if arg == '--all':
            thor_only = False

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

    listings = data['listings']

    # Filter to Thor brands if requested
    if thor_only:
        listings = [l for l in listings if is_thor_brand(l.get('make', ''))]
        print(f"Thor brand listings: {len(listings)}")

    if limit:
        listings = listings[:limit]

    print(f"Scraping {len(listings)} listings...")
    print("-" * 60)

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        for i, listing in enumerate(listings):
            result = await scrape_listing(page, listing)
            results.append(result)

            # Progress
            status = f"OK ({result['spec_count']} specs)" if result['success'] else f"FAIL:{result['error']}"
            make = (listing.get('make') or '?')[:10]
            model = (listing.get('model') or '?')[:15]
            print(f"  [{i+1}/{len(listings)}] {make} {model}: {status}")

            # Small delay
            await asyncio.sleep(0.5)

        await browser.close()

    # Merge results with original data
    spec_by_id = {r['id']: r for r in results}
    merged = []

    for listing in listings:
        ad_id = str(listing.get('id'))
        spec_result = spec_by_id.get(ad_id, {})

        merged.append({
            **listing,
            'specs': spec_result.get('specs', {}),
            'spec_count': spec_result.get('spec_count', 0),
            'spec_scrape_success': spec_result.get('success', False),
        })

    # Summary
    success = sum(1 for r in results if r['success'])
    total_specs = sum(r['spec_count'] for r in results)
    print("-" * 60)
    print(f"Success: {success}/{len(results)}")
    print(f"Total specs extracted: {total_specs}")

    # Spec field coverage
    print("\nSpec field coverage:")
    field_counts = {}
    for r in results:
        for field in r.get('specs', {}):
            field_counts[field] = field_counts.get(field, 0) + 1

    for field, count in sorted(field_counts.items(), key=lambda x: -x[1]):
        pct = count / len(results) * 100 if results else 0
        print(f"  {field}: {count}/{len(results)} ({pct:.0f}%)")

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f'specs_data_{timestamp}.json'

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'source_file': str(latest_file),
            'count': len(merged),
            'success_count': success,
            'total_specs': total_specs,
            'listings': merged
        }, f, indent=2, ensure_ascii=False)

    print(f"\nSaved: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
