#!/usr/bin/env python3
"""
Daily automation script for Business Searcher.

Workflow:
1. Fetch new listings from Seek Business
2. Reset all listings to 'new' status
3. Apply pre-filters
4. Generate output files
5. Email results

Usage:
    python daily_run.py
    
Or set up as a cron job:
    0 9 * * * cd /path/to/businesssearcher && python daily_run.py >> daily_run.log 2>&1
"""

import os
import sys
import base64
from datetime import datetime
from contextlib import contextmanager

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy import select, update

from business_searcher.models.database import SessionLocal, init_db
from business_searcher.models.listing import ListingORM, ListingStatus, ListingFilter
from business_searcher.models.repository import ListingRepository, PrefilterService
from business_searcher.fetchers.seek import SeekBusinessFetcher

# Email configuration
SENDER = 'c2501038@gmail.com'
RECIPIENT = 'cmilner99@gmail.com'
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Search configuration
LOCATION = 'sunshine-coast-qld'
RADIUS_KM = 50
FETCH_COUNT = 100  # Fetch up to 100 listings


@contextmanager
def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def fetch_listings():
    """Step 1: Fetch new listings from Seek Business."""
    print("\n" + "="*60)
    print("STEP 1: Fetching listings from Seek Business")
    print("="*60)
    
    with get_db() as db:
        # Get existing IDs to avoid refetching
        existing_ids = set(
            row[0] for row in db.execute(select(ListingORM.id)).all()
        )
        print(f"📦 {len(existing_ids)} listings already in DB")
        
        # Initialize fetcher
        fetcher = SeekBusinessFetcher()
        repo = ListingRepository(db)
        
        new_count = 0
        updated_count = 0
        
        try:
            for listing in fetcher.fetch(
                location=LOCATION,
                radius_km=RADIUS_KM,
                count=FETCH_COUNT,
                fetch_details=True,
                known_ids=existing_ids
            ):
                _, is_new = repo.save_with_dedup_check(listing)
                if is_new:
                    new_count += 1
                else:
                    updated_count += 1
        except Exception as e:
            print(f"⚠️  Fetch error: {e}")
        
        print(f"✅ Fetch complete: {new_count} new, {updated_count} updated")
        return new_count, updated_count


def reset_and_filter():
    """Step 2 & 3: Reset status and apply filters."""
    print("\n" + "="*60)
    print("STEP 2 & 3: Resetting status and applying filters")
    print("="*60)
    
    with get_db() as db:
        # Reset all to 'new'
        total = db.execute(
            update(ListingORM).values(status=ListingStatus.NEW.value)
        ).rowcount
        db.commit()
        print(f"🔄 Reset {total} listings to 'new' status")
        
        # Apply filters
        filter_config = ListingFilter()
        prefilter = PrefilterService(db, filter_config)
        repo = ListingRepository(db)
        
        new_listings = repo.get_by_status(ListingStatus.NEW)
        
        passed = 0
        failed = 0
        
        for orm in new_listings:
            from business_searcher.models.listing import BusinessListing
            listing = BusinessListing.model_validate(orm)
            
            # Skip SOLD listings
            if listing.title and 'sold' in listing.title.lower():
                repo.update_status(listing.id, ListingStatus.PREFILTER_FAIL)
                continue
            
            passes, reasons = prefilter.process_listing(listing)
            
            if passes:
                passed += 1
            else:
                failed += 1
        
        print(f"✅ Filter complete: {passed} passed, {failed} failed")
        return passed, failed


def export_results():
    """Step 4: Generate output files."""
    print("\n" + "="*60)
    print("STEP 4: Generating output files")
    print("="*60)
    
    with get_db() as db:
        results = db.execute(
            select(ListingORM)
            .where(ListingORM.status == 'prefilter_pass')
            .order_by(ListingORM.price.desc())
        ).scalars().all()
        
        # Write TXT
        output_lines = []
        output_lines.append('='*80)
        output_lines.append('BUSINESS LISTINGS - PREFILTER PASS')
        output_lines.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        output_lines.append(f'Total: {len(results)} listings')
        output_lines.append('='*80)
        output_lines.append('')
        
        for i, l in enumerate(results, 1):
            output_lines.append(f'#{i}')
            output_lines.append('-'*80)
            output_lines.append(f'Title:     {l.title}')
            output_lines.append(f'Price:     ${l.price:,}' if l.price else 'Price:     N/A')
            output_lines.append(f'Industry:  {l.industry}')
            output_lines.append(f'Location:  {l.location}')
            output_lines.append(f'URL:       {l.url}')
            if l.description:
                desc = l.description[:800] + '...' if len(l.description) > 800 else l.description
                output_lines.append(f'Description:\n{desc}')
            output_lines.append('')
            output_lines.append('')
        
        with open('prefilter_pass_listings.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        
        # Write CSV
        import csv
        with open('prefilter_pass_listings.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['#', 'Title', 'Price', 'Industry', 'Location', 'Posted', 'URL'])
            for i, l in enumerate(results, 1):
                writer.writerow([
                    i, l.title,
                    f'${l.price:,}' if l.price else 'N/A',
                    l.industry or 'N/A',
                    l.location or 'N/A',
                    str(l.posted_date) if l.posted_date else 'N/A',
                    l.url or 'N/A'
                ])
        
        print(f"✅ Exported: {len(results)} listings")
        print(f"   - prefilter_pass_listings.txt")
        print(f"   - prefilter_pass_listings.csv")
        return len(results)


def send_email(passed_count, total_count):
    """Step 5: Send email with results."""
    print("\n" + "="*60)
    print("STEP 5: Sending email")
    print("="*60)
    
    # Load credentials
    if not os.path.exists('token.json'):
        print("❌ Error: token.json not found. Run send_email.py first to authenticate.")
        return False
    
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    service = build('gmail', 'v1', credentials=creds)
    
    # Create message
    subject = f'Business Listings - {passed_count} Passed ({datetime.now().strftime("%Y-%m-%d")})'
    
    body = f'''Hi,

Daily business listings update:

SUMMARY
=======
Total listings in database: {total_count}
Passed filters: {passed_count}
Filtered out: {total_count - passed_count}

FILTERS APPLIED
===============
- Max Price: $1,000,000
- Max Days Listed: 60 days

EXCLUDED CATEGORIES
===================
• Retail, Food & Drink, Hospitality, Tourism
• Driving Schools, Beauty, Gyms, Mechanics, Sports
• Cleaning, Dry Cleaning, Laundromat
• Pest Control, Automotive, Taxi
• Courier, Truck Freight, Removals
• Garden, Lawn, Mowing, Nursery
• Air Conditioning, Carpet/Flooring, Electrical
• Dog Grooming, Pet Grooming
• Refund Biz

See attached file for full listing details.

Best regards,
Business Searcher
'''
    
    message = MIMEMultipart()
    message['to'] = RECIPIENT
    message['from'] = SENDER
    message['subject'] = subject
    message.attach(MIMEText(body))
    
    # Attach file
    with open('prefilter_pass_listings.txt', 'r', encoding='utf-8') as f:
        attachment = MIMEText(f.read())
        attachment.add_header(
            'Content-Disposition',
            'attachment; filename="prefilter_pass_listings.txt"'
        )
        message.attach(attachment)
    
    # Send
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = service.users().messages().send(userId='me', body={'raw': raw}).execute()
    
    print(f"✅ Email sent to {RECIPIENT}")
    print(f"   Message ID: {sent['id']}")
    return True


def get_stats():
    """Get current database stats."""
    with get_db() as db:
        total = db.execute(select(ListingORM)).scalar()
        passed = db.execute(
            select(ListingORM).where(ListingORM.status == 'prefilter_pass')
        ).scalar()
        return total, passed


def main():
    """Main daily workflow."""
    print("\n" + "="*60)
    print("BUSINESS SEARCHER - DAILY RUN")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    try:
        # Step 1: Fetch
        new_count, updated_count = fetch_listings()
        
        # Step 2 & 3: Reset and Filter
        passed, failed = reset_and_filter()
        
        # Step 4: Export
        passed_count = export_results()
        
        # Get total count
        total_count, _ = get_stats()
        
        # Step 5: Email
        send_email(passed_count, total_count)
        
        # Summary
        print("\n" + "="*60)
        print("DAILY RUN COMPLETE")
        print("="*60)
        print(f"New listings fetched: {new_count}")
        print(f"Updated listings: {updated_count}")
        print(f"Total passed filters: {passed_count}")
        print(f"Total in database: {total_count}")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
