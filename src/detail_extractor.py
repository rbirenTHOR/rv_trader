"""
Detail page extractor for RVTrader listings.
Extracts full listing data including complete description from individual listing pages.

Usage:
    python src/detail_extractor.py <listing_url>
    python src/detail_extractor.py "https://www.rvtrader.com/listing/2026-Coachmen-NOVA+20D-5038356664"
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
    if depth > 20:
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


def find_listing_data(nuxt_data: list) -> dict:
    """Find and resolve the main listing object from NUXT_DATA."""

    # Look for the listing object - it typically has 'adId' or 'vehicle' or 'listing' key
    for i, item in enumerate(nuxt_data):
        if isinstance(item, dict):
            # Detail page listing object patterns
            if 'adId' in item and 'vehicle' in item:
                return resolve_nuxt_data(nuxt_data, item)
            if 'listing' in item and isinstance(item.get('listing'), (dict, int)):
                resolved = resolve_nuxt_data(nuxt_data, item)
                if isinstance(resolved.get('listing'), dict):
                    return resolved['listing']
                return resolved

    # Fallback: find object with description field
    for i, item in enumerate(nuxt_data):
        if isinstance(item, dict) and 'description' in item:
            resolved = resolve_nuxt_data(nuxt_data, item)
            if isinstance(resolved.get('description'), str) and len(resolved['description']) > 100:
                return resolved

    return {}


def extract_listing_fields(data: dict) -> dict:
    """Extract relevant fields from the resolved listing data."""

    # Helper to get nested values
    def get(obj, *keys, default=None):
        for key in keys:
            if isinstance(obj, dict):
                obj = obj.get(key, default)
            else:
                return default
        return obj if obj is not None else default

    vehicle = data.get('vehicle', {})
    listing = data.get('listing', data)

    # Try to find description in various places
    description = None
    for loc in [listing, vehicle, data]:
        if isinstance(loc, dict):
            desc = loc.get('description') or loc.get('sellerDescription') or loc.get('fullDescription')
            if desc and isinstance(desc, str) and len(desc) > 50:
                description = desc
                break

    # Clean HTML from description
    if description:
        description = re.sub(r'<[^>]+>', ' ', description)
        description = re.sub(r'\s+', ' ', description).strip()

    return {
        # IDs
        'id': get(listing, 'adId') or get(data, 'adId') or get(listing, 'id'),
        'dealer_id': get(vehicle, 'dealerId') or get(listing, 'dealerId'),

        # Vehicle info
        'year': get(vehicle, 'year') or get(listing, 'year'),
        'make': get(vehicle, 'makeName') or get(listing, 'makeName'),
        'model': get(vehicle, 'modelName') or get(listing, 'modelName'),
        'trim': get(vehicle, 'trimName') or get(listing, 'trimName'),
        'class': get(vehicle, 'className') or get(listing, 'className'),
        'condition': get(vehicle, 'condition') or get(listing, 'condition'),

        # Full description
        'description': description,
        'description_length': len(description) if description else 0,

        # Specs
        'price': get(vehicle, 'price') or get(listing, 'price'),
        'msrp': get(listing, 'msrp'),
        'length': get(listing, 'length') or get(vehicle, 'length'),
        'mileage': get(listing, 'mileage'),
        'vin': get(listing, 'mfrSerialNum') or get(listing, 'vin'),

        # Location
        'city': get(vehicle, 'city') or get(listing, 'city'),
        'state': get(vehicle, 'stateCode') or get(listing, 'stateCode'),
        'zip_code': get(listing, 'zipCode'),

        # Dealer
        'dealer_name': get(listing, 'companyName') or get(vehicle, 'companyName'),

        # Media
        'photo_count': len(get(vehicle, 'photoIds', default=[])) if get(vehicle, 'photoIds') else get(listing, 'photoCount', default=0),
        'floorplan_id': get(vehicle, 'floorplanMediaid') or get(listing, 'floorplanMediaid'),

        # Status
        'is_premium': get(listing, 'isPremium'),
        'is_top_premium': get(listing, 'isToppremium'),

        # Raw data for debugging
        '_raw_keys': list(data.keys()) if isinstance(data, dict) else [],
    }


async def extract_detail_page(url: str, headless: bool = True) -> dict:
    """Extract full listing data from a detail page URL."""

    result = {
        'success': False,
        'url': url,
        'listing': None,
        'error': None,
        'timestamp': datetime.now().isoformat()
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()

            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)

            # Get NUXT data
            nuxt_content = await page.evaluate('''() => {
                const script = document.querySelector('script#__NUXT_DATA__');
                return script ? script.textContent : null;
            }''')

            if not nuxt_content:
                # Try alternative: look for __NUXT__ window object
                nuxt_content = await page.evaluate('''() => {
                    if (window.__NUXT__ && window.__NUXT__.data) {
                        return JSON.stringify(window.__NUXT__.data);
                    }
                    return null;
                }''')

            await browser.close()

            if nuxt_content:
                nuxt_data = json.loads(nuxt_content)
                listing_data = find_listing_data(nuxt_data)

                if listing_data:
                    result['listing'] = extract_listing_fields(listing_data)
                    result['success'] = True
                else:
                    result['error'] = 'Could not find listing data in NUXT'
            else:
                result['error'] = 'No NUXT data found on page'

    except Exception as e:
        result['error'] = str(e)

    return result


async def extract_multiple_details(urls: list, headless: bool = True) -> list:
    """Extract data from multiple detail pages."""
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        for url in urls:
            result = {
                'success': False,
                'url': url,
                'listing': None,
                'error': None,
            }

            try:
                page = await context.new_page()
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(1500)

                nuxt_content = await page.evaluate('''() => {
                    const script = document.querySelector('script#__NUXT_DATA__');
                    return script ? script.textContent : null;
                }''')

                await page.close()

                if nuxt_content:
                    nuxt_data = json.loads(nuxt_content)
                    listing_data = find_listing_data(nuxt_data)

                    if listing_data:
                        result['listing'] = extract_listing_fields(listing_data)
                        result['success'] = True
                    else:
                        result['error'] = 'No listing data found'
                else:
                    result['error'] = 'No NUXT data'

            except Exception as e:
                result['error'] = str(e)

            results.append(result)
            print(f"  Extracted: {url.split('/')[-1][:40]}... {'OK' if result['success'] else 'FAIL'}")

        await browser.close()

    return results


async def main():
    if len(sys.argv) < 2:
        print("Usage: python src/detail_extractor.py <listing_url>")
        print("       python src/detail_extractor.py --from-json <ranked_listings.json>")
        sys.exit(1)

    if sys.argv[1] == '--from-json' and len(sys.argv) > 2:
        # Extract details for listings from a ranked_listings JSON file
        json_path = sys.argv[2]
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Get URLs from listings
        urls = [l['listing_url'] for l in data['listings'] if l.get('listing_url')]

        # Limit to first N for testing
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        urls = urls[:limit]

        print(f"Extracting details for {len(urls)} listings...")
        results = await extract_multiple_details(urls)

        # Save results
        output_path = Path('output') / f'detail_extracts_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({'count': len(results), 'results': results}, f, indent=2)
        print(f"\nSaved to: {output_path}")

        # Summary
        success = sum(1 for r in results if r['success'])
        print(f"\nSuccess: {success}/{len(results)}")

        # Show description lengths
        print("\nDescription lengths:")
        for r in results:
            if r['success'] and r['listing']:
                l = r['listing']
                print(f"  {l.get('make','')} {l.get('model','')}: {l.get('description_length', 0)} chars")

    else:
        # Single URL extraction
        url = sys.argv[1]
        print(f"Extracting: {url}")

        result = await extract_detail_page(url)

        if result['success']:
            print("\nSUCCESS!")
            l = result['listing']
            print(f"  ID: {l.get('id')}")
            print(f"  Make/Model: {l.get('make')} {l.get('model')}")
            print(f"  Price: {l.get('price')}")
            print(f"  Description length: {l.get('description_length')} chars")
            print(f"\n  Description preview:")
            desc = l.get('description', '')
            print(f"  {desc[:500]}..." if len(desc) > 500 else f"  {desc}")
        else:
            print(f"\nFAILED: {result['error']}")

        # Save to file
        output_path = Path('output') / 'detail_extract.json'
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        print(f"\nFull data saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
