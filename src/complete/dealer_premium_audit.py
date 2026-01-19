"""
Dealer Premium Tier Audit
Detects Tier A vs Tier B dealers by comparing COMPARABLE listings.

Algorithm:
1. Find comparable listings (same make/model/year, similar price/photos/age)
2. Compare relevance scores between different dealers for comparable units
3. Dealer with consistently higher relevance for same-spec units = Tier A
4. Build confidence score based on number of comparisons

Key Insight:
- Two dealers with identical listings (same make/model/year/specs)
- But different relevance scores = different premium tiers
- The ONLY variable is the dealer's premium package level

Usage:
    python src/complete/dealer_premium_audit.py                     # Most recent data
    python src/complete/dealer_premium_audit.py --file output/ranked_listings_20260118.csv
"""

import csv
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import statistics
import glob

# Comparison thresholds for "comparable" listings
PRICE_TOLERANCE_PCT = 0.15      # 15% price difference = comparable
PHOTO_TOLERANCE = 10            # Within 10 photos = comparable
AGE_TOLERANCE_DAYS = 30         # Listed within 30 days of each other = comparable
MIN_RELEVANCE_GAP = 25          # Minimum gap to consider significant

# Confidence thresholds
MIN_COMPARISONS_HIGH_CONFIDENCE = 3
MIN_COMPARISONS_MEDIUM_CONFIDENCE = 2

# Premium vs Standard thresholds (based on observed clustering)
# These are the relevance score cutoffs that indicate premium placement
PREMIUM_TIER_A_MIN = 500        # Tier A premium: relevance >= 500
PREMIUM_TIER_B_MIN = 450        # Tier B premium: 450 <= relevance < 500
STANDARD_MAX = 400              # Standard: relevance < 400 (gray zone 400-450)

# Thor Industries brands
THOR_BRANDS = {
    'thor', 'thor motor coach', 'jayco', 'airstream', 'tiffin', 'tiffin motorhomes',
    'entegra', 'entegra coach', 'heartland', 'keystone', 'cruiser', 'dutchmen'
}


def find_latest_data_file(output_dir: Path = Path('output')) -> Path:
    """Find the most recent ranked_listings CSV file."""
    pattern = str(output_dir / 'ranked_listings_*.csv')
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"No ranked_listings files found in {output_dir}")
    files.sort(key=lambda x: Path(x).stat().st_mtime, reverse=True)
    return Path(files[0])


def load_listings(filepath: Path) -> list:
    """Load listings from CSV file."""
    listings = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['rank'] = int(row['rank']) if row.get('rank') else None
            row['relevance_score'] = float(row['relevance_score']) if row.get('relevance_score') else 0
            row['merch_score'] = float(row['merch_score']) if row.get('merch_score') else 0
            row['price'] = float(row['price']) if row.get('price') else None
            row['photo_count'] = int(row['photo_count']) if row.get('photo_count') else 0
            row['year'] = int(row['year']) if row.get('year') else None
            row['is_premium'] = row.get('is_premium', '').lower() in ('true', '1', 'yes')
            row['is_top_premium'] = row.get('is_top_premium', '').lower() in ('true', '1', 'yes')
            listings.append(row)
    return listings


def is_thor_brand(make: str) -> bool:
    """Check if make is a Thor Industries brand."""
    if not make:
        return False
    return make.lower().strip() in THOR_BRANDS


def are_comparable(listing_a: dict, listing_b: dict) -> bool:
    """
    Determine if two listings are comparable (same specs, different dealers).

    Comparable means:
    - Same make and model (exact match)
    - Same year
    - Same condition
    - Price within 15%
    - Photo count within 10
    """
    # Must be different dealers
    if listing_a.get('dealer_id') == listing_b.get('dealer_id'):
        return False

    # Must have same make/model (case-insensitive)
    make_a = (listing_a.get('make') or '').lower().strip()
    make_b = (listing_b.get('make') or '').lower().strip()
    model_a = (listing_a.get('model') or '').lower().strip()
    model_b = (listing_b.get('model') or '').lower().strip()

    if make_a != make_b or model_a != model_b:
        return False

    # Must have same year
    if listing_a.get('year') != listing_b.get('year'):
        return False

    # Must have same condition
    cond_a = (listing_a.get('condition') or '').lower()
    cond_b = (listing_b.get('condition') or '').lower()
    if cond_a != cond_b:
        return False

    # Price within tolerance (if both have prices)
    price_a = listing_a.get('price')
    price_b = listing_b.get('price')
    if price_a and price_b:
        avg_price = (price_a + price_b) / 2
        if abs(price_a - price_b) / avg_price > PRICE_TOLERANCE_PCT:
            return False

    # Photo count within tolerance
    photos_a = listing_a.get('photo_count', 0)
    photos_b = listing_b.get('photo_count', 0)
    if abs(photos_a - photos_b) > PHOTO_TOLERANCE:
        return False

    return True


def find_comparable_pairs(listings: list) -> list:
    """
    Find all pairs of comparable listings from different dealers.
    Returns list of (listing_a, listing_b, relevance_gap) tuples.
    """
    # Group by make+model+year+condition for efficiency
    groups = defaultdict(list)
    for listing in listings:
        key = (
            (listing.get('make') or '').lower().strip(),
            (listing.get('model') or '').lower().strip(),
            listing.get('year'),
            (listing.get('condition') or '').lower(),
        )
        if key[0] and key[1]:  # Must have make and model
            groups[key].append(listing)

    pairs = []
    for key, group_listings in groups.items():
        if len(group_listings) < 2:
            continue

        # Compare all pairs within group
        for i, listing_a in enumerate(group_listings):
            for listing_b in group_listings[i+1:]:
                if are_comparable(listing_a, listing_b):
                    rel_a = listing_a.get('relevance_score', 0)
                    rel_b = listing_b.get('relevance_score', 0)
                    gap = abs(rel_a - rel_b)

                    # Order so higher relevance is first
                    if rel_a >= rel_b:
                        pairs.append((listing_a, listing_b, gap))
                    else:
                        pairs.append((listing_b, listing_a, gap))

    return pairs


def analyze_dealer_tiers(listings: list, pairs: list) -> list:
    """
    Analyze dealers to classify as Premium (A/B) or Standard.

    Classification approach:
    1. PRIMARY: Use relevance score distribution to determine premium vs standard
       - Tier A Premium: significant listings with relevance >= 500
       - Tier B Premium: significant listings with relevance 450-499
       - Standard: most listings have relevance < 400
    2. SECONDARY: Use head-to-head comparisons to validate/refine
    """
    # Track dealer stats
    dealer_stats = defaultdict(lambda: {
        'dealer_id': None,
        'dealer_name': '',
        'dealer_group': '',
        'city': '',
        'state': '',
        'total_listings': 0,
        'thor_listings': 0,
        'wins': 0,
        'losses': 0,
        'win_gaps': [],
        'loss_gaps': [],
        'opponents': set(),
        'relevance_scores': [],
        'tier_a_listings': 0,  # Listings with relevance >= 500
        'tier_b_listings': 0,  # Listings with relevance 450-499
        'standard_listings': 0,  # Listings with relevance < 400
    })

    # First pass: collect dealer info and classify each listing
    for listing in listings:
        dealer_id = listing.get('dealer_id')
        if not dealer_id:
            continue

        d = dealer_stats[dealer_id]
        d['dealer_id'] = dealer_id
        d['dealer_name'] = listing.get('dealer_name', '')
        d['dealer_group'] = listing.get('dealer_group', '')
        d['city'] = listing.get('city', '')
        d['state'] = listing.get('state', '')
        d['total_listings'] += 1

        rel_score = listing.get('relevance_score', 0)
        d['relevance_scores'].append(rel_score)

        # Classify this listing
        if rel_score >= PREMIUM_TIER_A_MIN:
            d['tier_a_listings'] += 1
        elif rel_score >= PREMIUM_TIER_B_MIN:
            d['tier_b_listings'] += 1
        elif rel_score < STANDARD_MAX:
            d['standard_listings'] += 1
        # else: gray zone 400-450, don't count either way

        if is_thor_brand(listing.get('make', '')):
            d['thor_listings'] += 1

    # Second pass: analyze pairwise comparisons
    for winner, loser, gap in pairs:
        if gap < MIN_RELEVANCE_GAP:
            continue

        winner_id = winner.get('dealer_id')
        loser_id = loser.get('dealer_id')

        if winner_id:
            dealer_stats[winner_id]['wins'] += 1
            dealer_stats[winner_id]['win_gaps'].append(gap)
            dealer_stats[winner_id]['opponents'].add(loser_id)

        if loser_id:
            dealer_stats[loser_id]['losses'] += 1
            dealer_stats[loser_id]['loss_gaps'].append(gap)
            dealer_stats[loser_id]['opponents'].add(winner_id)

    # Calculate tier classification for each dealer
    results = []
    for dealer_id, stats in dealer_stats.items():
        wins = stats['wins']
        losses = stats['losses']
        total_comparisons = wins + losses
        total_listings = stats['total_listings']

        avg_relevance = statistics.mean(stats['relevance_scores']) if stats['relevance_scores'] else 0
        max_relevance = max(stats['relevance_scores']) if stats['relevance_scores'] else 0
        median_relevance = statistics.median(stats['relevance_scores']) if stats['relevance_scores'] else 0

        avg_win_gap = statistics.mean(stats['win_gaps']) if stats['win_gaps'] else 0
        avg_loss_gap = statistics.mean(stats['loss_gaps']) if stats['loss_gaps'] else 0

        win_rate = wins / total_comparisons if total_comparisons > 0 else None

        tier_a_pct = stats['tier_a_listings'] / total_listings if total_listings > 0 else 0
        tier_b_pct = stats['tier_b_listings'] / total_listings if total_listings > 0 else 0
        standard_pct = stats['standard_listings'] / total_listings if total_listings > 0 else 0

        # PRIMARY CLASSIFICATION: Based on relevance score distribution
        # A dealer is classified by their BEST listings (the premium they're paying for)
        if stats['tier_a_listings'] >= 3 or tier_a_pct >= 0.10:
            # Has meaningful Tier A premium listings
            inferred_tier = 'premium_A'
            confidence = 'high' if stats['tier_a_listings'] >= 5 else 'medium'
        elif stats['tier_b_listings'] >= 3 or tier_b_pct >= 0.10:
            # Has meaningful Tier B premium listings
            inferred_tier = 'premium_B'
            confidence = 'high' if stats['tier_b_listings'] >= 5 else 'medium'
        elif standard_pct >= 0.50 and stats['tier_a_listings'] == 0 and stats['tier_b_listings'] == 0:
            # Majority standard, no premium listings
            inferred_tier = 'standard'
            confidence = 'high' if stats['standard_listings'] >= 10 else 'medium'
        elif avg_relevance < STANDARD_MAX:
            # Low average relevance suggests standard
            inferred_tier = 'likely_standard'
            confidence = 'low'
        elif avg_relevance >= PREMIUM_TIER_A_MIN:
            # High average suggests premium A
            inferred_tier = 'likely_premium_A'
            confidence = 'low'
        elif avg_relevance >= PREMIUM_TIER_B_MIN:
            # Medium-high average suggests premium B
            inferred_tier = 'likely_premium_B'
            confidence = 'low'
        else:
            inferred_tier = 'unknown'
            confidence = 'none'

        # SECONDARY: Validate with head-to-head comparisons if available
        # BUT: Don't downgrade if dealer has significant premium listings
        # (they may have BOTH premium and standard inventory)
        if total_comparisons >= MIN_COMPARISONS_HIGH_CONFIDENCE:
            if win_rate >= 0.80 and avg_win_gap >= 100:
                # Consistently beats others by large margin = premium
                if inferred_tier in ('standard', 'likely_standard'):
                    inferred_tier = 'likely_premium_B'  # Upgrade classification
                confidence = 'high'
            elif win_rate <= 0.20 and avg_loss_gap >= 100:
                # Consistently loses by large margin on compared listings
                # BUT only downgrade if they have NO premium listings
                if stats['tier_a_listings'] == 0 and stats['tier_b_listings'] == 0:
                    if inferred_tier.startswith('premium') or inferred_tier.startswith('likely_premium'):
                        inferred_tier = 'standard'
                    confidence = 'high'
                # If they have premium listings, mark as mixed (has both)
                elif stats['tier_a_listings'] > 0 or stats['tier_b_listings'] > 0:
                    inferred_tier = inferred_tier + '_mixed' if not inferred_tier.endswith('_mixed') else inferred_tier

        results.append({
            'dealer_id': dealer_id,
            'dealer_name': stats['dealer_name'],
            'dealer_group': stats['dealer_group'],
            'city': stats['city'],
            'state': stats['state'],
            'total_listings': total_listings,
            'thor_listings': stats['thor_listings'],
            'tier_a_listings': stats['tier_a_listings'],
            'tier_b_listings': stats['tier_b_listings'],
            'standard_listings': stats['standard_listings'],
            'comparisons': total_comparisons,
            'wins': wins,
            'losses': losses,
            'win_rate': round(win_rate, 2) if win_rate is not None else None,
            'avg_win_gap': round(avg_win_gap, 1),
            'avg_loss_gap': round(avg_loss_gap, 1),
            'opponents_count': len(stats['opponents']),
            'avg_relevance': round(avg_relevance, 1),
            'max_relevance': round(max_relevance, 1),
            'median_relevance': round(median_relevance, 1),
            'inferred_tier': inferred_tier,
            'confidence': confidence,
            'last_updated': datetime.now().isoformat(),
        })

    # Sort: Premium A first, then Premium B, then Standard
    tier_order = {
        'premium_A': 0, 'likely_premium_A': 1, 'premium_A_mixed': 2,
        'premium_B': 3, 'likely_premium_B': 4, 'premium_B_mixed': 5,
        'standard': 6, 'likely_standard': 7,
        'unknown': 8
    }
    results.sort(key=lambda x: (tier_order.get(x['inferred_tier'], 9), -x['avg_relevance']))

    return results


def save_results(results: list, pairs: list, output_dir: Path):
    """Save results to CSV files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    main_file = output_dir / 'dealer_premium_tiers.csv'
    backup_file = output_dir / f'dealer_premium_tiers_{timestamp}.csv'
    pairs_file = output_dir / f'comparable_pairs_{timestamp}.csv'

    # Dealer tiers
    fieldnames = [
        'dealer_id', 'dealer_name', 'dealer_group', 'city', 'state',
        'total_listings', 'thor_listings',
        'tier_a_listings', 'tier_b_listings', 'standard_listings',
        'comparisons', 'wins', 'losses', 'win_rate',
        'avg_win_gap', 'avg_loss_gap', 'opponents_count',
        'avg_relevance', 'max_relevance', 'median_relevance',
        'inferred_tier', 'confidence', 'last_updated'
    ]

    for filepath in [main_file, backup_file]:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

    print(f"\nSaved: {main_file}")
    print(f"Backup: {backup_file}")

    # Save significant pairs for evidence
    significant_pairs = [(w, l, g) for w, l, g in pairs if g >= MIN_RELEVANCE_GAP]
    if significant_pairs:
        pairs_fields = [
            'make', 'model', 'year', 'condition', 'price_a', 'price_b',
            'photos_a', 'photos_b',
            'winner_dealer', 'winner_relevance', 'winner_rank',
            'loser_dealer', 'loser_relevance', 'loser_rank',
            'relevance_gap'
        ]
        with open(pairs_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=pairs_fields)
            writer.writeheader()
            for winner, loser, gap in sorted(significant_pairs, key=lambda x: -x[2])[:100]:
                writer.writerow({
                    'make': winner.get('make', ''),
                    'model': winner.get('model', ''),
                    'year': winner.get('year', ''),
                    'condition': winner.get('condition', ''),
                    'price_a': winner.get('price', ''),
                    'price_b': loser.get('price', ''),
                    'photos_a': winner.get('photo_count', ''),
                    'photos_b': loser.get('photo_count', ''),
                    'winner_dealer': winner.get('dealer_name', ''),
                    'winner_relevance': winner.get('relevance_score', ''),
                    'winner_rank': winner.get('rank', ''),
                    'loser_dealer': loser.get('dealer_name', ''),
                    'loser_relevance': loser.get('relevance_score', ''),
                    'loser_rank': loser.get('rank', ''),
                    'relevance_gap': gap,
                })
        print(f"Pairs evidence: {pairs_file}")

    return main_file


def print_summary(results: list, pairs: list, source_file: Path):
    """Print summary of findings."""
    print("\n" + "="*80)
    print("DEALER PREMIUM TIER AUDIT")
    print("="*80)
    print(f"Source: {source_file.name}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Stats
    total_pairs = len(pairs)
    significant_pairs = len([p for p in pairs if p[2] >= MIN_RELEVANCE_GAP])

    print(f"\nComparable listing pairs found: {total_pairs}")
    print(f"Significant pairs (gap >= {MIN_RELEVANCE_GAP}): {significant_pairs}")

    # Tier counts
    premium_a = [r for r in results if r['inferred_tier'].startswith('premium_A')]
    premium_b = [r for r in results if r['inferred_tier'].startswith('premium_B')]
    standard = [r for r in results if r['inferred_tier'] in ('standard', 'likely_standard')]
    unknown = [r for r in results if r['inferred_tier'] == 'unknown']

    print(f"\nDealer classification:")
    print(f"  PREMIUM Tier A: {len([r for r in results if r['inferred_tier'] == 'premium_A'])} pure, {len([r for r in results if r['inferred_tier'] == 'premium_A_mixed'])} mixed")
    print(f"  PREMIUM Tier B: {len([r for r in results if r['inferred_tier'] == 'premium_B'])} pure, {len([r for r in results if r['inferred_tier'] == 'premium_B_mixed'])} mixed")
    print(f"  STANDARD:       {len([r for r in results if r['inferred_tier'] == 'standard'])} confirmed, {len([r for r in results if r['inferred_tier'] == 'likely_standard'])} likely")
    print(f"  Unknown:        {len(unknown)}")

    # Classification rules
    print("\n" + "-"*80)
    print("CLASSIFICATION RULES:")
    print("-"*80)
    print(f"  Premium Tier A: >= 3 listings with relevance >= {PREMIUM_TIER_A_MIN}")
    print(f"  Premium Tier B: >= 3 listings with relevance {PREMIUM_TIER_B_MIN}-{PREMIUM_TIER_A_MIN-1}")
    print(f"  Standard:       Most listings have relevance < {STANDARD_MAX}")
    print("  Head-to-head comparisons validate classification (large gaps = tier difference)")

    # Premium A dealers
    if premium_a:
        print("\n" + "-"*80)
        print("PREMIUM TIER A DEALERS (paid for top placement):")
        print("-"*80)
        header = f"{'Dealer':<32} {'Tier':<12} {'A':<4} {'B':<4} {'Std':<4} {'AvgRel':<8} {'Thor':<5} {'Conf':<6}"
        print(header)
        print("-"*80)

        for r in premium_a[:20]:
            name = r['dealer_name'][:30] if r['dealer_name'] else 'Unknown'
            thor_flag = '*' if r['thor_listings'] > 0 else ''
            print(f"{name:<32} {r['inferred_tier']:<12} "
                  f"{r['tier_a_listings']:<4} {r['tier_b_listings']:<4} {r['standard_listings']:<4} "
                  f"{r['avg_relevance']:<8.1f} {r['thor_listings']}{thor_flag:<4} {r['confidence']:<6}")

    # Premium B dealers
    if premium_b:
        print("\n" + "-"*80)
        print("PREMIUM TIER B DEALERS (basic premium placement):")
        print("-"*80)
        print(header)
        print("-"*80)

        for r in premium_b[:20]:
            name = r['dealer_name'][:30] if r['dealer_name'] else 'Unknown'
            thor_flag = '*' if r['thor_listings'] > 0 else ''
            print(f"{name:<32} {r['inferred_tier']:<12} "
                  f"{r['tier_a_listings']:<4} {r['tier_b_listings']:<4} {r['standard_listings']:<4} "
                  f"{r['avg_relevance']:<8.1f} {r['thor_listings']}{thor_flag:<4} {r['confidence']:<6}")

    # Standard dealers
    if standard:
        print("\n" + "-"*80)
        print("STANDARD DEALERS (no premium placement):")
        print("-"*80)
        print(header)
        print("-"*80)

        for r in standard[:20]:
            name = r['dealer_name'][:30] if r['dealer_name'] else 'Unknown'
            thor_flag = '*' if r['thor_listings'] > 0 else ''
            print(f"{name:<32} {r['inferred_tier']:<12} "
                  f"{r['tier_a_listings']:<4} {r['tier_b_listings']:<4} {r['standard_listings']:<4} "
                  f"{r['avg_relevance']:<8.1f} {r['thor_listings']}{thor_flag:<4} {r['confidence']:<6}")

    # Example pairs showing tier differences
    significant = [(w, l, g) for w, l, g in pairs if g >= MIN_RELEVANCE_GAP]
    if significant:
        print("\n" + "-"*80)
        print("EVIDENCE: Comparable listings showing tier difference:")
        print("-"*80)
        print(f"{'Make/Model':<25} {'Higher Dealer':<20} {'Rel':<6} {'Lower Dealer':<20} {'Rel':<6} {'Gap':<5}")
        print("-"*80)

        for winner, loser, gap in sorted(significant, key=lambda x: -x[2])[:15]:
            make_model = f"{winner.get('make', '')} {winner.get('model', '')}"[:23]
            w_name = winner.get('dealer_name', '')[:18]
            l_name = loser.get('dealer_name', '')[:18]
            print(f"{make_model:<25} {w_name:<20} {winner.get('relevance_score', 0):<6.0f} "
                  f"{l_name:<20} {loser.get('relevance_score', 0):<6.0f} {gap:<5.0f}")


def main():
    data_file = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == '--file' and i + 1 < len(args):
            data_file = Path(args[i + 1])

    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)

    if data_file is None:
        try:
            data_file = find_latest_data_file(output_dir)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print("Run rank_listings.py first to generate data.")
            sys.exit(1)

    if not data_file.exists():
        print(f"Error: File not found: {data_file}")
        sys.exit(1)

    print("="*80)
    print("DEALER PREMIUM TIER AUDIT")
    print("="*80)
    print(f"Loading: {data_file}")

    listings = load_listings(data_file)
    print(f"Loaded {len(listings)} listings")

    print("\nFinding comparable listing pairs...")
    pairs = find_comparable_pairs(listings)
    print(f"Found {len(pairs)} comparable pairs")

    print("\nAnalyzing dealer tiers based on head-to-head comparisons...")
    results = analyze_dealer_tiers(listings, pairs)

    save_results(results, pairs, output_dir)
    print_summary(results, pairs, data_file)

    return results


if __name__ == "__main__":
    main()
