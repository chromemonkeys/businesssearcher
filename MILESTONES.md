# Business Searcher - Implementation Milestones

## ✅ M1: Data Collection Layer (COMPLETE)

**Files:**
- `business_searcher/models/database.py` - SQLAlchemy setup
- `business_searcher/models/listing.py` - Pydantic + ORM models
- `business_searcher/models/repository.py` - Repository pattern with dedup
- `business_searcher/fetchers/base.py` - Abstract fetcher + Registry
- `business_searcher/fetchers/mock.py` - Mock fetcher for testing
- `business_searcher/fetchers/seek.py` - **Seek Business scraper (Playwright)**

**Features:**
- SQLite database with SQLAlchemy ORM
- `BusinessListing` Pydantic model for validation
- `ListingORM` for persistence
- Automatic deduplication by `(id, source)`
- Derived metrics (EBITDA margin, asking multiple)
- Status tracking: `new` → `prefilter_pass/fail` → `researching` → `completed`
- **Real Seek Business scraper** using Playwright + BeautifulSoup

**CLI:**
```bash
python -m business_searcher.main init              # Initialize DB
python -m business_searcher.main fetch --source seekbusiness --count 20
python -m business_searcher.main list --status prefilter_pass
python -m business_searcher.main stats
```

**Seek Business Fetcher:**
- Scrapes from `seekbusiness.com.au`
- **Primary focus: Rich description text** for research agent analysis
- Extracts from detail pages:
  - Full business description (the key input for M3 research)
  - Title, price, location, industry
  - Listing URL
- Financial data on Seek is inconsistently disclosed - descriptions contain the real value
- Pagination support
- Headless browser automation

---

## ✅ M2: Deterministic Pre-Filter (COMPLETE)

**Files:**
- `business_searcher/models/listing.py` - `ListingFilter` class
- `business_searcher/models/repository.py` - `PrefilterService`

**Features:**
- Configurable thresholds (max price, min revenue, min EBITDA margin)
- Industry inclusion/exclusion filters
- Automatic status updates on evaluation
- Detailed rejection reasons

**CLI:**
```bash
python -m business_searcher.main filter            # Apply default filters
python -m business_searcher.main filter --max-price 500000 --min-revenue 300000
```

**Default Filters:**
- Max Price: $1,000,000
- Min Revenue: $500,000
- Min EBITDA Margin: 15%

**Current Stats:**
```
Total Listings: 35 (from Sunshine Coast, 50km radius)
prefilter_pass: 31
prefilter_fail: 4 (mostly price > $1M or revenue < $500K)

Seek Business Detail Extraction Quality:
- With description: 64%
- With revenue: ~8% (financial disclosure varies by listing)
- With EBITDA: ~8%
```

---

## 🔄 M3: Research Agent Skeleton (NEXT)

**Goal:** Recursive research loop with state management

**Components:**
- `ResearchState` dataclass (defined in listing.py)
- `ResearchAgent` class in `agents/research.py`
- Max depth: 5 iterations
- Confidence threshold: 0.8

**State Tracking:**
```python
{
    "listing_data": {...},
    "inferred_industry": str,
    "search_history": [],
    "findings": [],
    "confidence_score": 0.0,
    "depth": 0
}
```

**Next Steps:**
1. Create `ResearchAgent` class
2. Implement recursive research loop
3. Add LLM integration for query generation
4. Test on 1-2 listings from `prefilter_pass`

---

## 📋 Upcoming Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| M4 | Web Search Integration (SerpAPI) | 🔜 |
| M5 | Final Memo Generation (Premium LLM) | 🔜 |
| M6 | Daily Scheduler | 🔜 |
| M7 | Logging & Cost Controls | 🔜 |
| M8 | Multi-agent Enhancements | 🔜 |

---

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
│   ├── listing.py          # Pydantic + ORM models
│   └── repository.py       # Repository pattern
├── fetchers/
│   ├── __init__.py
│   ├── base.py             # Abstract fetcher + Registry
│   ├── mock.py             # Mock fetcher
│   └── seek.py             # Seek Business scraper
└── agents/                 # (M3+)
    └── __init__.py

requirements.txt
MILESTONES.md
business_searcher.db        # SQLite DB
```

---

## Testing M1-M2 with Real Data

```bash
# 1. Setup
pip install -r requirements.txt
python -m business_searcher.main init

# 2. Fetch real listings from Sunshine Coast
python -m business_searcher.main fetch --source seekbusiness --count 30

# 3. Apply pre-filter
python -m business_searcher.main filter

# 4. Check results
python -m business_searcher.main stats
python -m business_searcher.main list --status prefilter_pass
```

---

## Next Steps

Ready to implement **M3: Research Agent Skeleton**? This will create the recursive research loop that:
1. Takes a `prefilter_pass` listing
2. Researches the industry using LLM + web search
3. Builds confidence score
4. Generates investment memo

Or should we enhance M1 first with:
- Detail page scraping (get revenue/EBITDA from listing pages)
- Filter out "SOLD" listings
- Add more locations/sources
