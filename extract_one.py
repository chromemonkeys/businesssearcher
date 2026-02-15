#!/usr/bin/env python3
"""Extract and display a single business listing."""

from business_searcher.models.database import SessionLocal
from business_searcher.models.listing import ListingORM
from business_searcher.fetchers.seek import SeekBusinessFetcher
from business_searcher.models.repository import ListingRepository
from sqlalchemy import select

def fetch_one_new(location="sunshine-coast-qld", radius_km=50):
    """Fetch 1 new listing from Seek Business."""
    fetcher = SeekBusinessFetcher()
    
    listings = list(fetcher.fetch(
        location=location,
        radius_km=radius_km,
        max_listings=1
    ))
    
    if not listings:
        print("No listings found")
        return None
    
    listing = listings[0]
    
    # Save to DB
    with SessionLocal() as db:
        repo = ListingRepository(db)
        saved, is_new = repo.save_with_dedup_check(listing)
        print(f"{'✨ New' if is_new else '🔄 Updated'}: {saved.title[:60]}...")
    
    return listing

def show_listing(listing):
    """Display a listing's full details."""
    print("=" * 70)
    print(f"📋 {listing.title}")
    print("=" * 70)
    print(f"ID:       {listing.id}")
    print(f"Source:   {listing.source}")
    print(f"Price:    ${listing.price:,}" if listing.price else "Price:    N/A")
    print(f"Location: {listing.location}")
    print(f"Industry: {listing.industry}")
    print(f"URL:      {listing.url}")
    print("-" * 70)
    print("DESCRIPTION:")
    print("-" * 70)
    if listing.description:
        print(listing.description)
    else:
        print("(No description available)")
    print("-" * 70)
    print(f"Raw data: {listing.raw_data}")
    print("=" * 70)

def get_latest_from_db():
    """Get the most recently added listing from DB."""
    with SessionLocal() as db:
        stmt = select(ListingORM).order_by(ListingORM.first_seen_at.desc()).limit(1)
        result = db.execute(stmt)
        return result.scalar()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--db":
        # Show latest from DB
        listing = get_latest_from_db()
        if listing:
            show_listing(listing)
    else:
        # Fetch new one
        print("Fetching 1 new listing from Seek Business...")
        listing = fetch_one_new()
        if listing:
            print()
            show_listing(listing)
