# Business Searcher

A tool for scraping and filtering business-for-sale listings from Seek Business (Australia).

## Features

- Scrape business listings from seekbusiness.com.au
- Apply deterministic pre-filters to exclude unwanted business types
- Store listings in SQLite database
- Export filtered results to CSV/TXT

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Or use uv
uv pip install -r requirements.txt

# Initialize database
python -m business_searcher.main init
```

## Usage

### Fetch Listings

```bash
# Fetch listings from Seek Business (Sunshine Coast default)
python -m business_searcher.main fetch --source seekbusiness --count 50

# Fetch from all sources
python -m business_searcher.main fetch --source all --count 20
```

### Apply Pre-filters

```bash
# Apply default filters (max $1M, excluded industries)
python -m business_searcher.main filter

# Custom max price
python -m business_searcher.main filter --max-price 800000
```

**Current Filters:**
- Max Price: $1,000,000 (configurable)
- Max Days Listed: 60 days
- Excluded Industries: retail, food & drink, hospitality, tourism, driving schools, beauty, gyms, mechanics, cleaning, fencing, sports, car detailing, dry cleaning, hair/beauty/spa, massage, handymen, pest control, automotive, taxi, dog grooming, truck freight, garden, laundromat, refund biz, courier, removals, air conditioning, carpet/flooring, electrical
- Excluded Title Keywords: franchise (unless mortgage/finance/insurance/legal/accounting/business services/real estate)

### View Results

```bash
# Show statistics
python -m business_searcher.main stats

# List passed listings
python -m business_searcher.main list --status prefilter_pass

# List failed listings
python -m business_searcher.main list --status prefilter_fail --limit 10
```

### Reset and Re-filter

```bash
# Reset all listings to 'new' status
python -c "
from business_searcher.models.database import SessionLocal
from business_searcher.models.listing import ListingORM, ListingStatus
from sqlalchemy import update

db = SessionLocal()
db.execute(update(ListingORM).values(status=ListingStatus.NEW.value))
db.commit()
print('Reset all listings to new')
"

# Then re-run filter
python -m business_searcher.main filter
```

## Exporting Results

Filtered results are automatically exported to:
- `prefilter_pass_listings.txt` - Full details with descriptions
- `prefilter_pass_listings.csv` - Spreadsheet format

## Project Structure

```
business_searcher/
├── __init__.py
├── main.py                 # CLI entry point
├── config/
│   └── settings.py         # Settings & env vars
├── models/
│   ├── __init__.py
│   ├── database.py         # SQLAlchemy setup
│   ├── listing.py          # Pydantic + ORM models + Filters
│   └── repository.py       # Repository pattern
└── fetchers/
    ├── __init__.py
    ├── base.py             # Abstract fetcher + Registry
    ├── mock.py             # Mock fetcher
    └── seek.py             # Seek Business scraper

business_searcher.db        # SQLite database
requirements.txt
MILESTONES.md
```

## Database Query (Direct)

```bash
# Query database directly
python db_query.py
```

## License

MIT
