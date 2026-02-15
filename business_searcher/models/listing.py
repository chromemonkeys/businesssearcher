"""Listing data models - Pydantic and SQLAlchemy."""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Boolean
from business_searcher.models.database import Base


class ListingStatus(str, Enum):
    """Processing status for a listing."""
    NEW = "new"
    PREFILTER_PASS = "prefilter_pass"
    PREFILTER_FAIL = "prefilter_fail"
    RESEARCHING = "researching"
    COMPLETED = "completed"
    FAILED = "failed"


# SQLAlchemy ORM Model
class ListingORM(Base):
    """Database model for business listings."""
    __tablename__ = "listings"
    
    id = Column(String, primary_key=True)
    source = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Integer)
    revenue = Column(Integer)
    ebitda = Column(Integer)
    location = Column(String, index=True)
    industry = Column(String, index=True)
    url = Column(String)
    
    # Financial metrics
    ebitda_margin = Column(Float)
    asking_multiple = Column(Float)  # Price / EBITDA
    
    # Processing state
    status = Column(String, default=ListingStatus.NEW, index=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime)
    
    # Source metadata
    posted_date = Column(String)  # e.g., "6 days ago", "29 days ago"
    
    # Raw data storage
    raw_data = Column(JSON)
    
    # Research results
    research_findings = Column(JSON)
    confidence_score = Column(Float)
    scalability_score = Column(Integer)
    memo = Column(Text)


# Pydantic Models for API/Validation
class BusinessListing(BaseModel):
    """Pydantic model for a business listing."""
    
    id: str = Field(..., description="Unique identifier from source")
    source: str = Field(..., description="Source platform (e.g., 'bizbuysell', 'seek')")
    title: str = Field(..., description="Business listing title")
    description: Optional[str] = Field(None, description="Full business description")
    
    # Financials
    price: Optional[int] = Field(None, description="Asking price in USD")
    revenue: Optional[int] = Field(None, description="Annual revenue in USD")
    ebitda: Optional[int] = Field(None, description="Annual EBITDA in USD")
    
    # Location & Industry
    location: Optional[str] = Field(None, description="Business location")
    industry: Optional[str] = Field(None, description="Industry/category")
    
    # Metadata
    url: Optional[str] = Field(None, description="Original listing URL")
    posted_date: Optional[datetime] = Field(None, description="When listing was posted")
    
    # Raw data for extensibility
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Original scraped data")
    
    class Config:
        from_attributes = True


class ListingFilter(BaseModel):
    """Filter criteria for deterministic pre-filtering."""
    
    max_price: int = Field(1_000_000, description="Maximum asking price")
    max_days_listed: Optional[int] = Field(60, description="Maximum days since listing (None = no limit)")
    preferred_industries: Optional[List[str]] = Field(None, description="Preferred industry keywords")
    excluded_industries: Optional[List[str]] = Field(
        default_factory=lambda: [
            # Retail
            "retail",
            # Hospitality
            "food & drink",
            "coffee", "cafe", "restaurant", 
            "pub", "bar",
            "accommodation", "tourism", "leisure",
            "takeaway", "hospitality",
            # Franchise (checked in title too)
            "franchise",
            "master franchise",
            # Personal Services (driving, beauty, etc.)
            "driving school", "driving",
            "beauty", "hair", "spa",
            "massage", "pilates", "gym", "fitness", "f45",
            "mechanic", "automotive", "tyre", "car detailing",
            "electrical", "electrical services",
            "handyman", "home services",
            "cleaning", "maintenance", "dry cleaning", "laundromat", "laundry",
            "fencing",
            "sports",
            "pest control",
            "taxi", "transport", "chauffeur", "courier", "freight", "truck",
            "pet grooming", "dog grooming",
            "garden", "lawn", "mowing", "nursery", "landscaping",
            "removals",
            "air conditioning", "air-con",
            "carpet", "flooring",
            "refund",
        ],
        description="Excluded industry keywords"
    )
    excluded_title_keywords: Optional[List[str]] = Field(
        default_factory=lambda: [
            "franchise",
            # Personal services (when not caught by industry filter)
            "pest control",
            "driving school",
            "driving",
            "massage",
            "pilates",
            "gym",
            "fitness",
            "f45",
            "beauty",
            "hair salon",
            "dry cleaning",
            "laundromat",
            "laundry",
            "handyman",
            "garden",
            "lawn",
            "mowing",
            "nursery",
            "courier",
            "taxi",
            "refund",
            "dog grooming",
            "pet grooming",
        ],
        description="Excluded title keywords (unless professional services)"
    )
    # Industries where 'franchise' in title is OK (professional services)
    franchise_allowed_industries: Optional[List[str]] = Field(
        default_factory=lambda: [
            "mortgage",
            "finance",
            "insurance",
            "legal",
            "accounting",
            "business services",
            "real estate",
        ],
        description="Industries where franchise keyword is allowed"
    )
    
    def evaluate(self, listing: BusinessListing) -> tuple[bool, List[str]]:
        """
        Evaluate listing against filter criteria.
        Returns (passes, reasons).
        """
        reasons = []
        passes = True
        
        # Price check
        if listing.price and listing.price > self.max_price:
            passes = False
            reasons.append(f"Price ${listing.price:,} exceeds max ${self.max_price:,}")
        
        # Industry exclusions
        if self.excluded_industries and listing.industry:
            for excluded in self.excluded_industries:
                if excluded.lower() in listing.industry.lower():
                    passes = False
                    reasons.append(f"Industry '{listing.industry}' matches exclusion '{excluded}'")
                    break
        
        # Title exclusions (e.g., franchise keywords in title)
        # But allow 'franchise' keyword for professional services industries
        if self.excluded_title_keywords and listing.title:
            title_lower = listing.title.lower()
            industry_lower = (listing.industry or "").lower()
            
            for excluded in self.excluded_title_keywords:
                if excluded.lower() in title_lower:
                    # Only allow 'franchise' keyword in professional services
                    # All other excluded keywords (pest control, dry cleaning, etc.) are never allowed
                    if excluded.lower() == "franchise":
                        is_allowed_franchise = any(
                            allowed in industry_lower 
                            for allowed in (self.franchise_allowed_industries or [])
                        )
                        if is_allowed_franchise:
                            continue  # Skip this exclusion for allowed industries
                    
                    passes = False
                    reasons.append(f"Title contains excluded keyword '{excluded}'")
                    break
        
        # Freshness filter (days since posted)
        if self.max_days_listed and listing.posted_date:
            from datetime import datetime
            try:
                # posted_date is already a datetime object (Pydantic converts it)
                if isinstance(listing.posted_date, datetime):
                    posted = listing.posted_date
                else:
                    posted = datetime.strptime(listing.posted_date, '%Y-%m-%d')
                days_listed = (datetime.utcnow() - posted).days
                if days_listed > self.max_days_listed:
                    passes = False
                    reasons.append(f"Listed {days_listed} days ago (max {self.max_days_listed})")
            except (ValueError, TypeError):
                pass  # If date parsing fails, skip this check
        
        return passes, reasons


class ResearchState(BaseModel):
    """State object for the research agent loop."""
    
    listing_data: BusinessListing
    inferred_industry: Optional[str] = None
    search_history: List[str] = Field(default_factory=list)
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = 0.0
    depth: int = 0
    
    class Config:
        arbitrary_types_allowed = True
