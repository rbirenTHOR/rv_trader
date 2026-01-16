"""
Efficient detail page spec scraper using Playwright.
Extracts ALL spec fields from detail pages to analyze correlation with scores.

Usage:
    python src/spec_scraper_playwright.py
    python src/spec_scraper_playwright.py --limit 50
"""

import json
import sys
import asyncio
import re
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


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


def extract_specs_from_nuxt(nuxt_data: list) -> dict:
    """Extract all spec fields from NUXT data."""

    result = {
        'specs': {},
        'description': None,
        'description_length': 0
    }

    ad_details = None
    display_details = None
    description = None

    for i, item in enumerate(nuxt_data):
        if isinstance(item, dict):
            keys = set(item.keys())

            # adDetails has these specific keys (vehicleSpecs)
            if 'sleepingCapacity' in keys or ('waterCapacity' in keys and 'slideouts' in keys):
                ad_details = resolve_nuxt_data(nuxt_data, item)

            # displaySpecs has title-case keys
            if 'Sleeping Capacity' in keys or 'Water Capacity' in keys:
                display_details = resolve_nuxt_data(nuxt_data, item)

            # Main listing object has description
            if 'description' in keys and ('adId' in keys or 'dealerId' in keys):
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
            if val is not None and val != '' and str(val) != 'null':
                specs[field] = val

    # Also extract from display details
    if display_details:
        for key, val in display_details.items():
            if val is not None and val != '' and str(val) != 'null':
                snake_key = 'display_' + key.lower().replace(' ', '_')
                if snake_key not in specs:
                    specs[snake_key] = val

    # Clean description HTML
    if description:
        description = re.sub(r'<[^>]+>', ' ', description)
        description = re.sub(r'\s+', ' ', description).strip()

    result['specs'] = specs
    result['description'] = description
    result['description_length'] = len(description) if description else 0

    return result


async def scrape_listings(listings: list) -> list:
    """Scrape detail pages for all listings using Playwright."""

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        total = len(listings)

        for i, listing in enumerate(listings):
            url = listing.get('listing_url')
            if not url:
                continue

            result = {
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
                'listing_url': url,
                'detail_success': False,
                'detail_error': None,
                'description_length': 0
            }

            try:
                page = await context.new_page()
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(1500)  # Let page hydrate

                # Extract NUXT data
                nuxt_content = await page.evaluate('''() => {
                    const script = document.querySelector('script#__NUXT_DATA__');
                    return script ? script.textContent : null;
                }''')

                await page.close()

                if nuxt_content:
                    nuxt_data = json.loads(nuxt_content)
                    extracted = extract_specs_from_nuxt(nuxt_data)

                    result['detail_success'] = True
                    result['description_length'] = extracted['description_length']

                    # Add all spec fields with prefix
                    for k, v in extracted['specs'].items():
                        result[f'spec_{k}'] = v
                else:
                    result['detail_error'] = 'No NUXT_DATA'

            except Exception as e:
                result['detail_error'] = str(e)[:50]

            results.append(result)

            status = 'OK' if result['detail_success'] else f"FAIL: {result.get('detail_error', '?')[:25]}"
            specs_count = sum(1 for k in result.keys() if k.startswith('spec_'))
            print(f"  [{i+1}/{total}] {listing.get('make', '?')[:15]} {listing.get('model', '?')[:15]}: {status} ({specs_count} specs)")

            # Small delay
            await asyncio.sleep(0.3)

        await browser.close()

    return results


async def main():
    # Parse arguments
    limit = 56
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
    print(f"Scraping {len(listings)} detail pages with Playwright...")
    print("-" * 70)

    # Run scraper
    results = await scrape_listings(listings)

    # Summary
    success_count = sum(1 for r in results if r['detail_success'])
    print("-" * 70)
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

    # Stats on specs found
    all_spec_keys = set()
    for r in results:
        for k in r.keys():
            if k.startswith('spec_'):
                all_spec_keys.add(k)

    print(f"\nSpec fields found: {len(all_spec_keys)}")
    for key in sorted(all_spec_keys):
        count = sum(1 for r in results if r.get(key) is not None)
        pct = count / len(results) * 100
        print(f"  {key:35} {count:3}/{len(results)} ({pct:5.1f}%)")

    return results


if __name__ == "__main__":
    asyncio.run(main())
