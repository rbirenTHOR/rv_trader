"""
Fast combined scraper: API for engagement + Playwright for specs.
Parallel execution for maximum speed.

Usage:
    python src/fast_detail_scraper.py
    python src/fast_detail_scraper.py --limit 10
"""

import json
import sys
import asyncio
import aiohttp
import re
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

# API endpoints for engagement
URL_VIEWS = "https://www.rvtrader.com/gettiledata/addetail_listingstats/showadviewsstats?adId={ad_id}&realmId=%5Bobject%20Object%5D"
URL_SAVES = "https://www.rvtrader.com/gettiledata/addetail_listingstats/showsavedadsstats?adId={ad_id}&realmId=%5Bobject%20Object%5D"

COOKIE = "datadome=7_caNIdEfJrpV_byUEG8pMtjxiiLYy_Rw1dFy7gNKH6yKwM1Vm5aTAc8KNLfdHpE4aFe7XGaCo9ltwXxsEPgWKOf2AiGbxX4tr0aFeqCidYLxy_689eue7fuhbHfdX0V; zipCode=60618"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "cookie": COOKIE,
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


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
    """Extract specs and description from NUXT data."""
    result = {'specs': {}, 'description': None, 'description_length': 0}
    ad_details = None
    description = None

    for item in nuxt_data:
        if isinstance(item, dict):
            keys = set(item.keys())
            if 'sleepingCapacity' in keys or ('waterCapacity' in keys and 'slideouts' in keys):
                ad_details = resolve_nuxt_data(nuxt_data, item)
            if 'description' in keys and ('adId' in keys or 'dealerId' in keys):
                resolved = resolve_nuxt_data(nuxt_data, item)
                desc = resolved.get('description')
                if isinstance(desc, str) and len(desc) > 100:
                    description = desc

    if ad_details:
        spec_fields = [
            'sleepingCapacity', 'isBunkhouse', 'hasFloorplan', 'slideouts',
            'numAirConditioners', 'awnings', 'waterCapacity', 'levelingJacks',
            'selfContained', 'horsePower', 'fuelType', 'grossVehicleWeight',
            'axles', 'realAxles', 'suspension', 'driveTrain', 'engineSize',
            'engineType', 'engineManufacturer', 'transmissionMake',
            'transmissionSpeed', 'primaryColor', 'secondaryColor',
            'exteriorColor', 'interiorColor', 'length', 'mileage',
            'condition', 'year', 'sleepOption', 'propellerHours', 'hours'
        ]
        for field in spec_fields:
            val = ad_details.get(field)
            if val is not None and val != '' and str(val) != 'null':
                result['specs'][field] = val

    if description:
        description = re.sub(r'<[^>]+>', ' ', description)
        description = re.sub(r'\s+', ' ', description).strip()
        result['description'] = description
        result['description_length'] = len(description)

    return result


# ============== PHASE 1: Fast API calls for engagement ==============

async def fetch_engagement_batch(listings: list, concurrency: int = 20) -> dict:
    """Fetch views/saves for all listings via HTTP. Returns dict keyed by ad_id."""
    results = {}
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_one(session, ad_id):
        async with semaphore:
            data = {'views': None, 'saves': None}
            try:
                async with session.get(URL_VIEWS.format(ad_id=ad_id), headers=HEADERS) as resp:
                    if resp.status == 200:
                        j = await resp.json()
                        v = j.get('listingViewsData')
                        if v is not None:
                            data['views'] = int(v) if str(v).isdigit() else None

                async with session.get(URL_SAVES.format(ad_id=ad_id), headers=HEADERS) as resp:
                    if resp.status == 200:
                        j = await resp.json()
                        s = j.get('listingSavesData')
                        if s is not None:
                            data['saves'] = int(s) if str(s).lstrip('-').isdigit() else s
            except:
                pass
            return ad_id, data

    connector = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_one(session, str(l.get('id'))) for l in listings if l.get('id')]
        for ad_id, data in await asyncio.gather(*tasks):
            results[ad_id] = data

    return results


# ============== PHASE 2: Parallel Playwright for specs ==============

async def scrape_specs_parallel(listings: list, concurrency: int = 6) -> dict:
    """Scrape NUXT specs using parallel browser pages. Returns dict keyed by ad_id."""
    results = {}
    semaphore = asyncio.Semaphore(concurrency)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
        )

        async def scrape_one(listing, index, total):
            async with semaphore:
                ad_id = str(listing.get('id'))
                url = listing.get('listing_url')
                data = {'specs': {}, 'description_length': 0, 'success': False, 'error': None}

                if not url:
                    data['error'] = 'no_url'
                    return ad_id, data

                page = await context.new_page()
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                    await page.wait_for_timeout(1000)

                    nuxt_content = await page.evaluate('''() => {
                        const script = document.querySelector('script#__NUXT_DATA__');
                        return script ? script.textContent : null;
                    }''')

                    if nuxt_content:
                        nuxt_data = json.loads(nuxt_content)
                        extracted = extract_specs_from_nuxt(nuxt_data)
                        data['specs'] = extracted['specs']
                        data['description_length'] = extracted['description_length']
                        data['success'] = True
                    else:
                        data['error'] = 'no_nuxt'

                except Exception as e:
                    data['error'] = str(e)[:50]
                finally:
                    await page.close()

                status = 'OK' if data['success'] else f"FAIL:{data['error'][:20]}"
                specs_ct = len(data['specs'])
                print(f"  [{index+1}/{total}] {listing.get('make','?')[:12]} {listing.get('model','?')[:12]}: {status} ({specs_ct} specs)")
                return ad_id, data

        tasks = [scrape_one(l, i, len(listings)) for i, l in enumerate(listings)]
        for ad_id, data in await asyncio.gather(*tasks):
            results[ad_id] = data

        await browser.close()

    return results


# ============== MAIN: Combine both phases ==============

async def main():
    import time

    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    output_dir = Path('output')
    json_files = list(output_dir.glob('ranked_listings_*.json'))
    if not json_files:
        print("ERROR: No ranked_listings JSON files found")
        sys.exit(1)

    latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
    print(f"Source: {latest_file}")

    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    listings = data['listings'][:limit] if limit else data['listings']
    print(f"Processing {len(listings)} listings\n")

    # PHASE 1: API calls
    print("=" * 60)
    print("PHASE 1: Fetching engagement data via API (20 concurrent)...")
    t1 = time.time()
    engagement_data = await fetch_engagement_batch(listings, concurrency=20)
    t1_elapsed = time.time() - t1
    print(f"Done in {t1_elapsed:.1f}s - {sum(1 for v in engagement_data.values() if v['views'] is not None)} with views")

    # PHASE 2: Playwright
    print("\n" + "=" * 60)
    print("PHASE 2: Scraping specs via Playwright (6 concurrent pages)...")
    t2 = time.time()
    specs_data = await scrape_specs_parallel(listings, concurrency=6)
    t2_elapsed = time.time() - t2
    print(f"Done in {t2_elapsed:.1f}s - {sum(1 for v in specs_data.values() if v['success'])} successful")

    # MERGE results
    print("\n" + "=" * 60)
    print("Merging results...")
    results = []
    for listing in listings:
        ad_id = str(listing.get('id'))
        eng = engagement_data.get(ad_id, {})
        spec = specs_data.get(ad_id, {})

        row = {
            'id': ad_id,
            'rank': listing.get('rank'),
            'merch_score': listing.get('merch_score'),
            'relevance_score': listing.get('relevance_score'),
            'is_premium': listing.get('is_premium'),
            'is_top_premium': listing.get('is_top_premium'),
            'photo_count': listing.get('photo_count'),
            'has_floorplan': 1 if listing.get('floorplan_id') else 0,
            'has_price': 1 if listing.get('price') else 0,
            'price': listing.get('price'),
            'make': listing.get('make'),
            'model': listing.get('model'),
            'year': listing.get('year'),
            'listing_url': listing.get('listing_url'),
            # Engagement
            'views': eng.get('views'),
            'saves': eng.get('saves'),
            # Specs
            'description_length': spec.get('description_length', 0),
            'spec_success': spec.get('success', False),
        }
        # Add all spec fields
        for k, v in spec.get('specs', {}).items():
            row[f'spec_{k}'] = v

        results.append(row)

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f'full_detail_data_{timestamp}.json'

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'source_file': str(latest_file),
            'count': len(results),
            'phase1_time': t1_elapsed,
            'phase2_time': t2_elapsed,
            'total_time': t1_elapsed + t2_elapsed,
            'results': results
        }, f, indent=2)

    print(f"\nSaved: {output_file}")
    print(f"\nTOTAL TIME: {t1_elapsed + t2_elapsed:.1f}s")

    # Quick summary
    views_list = [r['views'] for r in results if r['views'] is not None]
    saves_list = [r['saves'] for r in results if r['saves'] is not None]
    if views_list:
        print(f"Views: min={min(views_list)}, max={max(views_list)}, avg={sum(views_list)/len(views_list):.0f}")
    if saves_list:
        print(f"Saves: min={min(saves_list)}, max={max(saves_list)}, avg={sum(saves_list)/len(saves_list):.1f}")


if __name__ == "__main__":
    asyncio.run(main())
