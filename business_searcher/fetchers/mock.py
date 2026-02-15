"""Mock fetcher for testing - generates sample business listings."""
import random
from datetime import datetime, timedelta
from typing import Iterator
from business_searcher.fetchers.base import ListingFetcher
from business_searcher.models.listing import BusinessListing


class MockFetcher(ListingFetcher):
    """
    Mock fetcher that generates sample business listings.
    Useful for testing without hitting real APIs.
    """
    
    # Sample data for realistic mock listings
    INDUSTRIES = [
        "Plumbing Services",
        "HVAC Installation & Repair",
        "Commercial Cleaning",
        "Auto Repair Shop",
        "Landscaping & Lawn Care",
        "Electrical Contracting",
        "Pest Control Services",
        "Coffee Shop / Cafe",
        "Digital Marketing Agency",
        "IT Services & Support",
        "Manufacturing - Industrial Parts",
        "Distribution - Wholesale Goods",
        "Restaurant - Fast Casual",
        "Fitness Center / Gym",
        "Medical Practice",
    ]
    
    LOCATIONS = [
        "Brisbane, QLD",
        "Sydney, NSW",
        "Melbourne, VIC",
        "Perth, WA",
        "Adelaide, SA",
        "Gold Coast, QLD",
        "Austin, TX",
        "Miami, FL",
        "Denver, CO",
        "Phoenix, AZ",
    ]
    
    TEMPLATES = [
        "Profitable {industry} with Established Customer Base",
        "Turnkey {industry} - Owner Retiring",
        "Growing {industry} - High Margins",
        "Well-Established {industry} - 20+ Years",
        "Scalable {industry} with Recurring Revenue",
    ]
    
    def __init__(self):
        super().__init__("mock")
        self._generated_ids = set()
    
    def fetch(self, count: int = 10, **kwargs) -> Iterator[BusinessListing]:
        """Generate mock listings."""
        for i in range(count):
            listing = self._generate_listing(i)
            yield listing
    
    def get_listing_detail(self, listing_id: str) -> BusinessListing:
        """Return detailed version (same as basic for mock)."""
        # Parse index from ID
        try:
            idx = int(listing_id.split("_")[-1])
        except (ValueError, IndexError):
            idx = 0
        return self._generate_listing(idx)
    
    def _generate_listing(self, idx: int) -> BusinessListing:
        """Generate a single realistic mock listing."""
        industry = random.choice(self.INDUSTRIES)
        location = random.choice(self.LOCATIONS)
        template = random.choice(self.TEMPLATES)
        
        # Generate financials with realistic ratios
        # Mix of passing and failing pre-filter criteria
        revenue = random.randint(200_000, 2_000_000)
        
        # EBITDA margin varies 5% to 35%
        ebitda_margin = random.uniform(0.05, 0.35)
        ebitda = int(revenue * ebitda_margin)
        
        # Asking price: 2x to 5x EBITDA
        price_multiple = random.uniform(2.0, 5.0)
        price = int(ebitda * price_multiple)
        
        # Posted date within last 30 days
        days_ago = random.randint(0, 30)
        posted_date = datetime.now() - timedelta(days=days_ago)
        
        listing_id = f"mock_{idx}_{datetime.now().strftime('%Y%m%d')}"
        
        return BusinessListing(
            id=listing_id,
            source="mock",
            title=template.format(industry=industry),
            description=self._generate_description(industry, location, revenue, ebitda),
            price=price,
            revenue=revenue,
            ebitda=ebitda,
            location=location,
            industry=industry,
            url=f"https://example.com/listing/{listing_id}",
            posted_date=posted_date,
            raw_data={
                "employees": random.randint(2, 25),
                "years_in_business": random.randint(5, 30),
                "reason_for_selling": random.choice([
                    "Retirement",
                    "Relocation",
                    "New venture",
                    "Health reasons",
                ]),
            }
        )
    
    def _generate_description(
        self, 
        industry: str, 
        location: str, 
        revenue: int, 
        ebitda: int
    ) -> str:
        """Generate a realistic business description."""
        margin = ebitda / revenue if revenue > 0 else 0
        
        descriptions = [
            f"Well-established {industry} operating in {location} for over 15 years. "
            f"Strong reputation with excellent customer retention. "
            f"Annual revenue of ${revenue:,} with {margin:.1%} EBITDA margin. "
            f"Trained staff in place. Owner willing to provide transition training.",
            
            f"Growing {industry} business in prime {location} location. "
            f"Revenue has increased 15% year-over-year for past 3 years. "
            f"Current revenue ${revenue:,}, EBITDA ${ebitda:,}. "
            f"Significant opportunity for expansion into adjacent markets.",
            
            f"Turnkey {industry} operation with established systems and processes. "
            f"Serves {location} and surrounding areas. "
            f"Strong recurring revenue base. Financials: ${revenue:,} revenue, "
            f"${ebitda:,} EBITDA. Owner retiring after 20 successful years.",
        ]
        
        return random.choice(descriptions)


# Register the mock fetcher
from business_searcher.fetchers.base import FetcherRegistry
FetcherRegistry.register(MockFetcher())
