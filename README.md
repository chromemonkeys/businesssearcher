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

## Daily Automation

Run the complete workflow (fetch → filter → email) in one command:

```bash
# Run daily automation (fetches new listings, filters, exports, emails)
python daily_run.py
```

### Setup Gmail API (One-time)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download `client_secret.json` and place in project directory
5. Add `c2501038@gmail.com` as a test user
6. Run once to authenticate:
   ```bash
   python send_email.py
   ```
   - Sign in with c2501038@gmail.com when browser opens
   - Click "Continue" to authorize
   - Token saved to `token.json` for future runs

### Schedule Daily Runs (Linux/Mac)

Add to crontab to run daily at 9 AM:

```bash
# Open crontab editor
crontab -e

# Add this line:
0 9 * * * cd /path/to/businesssearcher && python daily_run.py >> daily_run.log 2>&1
```

### Windows Task Scheduler

1. Open Task Scheduler → Create Basic Task
2. Name: "Business Searcher Daily"
3. Trigger: Daily at 9:00 AM
4. Action: Start a program
5. Program: `python` (or full path to python.exe)
6. Arguments: `daily_run.py`
7. Start in: `C:\path\to\businesssearcher`

## Email Results Manually

```bash
# Send current filtered results via email
python send_email.py
```

## Database Query (Direct)

```bash
# Query database directly
python db_query.py
```

## License

MIT
