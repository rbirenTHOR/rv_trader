"""
Fast engagement stats scraper using direct API endpoints.
Fetches views and saves data for all listings via HTTP.

Supports ScraperAPI proxy mode for static IP (browser + requests through same IP).

Usage:
    python src/engagement_scraper.py
    python src/engagement_scraper.py --limit 10
    python src/engagement_scraper.py --refresh-cookies  # Force cookie refresh
    python src/engagement_scraper.py --use-proxy        # Use ScraperAPI proxy mode
    python src/engagement_scraper.py --use-proxy --refresh-cookies  # Generate cookies via proxy
"""

import json
import sys
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote

# ScraperAPI configuration
SCRAPERAPI_KEY = "ef66e965591986214ea474407eb0adc8"

# ScraperAPI Proxy Mode (for routing browser + requests through same IP)
SCRAPERAPI_PROXY = {
    'server': 'http://proxy-server.scraperapi.com:8001',
    'username': 'scraperapi',
    'password': SCRAPERAPI_KEY,
}

# Global flag for proxy mode
USE_PROXY = False

# API endpoints (raw - will be wrapped with ScraperAPI if enabled)
URL_VIEWS_RAW = "https://www.rvtrader.com/gettiledata/addetail_listingstats/showadviewsstats?adId={ad_id}&realmId=%5Bobject%20Object%5D"
URL_SAVES_RAW = "https://www.rvtrader.com/gettiledata/addetail_listingstats/showsavedadsstats?adId={ad_id}&realmId=%5Bobject%20Object%5D"

def wrap_with_scraperapi(url: str, cookie_string: str = None) -> str:
    """Wrap a URL with ScraperAPI proxy using sticky session for consistent IP."""
    encoded_url = quote(url, safe='')
    # Use session_number for sticky IP (same IP as cookie generation)
    api_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={encoded_url}&session_number={SCRAPER_SESSION_ID}"

    # Pass cookies through ScraperAPI header passthrough
    if cookie_string:
        api_url += "&keep_headers=true"

    return api_url

# Cookie cache file and expiry
COOKIE_CACHE_FILE = Path(__file__).parent.parent / ".cookie_cache.json"
COOKIE_EXPIRY_HOURS = 48

# ScraperAPI session for sticky IP (valid for 3 min, refreshed on each request)
import random
SCRAPER_SESSION_ID = random.randint(1000000, 9999999)


def get_scraperapi_session_url(target_url: str, render: bool = False) -> str:
    """Build ScraperAPI URL with sticky session for consistent IP."""
    encoded_url = quote(target_url, safe='')
    url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={encoded_url}&session_number={SCRAPER_SESSION_ID}"
    if render:
        url += "&render=true"  # Execute JavaScript (needed for datadome cookie)
    return url


def get_headers(cookie_string: str) -> dict:
    """Build headers with the given cookie string."""
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "cookie": cookie_string,
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    }


def load_cached_cookies() -> tuple[str | None, datetime | None, int | None]:
    """Load cookies from cache file. Returns (cookie_string, timestamp, session_id) or (None, None, None)."""
    if not COOKIE_CACHE_FILE.exists():
        return None, None, None

    try:
        with open(COOKIE_CACHE_FILE, 'r') as f:
            data = json.load(f)
        timestamp = datetime.fromisoformat(data['timestamp'])
        session_id = data.get('session_id')  # May be None for browser-generated cookies
        return data['cookie_string'], timestamp, session_id
    except (json.JSONDecodeError, KeyError, ValueError):
        return None, None, None


def save_cookies_to_cache(cookie_string: str, session_id: int = None):
    """Save cookies to cache file with current timestamp and optional session ID."""
    with open(COOKIE_CACHE_FILE, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'cookie_string': cookie_string,
            'session_id': session_id
        }, f, indent=2)
    print(f"Cookies saved to {COOKIE_CACHE_FILE}")
    if session_id:
        print(f"  ScraperAPI session ID: {session_id}")


def cookies_are_valid(require_session: bool = False) -> bool:
    """Check if cached cookies exist and are less than 48 hours old.

    If require_session=True, also checks that a ScraperAPI session ID is stored.
    """
    cookie_string, timestamp, session_id = load_cached_cookies()
    if cookie_string is None or timestamp is None:
        return False

    age = datetime.now() - timestamp
    if age > timedelta(hours=COOKIE_EXPIRY_HOURS):
        print(f"Cookies are {age.total_seconds() / 3600:.1f} hours old (max {COOKIE_EXPIRY_HOURS}h)")
        return False

    if require_session and session_id is None:
        print("Cookies don't have ScraperAPI session ID - need refresh for proxy mode")
        return False

    return True


async def refresh_cookies_via_scraperapi() -> tuple[str, int]:
    """Get cookies by making a rendered request through ScraperAPI.

    Returns (cookie_string, session_id) so we can reuse the same IP.
    """
    import aiohttp

    print("\n" + "=" * 70)
    print("COOKIE REFRESH VIA SCRAPERAPI")
    print("=" * 70)
    print(f"  Session ID: {SCRAPER_SESSION_ID}")
    print("  Using JavaScript rendering to get datadome cookie...")
    print("=" * 70 + "\n")

    # Make a rendered request to RVTrader to get cookies
    target_url = "https://www.rvtrader.com/"
    api_url = get_scraperapi_session_url(target_url, render=True)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                print(f"  Status: {resp.status}")

                # ScraperAPI returns cookies in response headers
                cookies = []
                for cookie in resp.cookies.values():
                    cookies.append(f"{cookie.key}={cookie.value}")

                # Also check Set-Cookie headers
                set_cookies = resp.headers.getall('Set-Cookie', [])
                for sc in set_cookies:
                    # Parse "name=value; ..." format
                    if '=' in sc:
                        name_val = sc.split(';')[0]
                        if name_val not in cookies:
                            cookies.append(name_val)

                cookie_string = "; ".join(cookies)

                # Check for datadome
                if 'datadome' in cookie_string.lower():
                    print("  [OK] Got datadome cookie!")
                else:
                    print("  [WARN] No datadome cookie - engagement API may fail")
                    print(f"  Cookies received: {cookies[:3]}...")

                if cookie_string:
                    save_cookies_to_cache(cookie_string, SCRAPER_SESSION_ID)
                    return cookie_string, SCRAPER_SESSION_ID

    except Exception as e:
        print(f"  [ERROR] ScraperAPI cookie fetch failed: {e}")

    # Fallback to browser method
    print("\n  Falling back to browser method...")
    return await refresh_cookies_via_browser(), None


async def refresh_cookies_via_browser(use_proxy: bool = False) -> str:
    """Open browser, let user visit RVTrader, then capture cookies.

    If use_proxy=True, routes browser through ScraperAPI proxy for consistent IP.
    """
    from playwright.async_api import async_playwright

    print("\n" + "=" * 70)
    if use_proxy:
        print("COOKIE REFRESH VIA BROWSER (ScraperAPI Proxy)")
        print("=" * 70)
        print(f"  Proxy: {SCRAPERAPI_PROXY['server']}")
        print("  Browser will route through ScraperAPI for static IP")
    else:
        print("COOKIE REFRESH VIA BROWSER (Direct)")
    print("=" * 70)
    print("A browser will open. Please:")
    print("  1. Wait for RVTrader.com to fully load")
    print("  2. Browse around briefly (view a listing or two)")
    print("  3. Navigate to: rvtrader.com/done (type in address bar)")
    print("=" * 70 + "\n")

    cookies = []

    async with async_playwright() as p:
        # Configure proxy if enabled
        launch_options = {'headless': False}

        if use_proxy:
            launch_options['proxy'] = {
                'server': SCRAPERAPI_PROXY['server'],
                'username': SCRAPERAPI_PROXY['username'],
                'password': SCRAPERAPI_PROXY['password'],
            }

        browser = await p.chromium.launch(**launch_options)
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate to RVTrader (longer timeout for proxy)
        timeout_ms = 120000 if use_proxy else 30000
        try:
            await page.goto("https://www.rvtrader.com/", timeout=timeout_ms)
            print("Browser opened. Browse the site, then go to: rvtrader.com/done")
        except Exception as e:
            print(f"  [WARN] Initial page load issue: {e}")
            print("  Browser should still be open - try navigating manually")

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


async def get_valid_cookies(force_refresh: bool = False, use_proxy: bool = False) -> tuple[str, int | None]:
    """Get valid cookies, refreshing if needed.

    Args:
        force_refresh: Force cookie refresh even if valid
        use_proxy: Use ScraperAPI to get cookies (enables proxy mode for engagement)

    Returns:
        (cookie_string, session_id) - session_id is None for browser-generated cookies
    """
    global SCRAPER_SESSION_ID

    # Check if we have valid cookies (with session if proxy mode)
    if not force_refresh and cookies_are_valid(require_session=use_proxy):
        cookie_string, timestamp, session_id = load_cached_cookies()
        age_hours = (datetime.now() - timestamp).total_seconds() / 3600
        print(f"Using cached cookies ({age_hours:.1f}h old)")
        if session_id:
            SCRAPER_SESSION_ID = session_id
            print(f"  ScraperAPI session ID: {session_id}")
        return cookie_string, session_id

    # Refresh cookies (browser method, optionally through proxy)
    cookie_string = await refresh_cookies_via_browser(use_proxy=use_proxy)
    return cookie_string, None


async def fetch_engagement(session: aiohttp.ClientSession, ad_id: str, listing: dict, headers: dict, use_proxy: bool = False, cookie_string: str = None, proxy_url: str = None) -> dict:
    """Fetch views and saves for a single listing.

    If use_proxy=True and proxy_url provided, routes requests through proxy.
    """
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
        # Build URLs (direct - proxy is handled at session level)
        views_url = URL_VIEWS_RAW.format(ad_id=ad_id)
        saves_url = URL_SAVES_RAW.format(ad_id=ad_id)

        # Fetch views - response: {"error":null,"listingViewsData":"138"}
        async with session.get(views_url, headers=headers, timeout=aiohttp.ClientTimeout(total=60), proxy=proxy_url) as resp:
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
        async with session.get(saves_url, headers=headers, timeout=aiohttp.ClientTimeout(total=60), proxy=proxy_url) as resp:
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

    except asyncio.TimeoutError:
        result['fetch_error'] = "Timeout"
    except Exception as e:
        result['fetch_error'] = f"{type(e).__name__}: {str(e)[:80]}"

    return result


async def scrape_all(listings: list, headers: dict, concurrency: int = 30, use_proxy: bool = False, cookie_string: str = None, proxy_url: str = None) -> list:
    """Scrape engagement data for all listings with concurrency limit.

    If use_proxy=True and proxy_url provided, routes all requests through the proxy.
    """
    results = []
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_with_semaphore(session, ad_id, listing, index, total):
        async with semaphore:
            result = await fetch_engagement(session, ad_id, listing, headers, use_proxy=use_proxy, cookie_string=cookie_string, proxy_url=proxy_url)
            err = result.get('fetch_error') or ''
            status = "OK" if result['fetch_success'] else f"FAIL: {err[:30] if err else '?'}"
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
    use_proxy = '--use-proxy' in sys.argv

    for i, arg in enumerate(sys.argv):
        if arg == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    # Build proxy URL if enabled
    proxy_url = None
    if use_proxy:
        proxy_url = f"http://{SCRAPERAPI_PROXY['username']}:{SCRAPERAPI_PROXY['password']}@proxy-server.scraperapi.com:8001"
        print("=" * 70)
        print("ScraperAPI Proxy Mode: Static IP")
        print("  - Browser and HTTP requests route through same proxy IP")
        print("  - Cookies will be valid for proxy IP")
        print("=" * 70)
        concurrency = 10  # Lower concurrency for proxy
    else:
        print("Direct Mode: Using session cookies")
        concurrency = 30

    # Get valid cookies (refreshes via browser, optionally through proxy)
    cookie_string, _ = await get_valid_cookies(force_refresh=force_refresh, use_proxy=use_proxy)
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
    start_time = datetime.now()
    results = await scrape_all(listings, headers, concurrency=concurrency, use_proxy=use_proxy, cookie_string=cookie_string, proxy_url=proxy_url)
    elapsed = (datetime.now() - start_time).total_seconds()

    # Summary
    success_count = sum(1 for r in results if r['fetch_success'])
    views_count = sum(1 for r in results if r.get('views') is not None)
    saves_count = sum(1 for r in results if r.get('saves') is not None)

    print("-" * 70)
    print(f"Completed in {elapsed:.1f}s ({len(results)/elapsed:.1f} listings/sec)")
    print(f"Success: {success_count}/{len(results)}")
    print(f"With views data: {views_count}/{len(results)}")
    print(f"With saves data: {saves_count}/{len(results)}")
    print(f"Mode: {'ScraperAPI Proxy' if use_proxy else 'Direct'}")

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
