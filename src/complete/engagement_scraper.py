"""
Fast engagement stats scraper using direct API endpoints.
Fetches views and saves data for all listings via HTTP.

Cookies are stored in .cookie_cache.json and refreshed via browser every 48 hours.

Usage:
    python src/engagement_scraper.py
    python src/engagement_scraper.py --limit 10
    python src/engagement_scraper.py --refresh-cookies  # Force cookie refresh
"""

import json
import sys
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime, timedelta

# API endpoints
URL_VIEWS = "https://www.rvtrader.com/gettiledata/addetail_listingstats/showadviewsstats?adId={ad_id}&realmId=%5Bobject%20Object%5D"
URL_SAVES = "https://www.rvtrader.com/gettiledata/addetail_listingstats/showsavedadsstats?adId={ad_id}&realmId=%5Bobject%20Object%5D"

# Cookie cache file and expiry
COOKIE_CACHE_FILE = Path(__file__).parent.parent / ".cookie_cache.json"
COOKIE_EXPIRY_HOURS = 48


def get_headers(cookie_string: str) -> dict:
    """Build headers with the given cookie string."""
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "cookie": cookie_string,
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    }


def load_cached_cookies() -> tuple[str | None, datetime | None]:
    """Load cookies from cache file. Returns (cookie_string, timestamp) or (None, None)."""
    if not COOKIE_CACHE_FILE.exists():
        return None, None

    try:
        with open(COOKIE_CACHE_FILE, 'r') as f:
            data = json.load(f)
        timestamp = datetime.fromisoformat(data['timestamp'])
        return data['cookie_string'], timestamp
    except (json.JSONDecodeError, KeyError, ValueError):
        return None, None


def save_cookies_to_cache(cookie_string: str):
    """Save cookies to cache file with current timestamp."""
    with open(COOKIE_CACHE_FILE, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'cookie_string': cookie_string
        }, f, indent=2)
    print(f"Cookies saved to {COOKIE_CACHE_FILE}")


def cookies_are_valid() -> bool:
    """Check if cached cookies exist and are less than 48 hours old."""
    cookie_string, timestamp = load_cached_cookies()
    if cookie_string is None or timestamp is None:
        return False

    age = datetime.now() - timestamp
    if age > timedelta(hours=COOKIE_EXPIRY_HOURS):
        print(f"Cookies are {age.total_seconds() / 3600:.1f} hours old (max {COOKIE_EXPIRY_HOURS}h)")
        return False

    return True


async def refresh_cookies_via_browser() -> str:
    """Open browser, let user visit RVTrader, then capture cookies."""
    from playwright.async_api import async_playwright

    print("\n" + "=" * 70)
    print("COOKIE REFRESH REQUIRED")
    print("=" * 70)
    print("A browser will open. Please:")
    print("  1. Wait for RVTrader.com to fully load")
    print("  2. Browse around briefly (view a listing or two)")
    print("  3. Navigate to: rvtrader.com/done (type in address bar)")
    print("=" * 70 + "\n")

    cookies = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate to RVTrader
        await page.goto("https://www.rvtrader.com/")
        print("Browser opened. Browse the site, then go to: rvtrader.com/done")

        # Wait for user to navigate to /done
        while True:
            await asyncio.sleep(1)
            try:
                url = page.url
                if '/done' in url or not browser.is_connected():
                    break
            except:
                break

        # Extract cookies
        try:
            cookies = await context.cookies()
        except:
            pass

        await browser.close()

    # Convert cookies to string format
    cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

    # Check we got the important datadome cookie
    cookie_names = [c['name'] for c in cookies]
    if 'datadome' not in cookie_names:
        print("WARNING: datadome cookie not found! API requests may fail.")
    else:
        print("Got datadome cookie.")

    save_cookies_to_cache(cookie_string)
    return cookie_string


async def get_valid_cookies(force_refresh: bool = False) -> str:
    """Get valid cookies, refreshing via browser if needed."""
    if not force_refresh and cookies_are_valid():
        cookie_string, timestamp = load_cached_cookies()
        age_hours = (datetime.now() - timestamp).total_seconds() / 3600
        print(f"Using cached cookies ({age_hours:.1f}h old)")
        return cookie_string

    return await refresh_cookies_via_browser()


async def fetch_engagement(session: aiohttp.ClientSession, ad_id: str, listing: dict, headers: dict) -> dict:
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
        async with session.get(URL_VIEWS.format(ad_id=ad_id), headers=headers) as resp:
            if resp.status == 200:
                text = await resp.text()
                try:
                    data = json.loads(text)
                    views_val = data.get('listingViewsData')
                    if views_val is not None:
                        result['views'] = int(views_val) if str(views_val).isdigit() else None
                except json.JSONDecodeError:
                    result['fetch_error'] = f"Views non-JSON: {text[:80]}"
            else:
                result['fetch_error'] = f"Views status {resp.status}"

        # Fetch saves - response: {"error":null,"listingSavesData":1}
        async with session.get(URL_SAVES.format(ad_id=ad_id), headers=headers) as resp:
            if resp.status == 200:
                text = await resp.text()
                try:
                    data = json.loads(text)
                    saves_val = data.get('listingSavesData')
                    if saves_val is not None:
                        result['saves'] = int(saves_val) if str(saves_val).lstrip('-').isdigit() else saves_val
                except json.JSONDecodeError:
                    if not result.get('fetch_error'):
                        result['fetch_error'] = f"Saves non-JSON: {text[:80]}"
            else:
                if not result.get('fetch_error'):
                    result['fetch_error'] = f"Saves status {resp.status}"

        if result['views'] is not None or result['saves'] is not None:
            result['fetch_success'] = True

    except Exception as e:
        result['fetch_error'] = str(e)[:100]

    return result


async def scrape_all(listings: list, headers: dict, concurrency: int = 10) -> list:
    """Scrape engagement data for all listings with concurrency limit."""
    results = []
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_with_semaphore(session, ad_id, listing, index, total):
        async with semaphore:
            result = await fetch_engagement(session, ad_id, listing, headers)
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
    force_refresh = '--refresh-cookies' in sys.argv
    for i, arg in enumerate(sys.argv):
        if arg == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    # Get valid cookies (refreshes via browser if expired or forced)
    cookie_string = await get_valid_cookies(force_refresh=force_refresh)
    headers = get_headers(cookie_string)

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
    results = await scrape_all(listings, headers)

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
