"""Main entry point for the business searcher."""
import argparse
import sys
from contextlib import contextmanager
from datetime import datetime

from business_searcher.models.database import init_db, SessionLocal
from business_searcher.models.repository import ListingRepository, PrefilterService
from business_searcher.models.listing import ListingFilter, ListingStatus
from business_searcher.fetchers.base import FetcherRegistry
from business_searcher.fetchers.mock import MockFetcher  # noqa: F401 - registers itself
from business_searcher.fetchers.seek import SeekBusinessFetcher  # noqa: F401 - registers itself


@contextmanager
def get_db_session():
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_command():
    """Initialize database."""
    print("🗄️  Initializing database...")
    init_db()
    print("✅ Database initialized")


def fetch_command(source: str = "all", count: int = 10):
    """Fetch listings from source(s)."""
    print(f"📥 Fetching listings from: {source}")

    with get_db_session() as db:
        repo = ListingRepository(db)

        if source == "all":
            fetcher = FetcherRegistry
        else:
            fetcher = FetcherRegistry.get(source)

        # Load existing IDs so fetcher can skip expensive detail fetches
        from sqlalchemy import select
        from business_searcher.models.listing import ListingORM
        existing_ids = set(
            row[0] for row in db.execute(select(ListingORM.id)).all()
        )
        if existing_ids:
            print(f"  📦 {len(existing_ids)} listings already in DB, will skip detail fetch for those")

        new_count = 0
        updated_count = 0

        for listing in fetcher.fetch(count=count, known_ids=existing_ids):
            _, is_new = repo.save_with_dedup_check(listing)
            if is_new:
                new_count += 1
                print(f"  ✨ New: {listing.title[:60]}...")
            else:
                updated_count += 1
                print(f"  🔄 Updated: {listing.title[:60]}...")

        print(f"\n📊 Summary: {new_count} new, {updated_count} updated")


def filter_command(max_price: int = 1_000_000):
    """Apply deterministic pre-filter to new listings."""
    print(f"🔍 Applying pre-filter...")
    print(f"   Max Price: ${max_price:,}")
    
    filter_config = ListingFilter(max_price=max_price)
    
    with get_db_session() as db:
        prefilter = PrefilterService(db, filter_config)
        repo = ListingRepository(db)
        
        # Get all NEW listings
        new_listings = repo.get_by_status(ListingStatus.NEW)
        
        passed = 0
        failed = 0
        skipped_sold = 0
        
        for orm in new_listings:
            from business_searcher.models.listing import BusinessListing
            listing = BusinessListing.model_validate(orm)
            
            # Check if SOLD - keep in DB but mark as fail
            if listing.title and 'sold' in listing.title.lower():
                repo.update_status(listing.id, ListingStatus.PREFILTER_FAIL)
                skipped_sold += 1
                print(f"  🚫 SOLD (skipped): {listing.title[:50]}...")
                continue
            
            passes, reasons = prefilter.process_listing(listing)
            
            if passes:
                passed += 1
                print(f"  ✅ PASS: {listing.title[:50]}...")
                if listing.price and listing.revenue and listing.ebitda:
                    margin = listing.ebitda / listing.revenue
                    print(f"      ${listing.price:,} | ${listing.revenue:,} rev | {margin:.1%} margin")
            else:
                failed += 1
                print(f"  ❌ FAIL: {listing.title[:50]}...")
                for reason in reasons:
                    print(f"      - {reason}")
        
        print(f"\n📊 Summary: {passed} passed, {failed} failed, {skipped_sold} SOLD skipped")


def list_command(status: str = "all", limit: int = 20):
    """List listings with optional status filter."""
    with get_db_session() as db:
        repo = ListingRepository(db)
        
        if status == "all":
            # Get all, most recent first
            from sqlalchemy import select
            from business_searcher.models.listing import ListingORM
            query = select(ListingORM).order_by(ListingORM.first_seen_at.desc()).limit(limit)
            listings = list(db.execute(query).scalars().all())
        else:
            from business_searcher.models.listing import ListingStatus
            listings = repo.get_by_status(ListingStatus(status), limit)
        
        print(f"\n📋 Listings (status={status}, limit={limit}):\n")
        print(f"{'ID':<20} {'Status':<15} {'Price':>12} {'Revenue':>12} {'Margin':>8} Title")
        print("-" * 100)
        
        for l in listings:
            margin_str = f"{l.ebitda_margin:.1%}" if l.ebitda_margin else "N/A"
            price_str = f"${l.price:,}" if l.price else "N/A"
            rev_str = f"${l.revenue:,}" if l.revenue else "N/A"
            
            print(f"{l.id[:20]:<20} {l.status:<15} {price_str:>12} {rev_str:>12} {margin_str:>8} {l.title[:40]}")
        
        print(f"\nTotal: {len(listings)} listings")


def stats_command():
    """Show database statistics."""
    with get_db_session() as db:
        repo = ListingRepository(db)
        stats = repo.get_stats()
        
        print("\n📊 Database Statistics:\n")
        print(f"Total Listings: {stats['total_listings']}")
        print("\nBy Status:")
        for status, count in stats['by_status'].items():
            print(f"  {status}: {count}")


def sources_command():
    """List available fetcher sources."""
    sources = FetcherRegistry.list_sources()
    print("\n📡 Available Sources:")
    for source in sources:
        print(f"  - {source}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Business-for-Sale Research Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s init                    # Initialize database
  %(prog)s fetch --source mock     # Fetch mock listings
  %(prog)s filter                  # Apply pre-filter
  %(prog)s list --status new       # List new listings
  %(prog)s stats                   # Show statistics
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # init
    subparsers.add_parser("init", help="Initialize database")
    
    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Fetch listings")
    fetch_parser.add_argument("--source", default="all", help="Source to fetch from")
    fetch_parser.add_argument("--count", type=int, default=10, help="Number of listings")
    
    # filter
    filter_parser = subparsers.add_parser("filter", help="Apply pre-filter")
    filter_parser.add_argument("--max-price", type=int, default=1_000_000)
    
    # list
    list_parser = subparsers.add_parser("list", help="List listings")
    list_parser.add_argument("--status", default="all", help="Filter by status")
    list_parser.add_argument("--limit", type=int, default=20)
    
    # stats
    subparsers.add_parser("stats", help="Show statistics")
    
    # sources
    subparsers.add_parser("sources", help="List available sources")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == "init":
        init_command()
    elif args.command == "fetch":
        fetch_command(args.source, args.count)
    elif args.command == "filter":
        filter_command(args.max_price)
    elif args.command == "list":
        list_command(args.status, args.limit)
    elif args.command == "stats":
        stats_command()
    elif args.command == "sources":
        sources_command()


if __name__ == "__main__":
    main()
