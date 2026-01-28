"""
Thor Industries Brand Analysis for RVTrader Rankings
Analyzes search ranking data to provide actionable insights for Thor RV sales team.
Includes estimated rank improvements based on ranking algorithm.
"""

import json
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime


# Thor Industries brands (case-insensitive matching)
THOR_BRANDS = {
    'thor': 'Thor Motor Coach',
    'thor motor coach': 'Thor Motor Coach',
    'jayco': 'Jayco',
    'airstream': 'Airstream',
    'tiffin': 'Tiffin Motorhomes',
    'tiffin motorhomes': 'Tiffin Motorhomes',
    'entegra': 'Entegra Coach',
    'entegra coach': 'Entegra Coach',
    'heartland': 'Heartland RV',
    'cruiser': 'Cruiser RV',
    'keystone': 'Keystone RV',
    'dutchmen': 'Dutchmen RV',
}

# Ranking algorithm point values (from docs/RANKING_ALGORITHM.md)
POINT_VALUES = {
    'has_price': {'relevance': 194, 'merch': 5},
    'has_vin': {'relevance': 165, 'merch': 6},
    'photos_35plus': {'relevance': 195, 'merch': 30},
    'photos_20plus': {'relevance': 100, 'merch': 15},  # estimated partial
    'has_floorplan': {'relevance': 50, 'merch': 12},
    'description_2000plus': {'relevance': 0, 'merch': 45},
    'description_1000plus': {'relevance': 0, 'merch': 25},  # estimated partial
}

# Average relevance score difference per rank position (estimated from data)
RELEVANCE_PER_RANK = 15.0  # ~15 relevance points = 1 rank position


def identify_thor_brand(make):
    """Check if a make belongs to Thor Industries family."""
    make_lower = make.lower().strip()
    for pattern, brand_name in THOR_BRANDS.items():
        if pattern in make_lower:
            return brand_name
    return None


def load_ranked_listings(csv_path):
    """Load ranked listings from CSV file."""
    listings = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric fields
            try:
                row['rank'] = int(row['rank']) if row['rank'] else None
                row['price'] = float(row['price']) if row['price'] else None
                row['relevance_score'] = float(row['relevance_score']) if row['relevance_score'] else None
                row['merch_score'] = float(row['merch_score']) if row['merch_score'] else None
                row['photo_count'] = int(row['photo_count']) if row['photo_count'] else 0
                row['is_premium'] = row['is_premium'] == '1' or row['is_premium'].lower() == 'true'
                row['is_top_premium'] = row['is_top_premium'] == '1' or row['is_top_premium'].lower() == 'true'
                row['year'] = int(row['year']) if row['year'] else None
            except (ValueError, KeyError):
                pass
            listings.append(row)
    return listings


def analyze_thor_brands(listings):
    """Analyze Thor brand performance vs competitors."""
    thor_listings = []
    competitor_listings = []

    for listing in listings:
        brand = identify_thor_brand(listing.get('make', ''))
        listing['thor_brand'] = brand
        if brand:
            thor_listings.append(listing)
        else:
            competitor_listings.append(listing)

    return thor_listings, competitor_listings


def calculate_brand_metrics(listings, brand_key='thor_brand'):
    """Calculate key metrics by brand."""
    brand_metrics = defaultdict(lambda: {
        'count': 0,
        'ranks': [],
        'relevance_scores': [],
        'merch_scores': [],
        'photo_counts': [],
        'prices': [],
        'premium_count': 0,
        'top_premium_count': 0,
        'has_vin_count': 0,
        'has_price_count': 0,
        'models': set(),
    })

    for listing in listings:
        brand = listing.get(brand_key) or listing.get('make', 'Unknown')
        metrics = brand_metrics[brand]
        metrics['count'] += 1

        if listing.get('rank'):
            metrics['ranks'].append(listing['rank'])
        if listing.get('relevance_score'):
            metrics['relevance_scores'].append(listing['relevance_score'])
        if listing.get('merch_score'):
            metrics['merch_scores'].append(listing['merch_score'])
        if listing.get('photo_count'):
            metrics['photo_counts'].append(listing['photo_count'])
        if listing.get('price') and listing['price'] > 0:
            metrics['prices'].append(listing['price'])
            metrics['has_price_count'] += 1
        if listing.get('is_premium'):
            metrics['premium_count'] += 1
        if listing.get('is_top_premium'):
            metrics['top_premium_count'] += 1
        if listing.get('vin'):
            metrics['has_vin_count'] += 1
        if listing.get('model'):
            metrics['models'].add(listing['model'])

    # Calculate averages
    for brand, metrics in brand_metrics.items():
        metrics['avg_rank'] = sum(metrics['ranks']) / len(metrics['ranks']) if metrics['ranks'] else None
        metrics['avg_relevance'] = sum(metrics['relevance_scores']) / len(metrics['relevance_scores']) if metrics['relevance_scores'] else None
        metrics['avg_merch'] = sum(metrics['merch_scores']) / len(metrics['merch_scores']) if metrics['merch_scores'] else None
        metrics['avg_photos'] = sum(metrics['photo_counts']) / len(metrics['photo_counts']) if metrics['photo_counts'] else 0
        metrics['avg_price'] = sum(metrics['prices']) / len(metrics['prices']) if metrics['prices'] else None
        metrics['vin_rate'] = metrics['has_vin_count'] / metrics['count'] if metrics['count'] > 0 else 0
        metrics['price_rate'] = metrics['has_price_count'] / metrics['count'] if metrics['count'] > 0 else 0
        metrics['premium_rate'] = metrics['premium_count'] / metrics['count'] if metrics['count'] > 0 else 0
        metrics['model_count'] = len(metrics['models'])

    return brand_metrics


def calculate_improvement_potential(listing):
    """Calculate potential point gains and estimated rank improvement for a listing."""
    improvements = []
    total_relevance_gain = 0
    total_merch_gain = 0

    photo_count = listing.get('photo_count', 0)
    has_vin = bool(listing.get('vin'))
    has_price = listing.get('price') and listing['price'] > 0
    has_floorplan = bool(listing.get('floorplan_id'))
    current_rank = listing.get('rank', 0)

    # Check for missing price
    if not has_price:
        rel_gain = POINT_VALUES['has_price']['relevance']
        merch_gain = POINT_VALUES['has_price']['merch']
        total_relevance_gain += rel_gain
        total_merch_gain += merch_gain
        improvements.append({
            'action': 'Add price',
            'relevance_gain': rel_gain,
            'merch_gain': merch_gain,
            'difficulty': 'Easy',
            'priority': 1,
        })

    # Check for missing VIN
    if not has_vin:
        rel_gain = POINT_VALUES['has_vin']['relevance']
        merch_gain = POINT_VALUES['has_vin']['merch']
        total_relevance_gain += rel_gain
        total_merch_gain += merch_gain
        improvements.append({
            'action': 'Add VIN',
            'relevance_gain': rel_gain,
            'merch_gain': merch_gain,
            'difficulty': 'Easy',
            'priority': 2,
        })

    # Check photo count
    if photo_count < 35:
        if photo_count < 20:
            rel_gain = POINT_VALUES['photos_35plus']['relevance']
            merch_gain = POINT_VALUES['photos_35plus']['merch']
            photos_needed = 35 - photo_count
            improvements.append({
                'action': f'Add {photos_needed} photos (to 35+)',
                'relevance_gain': rel_gain,
                'merch_gain': merch_gain,
                'difficulty': 'Medium',
                'priority': 3,
            })
        else:
            rel_gain = POINT_VALUES['photos_35plus']['relevance'] - POINT_VALUES['photos_20plus']['relevance']
            merch_gain = POINT_VALUES['photos_35plus']['merch'] - POINT_VALUES['photos_20plus']['merch']
            photos_needed = 35 - photo_count
            improvements.append({
                'action': f'Add {photos_needed} more photos (to 35+)',
                'relevance_gain': rel_gain,
                'merch_gain': merch_gain,
                'difficulty': 'Medium',
                'priority': 4,
            })
        total_relevance_gain += rel_gain
        total_merch_gain += merch_gain

    # Check floorplan
    if not has_floorplan:
        rel_gain = POINT_VALUES['has_floorplan']['relevance']
        merch_gain = POINT_VALUES['has_floorplan']['merch']
        total_relevance_gain += rel_gain
        total_merch_gain += merch_gain
        improvements.append({
            'action': 'Add floorplan image',
            'relevance_gain': rel_gain,
            'merch_gain': merch_gain,
            'difficulty': 'Easy',
            'priority': 5,
        })

    # Check premium opportunity for non-premium listings ranked > 5
    if current_rank > 5 and not listing.get('is_premium'):
        improvements.append({
            'action': 'Purchase premium placement',
            'relevance_gain': 0,
            'merch_gain': 0,
            'difficulty': 'Cost',
            'priority': 10,
            'note': 'Moves to top tier, overrides all other factors'
        })

    # Estimate rank improvement
    estimated_rank_improvement = int(total_relevance_gain / RELEVANCE_PER_RANK)
    new_estimated_rank = max(1, current_rank - estimated_rank_improvement)

    return {
        'improvements': sorted(improvements, key=lambda x: x['priority']),
        'total_relevance_gain': total_relevance_gain,
        'total_merch_gain': total_merch_gain,
        'estimated_rank_improvement': estimated_rank_improvement,
        'current_rank': current_rank,
        'new_estimated_rank': new_estimated_rank,
    }


def find_ranking_opportunities(thor_listings):
    """Identify Thor listings that could improve rankings with estimated gains."""
    opportunities = []

    for listing in thor_listings:
        potential = calculate_improvement_potential(listing)

        if potential['improvements']:
            opportunities.append({
                'id': listing.get('id'),
                'brand': listing.get('thor_brand'),
                'make': listing.get('make'),
                'model': listing.get('model'),
                'year': listing.get('year'),
                'rank': listing.get('rank'),
                'relevance_score': listing.get('relevance_score'),
                'merch_score': listing.get('merch_score'),
                'photo_count': listing.get('photo_count'),
                'price': listing.get('price'),
                'has_vin': bool(listing.get('vin')),
                'has_floorplan': bool(listing.get('floorplan_id')),
                'is_premium': listing.get('is_premium'),
                'url': listing.get('listing_url'),
                **potential,
            })

    # Sort by potential rank improvement (biggest gains first)
    opportunities.sort(key=lambda x: x.get('estimated_rank_improvement', 0), reverse=True)
    return opportunities


def generate_report(csv_path, output_path=None):
    """Generate comprehensive Thor brand analysis report."""

    print(f"\nLoading data from: {csv_path}")
    listings = load_ranked_listings(csv_path)
    print(f"Total listings loaded: {len(listings)}")

    # Analyze Thor vs competitors
    thor_listings, competitor_listings = analyze_thor_brands(listings)
    print(f"Thor brand listings: {len(thor_listings)}")
    print(f"Competitor listings: {len(competitor_listings)}")

    # Calculate metrics
    thor_metrics = calculate_brand_metrics(thor_listings, 'thor_brand')
    competitor_metrics = calculate_brand_metrics(competitor_listings, 'make')

    # Find opportunities
    opportunities = find_ranking_opportunities(thor_listings)

    # Generate report
    report = []
    report.append("=" * 80)
    report.append("THOR INDUSTRIES BRAND ANALYSIS REPORT")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"Data Source: {Path(csv_path).name}")
    report.append("=" * 80)

    # Executive Summary
    report.append("\n" + "=" * 40)
    report.append("EXECUTIVE SUMMARY")
    report.append("=" * 40)

    total_thor = len(thor_listings)
    total_all = len(listings)
    thor_share = (total_thor / total_all * 100) if total_all > 0 else 0

    thor_with_rank = [l for l in thor_listings if l.get('rank')]
    comp_with_rank = [l for l in competitor_listings if l.get('rank')]

    avg_thor_rank = sum(l['rank'] for l in thor_with_rank) / len(thor_with_rank) if thor_with_rank else 0
    avg_comp_rank = sum(l['rank'] for l in comp_with_rank) / len(comp_with_rank) if comp_with_rank else 0

    report.append(f"\nMarket Presence:")
    report.append(f"  - Thor brand listings: {total_thor} ({thor_share:.1f}% of search results)")
    report.append(f"  - Competitor listings: {len(competitor_listings)} ({100-thor_share:.1f}%)")

    report.append(f"\nRanking Performance:")
    report.append(f"  - Thor avg rank: {avg_thor_rank:.1f}")
    report.append(f"  - Competitor avg rank: {avg_comp_rank:.1f}")
    if avg_thor_rank < avg_comp_rank:
        report.append(f"  - Thor brands OUTPERFORMING competitors by {avg_comp_rank - avg_thor_rank:.1f} positions")
    else:
        report.append(f"  - OPPORTUNITY: Thor brands trailing by {avg_thor_rank - avg_comp_rank:.1f} positions")

    # Total improvement potential
    total_potential_gain = sum(o['estimated_rank_improvement'] for o in opportunities)
    listings_with_gains = len([o for o in opportunities if o['estimated_rank_improvement'] > 0])

    report.append(f"\nImprovement Potential:")
    report.append(f"  - Listings with improvement opportunity: {listings_with_gains}")
    report.append(f"  - Total estimated rank positions recoverable: {total_potential_gain}")
    report.append(f"  - Avg improvement per listing: {total_potential_gain/listings_with_gains:.1f} positions" if listings_with_gains else "")

    # Thor Brand Breakdown
    report.append("\n" + "=" * 40)
    report.append("THOR BRAND PERFORMANCE")
    report.append("=" * 40)

    sorted_thor = sorted(thor_metrics.items(), key=lambda x: x[1]['count'], reverse=True)

    report.append(f"\n{'Brand':<20} {'Count':>6} {'Avg Rank':>10} {'Avg Merch':>10} {'Avg Photos':>11} {'VIN %':>7} {'Premium %':>10}")
    report.append("-" * 80)

    for brand, metrics in sorted_thor:
        avg_rank_str = f"{metrics['avg_rank']:.1f}" if metrics['avg_rank'] else "N/A"
        avg_merch_str = f"{metrics['avg_merch']:.1f}" if metrics['avg_merch'] else "N/A"
        report.append(
            f"{brand:<20} {metrics['count']:>6} {avg_rank_str:>10} {avg_merch_str:>10} "
            f"{metrics['avg_photos']:>11.1f} {metrics['vin_rate']*100:>6.0f}% {metrics['premium_rate']*100:>9.0f}%"
        )

    # Top 10 Competitors
    report.append("\n" + "=" * 40)
    report.append("TOP COMPETITORS (by listing count)")
    report.append("=" * 40)

    sorted_competitors = sorted(competitor_metrics.items(), key=lambda x: x[1]['count'], reverse=True)[:10]

    report.append(f"\n{'Make':<25} {'Count':>6} {'Avg Rank':>10} {'Avg Merch':>10} {'Avg Photos':>11}")
    report.append("-" * 70)

    for make, metrics in sorted_competitors:
        avg_rank_str = f"{metrics['avg_rank']:.1f}" if metrics['avg_rank'] else "N/A"
        avg_merch_str = f"{metrics['avg_merch']:.1f}" if metrics['avg_merch'] else "N/A"
        report.append(f"{make[:25]:<25} {metrics['count']:>6} {avg_rank_str:>10} {avg_merch_str:>10} {metrics['avg_photos']:>11.1f}")

    # Top Thor Performers
    report.append("\n" + "=" * 40)
    report.append("TOP PERFORMING THOR LISTINGS")
    report.append("=" * 40)

    top_thor = sorted([l for l in thor_listings if l.get('rank')], key=lambda x: x.get('rank', 999))[:10]

    report.append(f"\n{'Rank':>5} {'Brand':<15} {'Model':<25} {'Merch':>6} {'Photos':>7} {'Premium':>8}")
    report.append("-" * 75)

    for listing in top_thor:
        brand = (listing.get('thor_brand') or '')[:15]
        model = (listing.get('model') or '')[:25]
        merch = listing.get('merch_score', 0)
        photos = listing.get('photo_count', 0)
        premium = 'Yes' if listing.get('is_premium') else 'No'
        report.append(f"{listing['rank']:>5} {brand:<15} {model:<25} {merch:>6.0f} {photos:>7} {premium:>8}")

    # RANKING IMPROVEMENT OPPORTUNITIES (NEW SECTION)
    report.append("\n" + "=" * 80)
    report.append("RANKING IMPROVEMENT OPPORTUNITIES WITH ESTIMATED GAINS")
    report.append("=" * 80)

    report.append("""
Point Values Reference (from ranking algorithm):
  - Add price:      +194 relevance, +5 merch
  - Add VIN:        +165 relevance, +6 merch
  - 35+ photos:     +195 relevance, +30 merch
  - Add floorplan:  +50 relevance, +12 merch
  - ~15 relevance points = 1 rank position improvement
""")

    # Summary by action type
    action_summary = defaultdict(lambda: {'count': 0, 'total_rel': 0, 'total_merch': 0, 'total_rank_gain': 0})
    for opp in opportunities:
        for imp in opp['improvements']:
            action = imp['action'].split(' (')[0].split(' more')[0]  # Normalize action name
            action_summary[action]['count'] += 1
            action_summary[action]['total_rel'] += imp.get('relevance_gain', 0)
            action_summary[action]['total_merch'] += imp.get('merch_gain', 0)

    report.append("Improvement Actions Summary:")
    report.append(f"{'Action':<30} {'Listings':>10} {'Total Rel+':>12} {'Total Merch+':>12}")
    report.append("-" * 70)

    for action, data in sorted(action_summary.items(), key=lambda x: x[1]['total_rel'], reverse=True):
        if 'premium' not in action.lower():
            report.append(f"{action:<30} {data['count']:>10} {data['total_rel']:>12} {data['total_merch']:>12}")

    # Detailed opportunities
    report.append("\n" + "-" * 80)
    report.append("TOP 15 LISTINGS WITH HIGHEST IMPROVEMENT POTENTIAL")
    report.append("-" * 80)

    for i, opp in enumerate(opportunities[:15], 1):
        report.append(f"\n{i}. {opp['brand']} {opp['model']} ({opp['year']})")
        report.append(f"   Current Rank: {opp['rank']} -> Estimated New Rank: {opp['new_estimated_rank']} "
                      f"(+{opp['estimated_rank_improvement']} positions)")
        rel_str = f"{opp['relevance_score']:.0f}" if opp['relevance_score'] else 'N/A'
        merch_str = f"{opp['merch_score']:.0f}" if opp['merch_score'] else 'N/A'
        report.append(f"   Current Scores: Relevance={rel_str}, Merch={merch_str}")
        report.append(f"   Photos: {opp['photo_count']} | VIN: {'Yes' if opp['has_vin'] else 'NO'} | "
                      f"Price: {'Yes' if opp['price'] and opp['price'] > 0 else 'NO'} | Floorplan: {'Yes' if opp['has_floorplan'] else 'NO'}")
        report.append(f"   Potential Gains: +{opp['total_relevance_gain']} relevance, +{opp['total_merch_gain']} merch")
        report.append(f"   Recommended Actions:")
        for imp in opp['improvements'][:4]:  # Top 4 actions
            note = f" ({imp.get('note')})" if imp.get('note') else ""
            if imp.get('relevance_gain', 0) > 0 or imp.get('merch_gain', 0) > 0:
                report.append(f"     [{imp['difficulty']}] {imp['action']}: +{imp['relevance_gain']} rel, +{imp['merch_gain']} merch{note}")
            else:
                report.append(f"     [{imp['difficulty']}] {imp['action']}{note}")
        report.append(f"   URL: {opp['url']}")

    # Quick Wins Summary
    report.append("\n" + "=" * 40)
    report.append("QUICK WINS - EASY FIXES")
    report.append("=" * 40)

    quick_wins = []
    for opp in opportunities:
        for imp in opp['improvements']:
            if imp['difficulty'] == 'Easy' and imp.get('relevance_gain', 0) > 0:
                quick_wins.append({
                    'brand': opp['brand'],
                    'model': opp['model'],
                    'action': imp['action'],
                    'rel_gain': imp['relevance_gain'],
                    'merch_gain': imp['merch_gain'],
                    'url': opp['url'],
                })

    if quick_wins:
        report.append(f"\nEasy fixes that will improve rankings ({len(quick_wins)} total):\n")
        report.append(f"{'Brand':<15} {'Model':<20} {'Action':<20} {'Rel+':>6} {'Merch+':>7}")
        report.append("-" * 75)
        for qw in quick_wins[:20]:
            report.append(f"{qw['brand'][:15]:<15} {qw['model'][:20]:<20} {qw['action'][:20]:<20} "
                          f"+{qw['rel_gain']:>5} +{qw['merch_gain']:>6}")

    # Key Recommendations
    report.append("\n" + "=" * 40)
    report.append("KEY RECOMMENDATIONS")
    report.append("=" * 40)

    # Calculate totals for recommendations
    missing_vin_count = len([o for o in opportunities if not o['has_vin']])
    missing_price_count = len([o for o in opportunities if not o['price'] or o['price'] == 0])
    low_photo_count = len([o for o in opportunities if o['photo_count'] < 35])
    missing_floorplan_count = len([o for o in opportunities if not o['has_floorplan']])

    report.append(f"""
1. IMMEDIATE ACTIONS (This Week):
   - Add VINs to {missing_vin_count} listings -> +{missing_vin_count * 165} total relevance points
   - Add prices to {missing_price_count} listings -> +{missing_price_count * 194} total relevance points
   - Add floorplans to {missing_floorplan_count} listings -> +{missing_floorplan_count * 50} total relevance points

2. PHOTO OPTIMIZATION (Next 2 Weeks):
   - {low_photo_count} listings have < 35 photos
   - Adding photos to these could gain +{low_photo_count * 195} relevance points
   - Include: exterior (8 angles), interior (10+ shots), floorplan, features

3. PREMIUM PLACEMENT STRATEGY:
   - Focus premium spend on listings with merch score > 115
   - Premium placement moves listing to top tier, overrides relevance
   - ROI highest for high-value units already well-merchandised

4. ESTIMATED TOTAL IMPACT:
   - If all easy fixes implemented: ~{total_potential_gain} rank positions gained
   - Average listing could improve {total_potential_gain//max(1,listings_with_gains)} positions
""")

    # Output
    report_text = "\n".join(report)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"\nReport saved to: {output_path}")

    return report_text


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze Thor brand rankings on RVTrader')
    parser.add_argument('--input', '-i', help='Input CSV file (default: latest in output/)')
    parser.add_argument('--output', '-o', help='Output report file (default: stdout)')
    args = parser.parse_args()

    # Find input file
    if args.input:
        csv_path = Path(args.input)
    else:
        output_dir = Path(__file__).parent.parent.parent / 'output'
        csv_files = sorted(output_dir.glob('ranked_listings_*.csv'), reverse=True)
        if not csv_files:
            print("Error: No ranked_listings CSV files found in output/")
            return
        csv_path = csv_files[0]

    # Generate report
    report = generate_report(str(csv_path), args.output)

    if not args.output:
        print(report)


if __name__ == '__main__':
    main()
