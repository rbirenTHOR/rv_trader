"""
Fast engagement stats scraper using direct API endpoints.
Fetches views and saves data for all listings via HTTP (no browser needed).

Usage:
    python src/engagement_scraper.py
    python src/engagement_scraper.py --limit 10
"""

import json
import sys
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime

# API endpoints
URL_VIEWS = "https://www.rvtrader.com/gettiledata/addetail_listingstats/showadviewsstats?adId={ad_id}&realmId=%5Bobject%20Object%5D"
URL_SAVES = "https://www.rvtrader.com/gettiledata/addetail_listingstats/showsavedadsstats?adId={ad_id}&realmId=%5Bobject%20Object%5D"

# Cookie required for API access (datadome is the key part)
COOKIE = "ti_traffic_split=730282330:1:marketplace-rec.tilabs.io:443; _sharedID=37ca3693-d3f5-4eab-9ee6-495cb6f36a8c; datadome=jGln3Q9fAU_olh5veqk677xwiLz8D~cWzkuWIxLk~zPRycf6zOGpEo34N7g9np66rE8dcurbaRZgEZtByzPhOLFF4td8r~IphZo4t~YwpGGpzkEKbSqZlGiE7TWyvqFW; zipCode=60618"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "cookie": COOKIE,
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
}


async def fetch_engagement(session: aiohttp.ClientSession, ad_id: str, listing: dict) -> dict:
    """Fetch views and saves for a single listing."""
    result = {
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
        'views': None,
        'saves': None,
        'days_listed': None,
        'fetch_success': False,
        'fetch_error': None
    }

    try:
        # Fetch views - response: {"error":null,"listingViewsData":"138"}
        async with session.get(URL_VIEWS.format(ad_id=ad_id), headers=HEADERS) as resp:
            if resp.status == 200:
                data = await resp.json()
                views_val = data.get('listingViewsData')
                if views_val is not None:
                    result['views'] = int(views_val) if str(views_val).isdigit() else None

        # Fetch saves - response: {"error":null,"listingSavesData":1}
        async with session.get(URL_SAVES.format(ad_id=ad_id), headers=HEADERS) as resp:
            if resp.status == 200:
                data = await resp.json()
                saves_val = data.get('listingSavesData')
                if saves_val is not None:
                    result['saves'] = int(saves_val) if str(saves_val).lstrip('-').isdigit() else saves_val

        result['fetch_success'] = True

    except Exception as e:
        result['fetch_error'] = str(e)[:100]

    return result


async def scrape_all(listings: list, concurrency: int = 10) -> list:
    """Scrape engagement data for all listings with concurrency limit."""
    results = []
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_with_semaphore(session, ad_id, listing, index, total):
        async with semaphore:
            result = await fetch_engagement(session, ad_id, listing)
            status = "OK" if result['fetch_success'] else f"FAIL: {result.get('fetch_error', '?')[:30]}"
            print(f"  [{index+1}/{total}] {listing.get('make', '?')[:15]} {listing.get('model', '?')[:15]}: {status} (views={result.get('views')}, saves={result.get('saves')})")
            return result

    connector = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for i, listing in enumerate(listings):
            ad_id = str(listing.get('id'))
            if ad_id:
                tasks.append(fetch_with_semaphore(session, ad_id, listing, i, len(listings)))

        results = await asyncio.gather(*tasks)

    return results


async def main():
    # Parse arguments
    limit = None
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

    listings = data['listings']
    if limit:
        listings = listings[:limit]

    print(f"Fetching engagement data for {len(listings)} listings...")
    print("-" * 70)

    # Run scraper
    results = await scrape_all(listings)

    # Summary
    success_count = sum(1 for r in results if r['fetch_success'])
    views_count = sum(1 for r in results if r.get('views') is not None)
    saves_count = sum(1 for r in results if r.get('saves') is not None)

    print("-" * 70)
    print(f"Success: {success_count}/{len(results)}")
    print(f"With views data: {views_count}/{len(results)}")
    print(f"With saves data: {saves_count}/{len(results)}")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f'engagement_stats_{timestamp}.json'

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'source_file': str(latest_file),
            'count': len(results),
            'success_count': success_count,
            'results': results
        }, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to: {output_file}")

    # Quick stats
    if views_count > 0:
        views_list = [r['views'] for r in results if r.get('views') is not None]
        print(f"\nViews stats: min={min(views_list)}, max={max(views_list)}, avg={sum(views_list)/len(views_list):.1f}")

    if saves_count > 0:
        saves_list = [r['saves'] for r in results if r.get('saves') is not None]
        print(f"Saves stats: min={min(saves_list)}, max={max(saves_list)}, avg={sum(saves_list)/len(saves_list):.1f}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
