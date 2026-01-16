"""
Single-page NUXT_DATA extractor for RVTrader search results.
Extracts full listing data from __NUXT_DATA__ script tag.

Usage:
    python src/nuxt_extractor.py [URL]
    python src/nuxt_extractor.py "https://www.rvtrader.com/rvs-for-sale?type=Class%20B%7C198068&page=1"
"""

import json
import sys
import asyncio
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


def resolve_nuxt_data(data: list, val, depth: int = 0):
    """Recursively resolve Nuxt's reference-based data format."""
    if depth > 15:
        return val

    # If it's an integer reference, resolve it
    if isinstance(val, int) and 0 <= val < len(data):
        return resolve_nuxt_data(data, data[val], depth + 1)

    # If it's a list, resolve each element
    if isinstance(val, list):
        return [resolve_nuxt_data(data, v, depth + 1) for v in val]

    # If it's a dict, resolve each value
    if isinstance(val, dict):
        resolved = {}
        for k, v in val.items():
            resolved[k] = resolve_nuxt_data(data, v, depth + 1)
        return resolved

    return val


def extract_listings_from_nuxt(nuxt_data: list) -> list:
    """Extract and resolve listing objects from NUXT_DATA array."""
    listings = []

    for i, item in enumerate(nuxt_data):
        # Listing objects have classId and vehicle properties
        if isinstance(item, dict) and 'classId' in item and 'vehicle' in item:
            resolved = resolve_nuxt_data(nuxt_data, item)
            listings.append(resolved)

    return listings


def flatten_listing(listing: dict) -> dict:
    """Flatten nested listing structure into a cleaner format."""
    vehicle = listing.get('vehicle', {})

    flat = {
        # Core IDs
        'id': listing.get('id'),
        'dealer_id': vehicle.get('dealerId'),
        'customer_id': vehicle.get('customerId'),

        # Vehicle info
        'make': vehicle.get('makeName', [None])[0] if vehicle.get('makeName') else None,
        'model': vehicle.get('modelName', [None])[0] if vehicle.get('modelName') else None,
        'trim': vehicle.get('trimName', [None])[0] if vehicle.get('trimName') else None,
        'class': vehicle.get('className'),
        'condition': vehicle.get('condition'),
        'price': vehicle.get('price'),
        'mileage': listing.get('mileage'),
        'vin': listing.get('mfrSerialNum'),
        'stock_number': listing.get('stockNumber'),

        # Location
        'city': vehicle.get('city'),
        'state': vehicle.get('stateCode'),
        'zip_code': listing.get('zipCode'),
        'latitude': listing.get('latitude'),
        'longitude': listing.get('longitude'),

        # Dealer
        'dealer_name': listing.get('companyName'),
        'dealer_group': vehicle.get('dealerGroupName'),
        'dealer_website': vehicle.get('dealerWebsiteUrl'),
        'dealer_phone': vehicle.get('phone'),

        # Media
        'photo_count': len(vehicle.get('photoIds', [])) if vehicle.get('photoIds') else 0,
        'photo_ids': vehicle.get('photoIds', []),
        'floorplan_id': vehicle.get('floorplanMediaid'),

        # Dates
        'create_date': listing.get('createDate'),
        'price_drop_date': listing.get('datePriceDrop'),

        # Pricing
        'msrp': listing.get('msrp'),
        'price_history': listing.get('priceHistory'),

        # Metadata
        'seller_type': listing.get('sellerType'),
        'is_premium': listing.get('isPremium'),
        'is_top_premium': listing.get('isToppremium'),
        'badge_status': listing.get('badgeStatus'),
        'trusted_partner': listing.get('trustedPartner'),
        'listing_url': vehicle.get('adDetailUrl'),
        'description': vehicle.get('description'),
    }

    return flat


async def extract_page(url: str, headless: bool = True, retries: int = 3, browser=None, context=None) -> dict:
    """
    Extract listings from a single RVTrader search results page.

    Args:
        url: The search results URL to scrape
        headless: Run browser in headless mode
        retries: Number of retry attempts
        browser: Reuse existing browser instance (for efficiency)
        context: Reuse existing context instance

    Returns:
        dict with keys: success, url, listings, count, trk, error
    """
    result = {
        'success': False,
        'url': url,
        'listings': [],
        'count': 0,
        'trk': None,
        'error': None,
        'timestamp': datetime.now().isoformat()
    }

    own_browser = browser is None

    async def _attempt_extraction(page):
        """Inner extraction logic."""
        # Navigate to page
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)

        # Try multiple selectors - page might render differently
        nuxt_content = None
        for attempt in range(3):
            await page.wait_for_timeout(1000 + attempt * 500)

            nuxt_content = await page.evaluate('''() => {
                const script = document.querySelector('script#__NUXT_DATA__');
                return script ? script.textContent : null;
            }''')

            if nuxt_content:
                break

        if not nuxt_content:
            raise Exception('No __NUXT_DATA__ found after multiple attempts')

        # Extract trk object (metadata)
        trk = await page.evaluate('() => window.trk || null')

        # Parse and extract listings
        nuxt_data = json.loads(nuxt_content)
        raw_listings = extract_listings_from_nuxt(nuxt_data)
        listings = [flatten_listing(l) for l in raw_listings]

        return trk, listings

    try:
        if own_browser:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=headless)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )

                for attempt in range(retries):
                    page = await context.new_page()
                    try:
                        trk, listings = await _attempt_extraction(page)
                        result['success'] = True
                        result['trk'] = trk
                        result['listings'] = listings
                        result['count'] = len(listings)
                        break
                    except Exception as e:
                        result['error'] = str(e)
                        if attempt < retries - 1:
                            await page.wait_for_timeout(2000 * (attempt + 1))
                    finally:
                        await page.close()

                await browser.close()
        else:
            # Reuse provided browser/context
            for attempt in range(retries):
                page = await context.new_page()
                try:
                    trk, listings = await _attempt_extraction(page)
                    result['success'] = True
                    result['trk'] = trk
                    result['listings'] = listings
                    result['count'] = len(listings)
                    break
                except Exception as e:
                    result['error'] = str(e)
                    if attempt < retries - 1:
                        await page.wait_for_timeout(2000 * (attempt + 1))
                finally:
                    await page.close()

    except Exception as e:
        result['error'] = str(e)

    return result


async def main():
    # Default test URL
    default_url = "https://www.rvtrader.com/rvs-for-sale?type=Class%20B%7C198068&page=1"

    url = sys.argv[1] if len(sys.argv) > 1 else default_url

    print(f"Extracting listings from: {url}")
    print("-" * 60)

    result = await extract_page(url, headless=True)

    if result['success']:
        print(f"SUCCESS: Extracted {result['count']} listings")

        # Show trk metadata
        if result['trk']:
            trk = result['trk']
            print(f"\nPage metadata (trk):")
            print(f"  Total results: {trk.get('numresults', 'N/A')}")
            print(f"  Page number: {trk.get('pagenumber', 'N/A')}")
            print(f"  Sort: {trk.get('sortby', 'N/A')}")

        # Show sample listing
        if result['listings']:
            print(f"\nSample listing:")
            sample = result['listings'][0]
            print(f"  ID: {sample['id']}")
            print(f"  Make/Model: {sample['make']} {sample['model']}")
            print(f"  Price: {sample['price']}")
            print(f"  VIN: {sample['vin']}")
            print(f"  Location: {sample['city']}, {sample['state']} {sample['zip_code']}")
            print(f"  Dealer: {sample['dealer_name']}")
            print(f"  Photos: {sample['photo_count']}")
            print(f"  URL: {sample['listing_url']}")

        # Save to file
        output_file = Path("output/single_page_extract.json")
        output_file.parent.mkdir(exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\nFull data saved to: {output_file}")

    else:
        print(f"FAILED: {result['error']}")

    return result


if __name__ == "__main__":
    asyncio.run(main())
