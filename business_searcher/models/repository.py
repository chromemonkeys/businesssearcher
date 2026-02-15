"""Repository pattern for listing persistence and deduplication."""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from business_searcher.models.listing import (
    ListingORM, 
    BusinessListing, 
    ListingStatus,
    ListingFilter
)


class ListingRepository:
    """
    Repository for listing CRUD operations and deduplication.
    
    Handles:
    - Saving new listings
    - Updating existing listings
    - Deduplication by source + ID
    - Status tracking
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def exists(self, listing_id: str, source: str) -> bool:
        """Check if listing already exists in database."""
        result = self.db.execute(
            select(ListingORM).where(
                and_(
                    ListingORM.id == listing_id,
                    ListingORM.source == source
                )
            )
        ).scalar_one_or_none()
        return result is not None
    
    def get_by_id(self, listing_id: str) -> Optional[ListingORM]:
        """Get listing by ID."""
        return self.db.execute(
            select(ListingORM).where(ListingORM.id == listing_id)
        ).scalar_one_or_none()
    
    def get_by_status(
        self, 
        status: ListingStatus, 
        limit: Optional[int] = None
    ) -> List[ListingORM]:
        """Get listings by processing status."""
        query = select(ListingORM).where(ListingORM.status == status.value)
        if limit:
            query = query.limit(limit)
        return list(self.db.execute(query).scalars().all())
    
    def save(self, listing: BusinessListing) -> ListingORM:
        """
        Save or update a listing.
        
        If listing exists, updates it.
        If new, creates it.
        """
        existing = self.get_by_id(listing.id)
        
        if existing:
            # Update existing
            return self._update(existing, listing)
        else:
            # Create new
            return self._create(listing)
    
    def save_with_dedup_check(
        self, 
        listing: BusinessListing
    ) -> tuple[ListingORM, bool]:
        """
        Save listing with explicit deduplication check.
        
        Returns:
            (orm_object, is_new) - is_new is True if newly created
        """
        is_new = not self.exists(listing.id, listing.source)
        orm = self.save(listing)
        return orm, is_new
    
    def update_status(
        self, 
        listing_id: str, 
        status: ListingStatus,
        processed_at: Optional[datetime] = None
    ) -> None:
        """Update processing status."""
        orm = self.get_by_id(listing_id)
        if orm:
            orm.status = status.value
            if processed_at:
                orm.processed_at = processed_at
            self.db.commit()
    
    def update_research_results(
        self,
        listing_id: str,
        confidence_score: float,
        scalability_score: int,
        memo: str,
        findings: dict
    ) -> None:
        """Update research results."""
        orm = self.get_by_id(listing_id)
        if orm:
            orm.confidence_score = confidence_score
            orm.scalability_score = scalability_score
            orm.memo = memo
            orm.research_findings = findings
            orm.status = ListingStatus.COMPLETED.value
            orm.processed_at = datetime.utcnow()
            self.db.commit()
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        from sqlalchemy import func
        
        total = self.db.execute(select(func.count(ListingORM.id))).scalar()
        
        status_counts = {}
        for status in ListingStatus:
            count = self.db.execute(
                select(func.count(ListingORM.id)).where(
                    ListingORM.status == status.value
                )
            ).scalar()
            status_counts[status.value] = count
        
        return {
            "total_listings": total,
            "by_status": status_counts,
        }
    
    def _create(self, listing: BusinessListing) -> ListingORM:
        """Create new listing record."""
        # Calculate derived metrics
        ebitda_margin = None
        if listing.ebitda and listing.revenue and listing.revenue > 0:
            ebitda_margin = listing.ebitda / listing.revenue
        
        asking_multiple = None
        if listing.price and listing.ebitda and listing.ebitda > 0:
            asking_multiple = listing.price / listing.ebitda
        
        orm = ListingORM(
            id=listing.id,
            source=listing.source,
            title=listing.title,
            description=listing.description,
            price=listing.price,
            revenue=listing.revenue,
            ebitda=listing.ebitda,
            location=listing.location,
            industry=listing.industry,
            url=listing.url,
            posted_date=listing.posted_date,
            ebitda_margin=ebitda_margin,
            asking_multiple=asking_multiple,
            raw_data=listing.raw_data,
            status=ListingStatus.NEW.value,
        )
        self.db.add(orm)
        self.db.commit()
        self.db.refresh(orm)
        return orm
    
    def _update(self, existing: ListingORM, listing: BusinessListing) -> ListingORM:
        """Update existing listing record."""
        existing.title = listing.title
        existing.description = listing.description
        existing.price = listing.price
        existing.revenue = listing.revenue
        existing.ebitda = listing.ebitda
        existing.location = listing.location
        existing.industry = listing.industry
        existing.url = listing.url
        existing.posted_date = listing.posted_date
        existing.raw_data = listing.raw_data
        existing.last_updated_at = datetime.utcnow()
        
        # Recalculate derived metrics
        if listing.ebitda and listing.revenue and listing.revenue > 0:
            existing.ebitda_margin = listing.ebitda / listing.revenue
        if listing.price and listing.ebitda and listing.ebitda > 0:
            existing.asking_multiple = listing.price / listing.ebitda
        
        self.db.commit()
        self.db.refresh(existing)
        return existing


class PrefilterService:
    """Service for applying deterministic pre-filters."""
    
    def __init__(self, db: Session, filters: Optional[ListingFilter] = None):
        self.db = db
        self.repo = ListingRepository(db)
        self.filters = filters or ListingFilter()
    
    def process_listing(self, listing: BusinessListing) -> tuple[bool, List[str]]:
        """
        Apply pre-filter to a listing and update its status.
        
        Returns:
            (passed, reasons) - passed is True if listing passes filter
        """
        # Save listing first
        orm, is_new = self.repo.save_with_dedup_check(listing)
        
        # Apply filter
        passes, reasons = self.filters.evaluate(listing)
        
        # Update status
        new_status = (
            ListingStatus.PREFILTER_PASS 
            if passes 
            else ListingStatus.PREFILTER_FAIL
        )
        self.repo.update_status(listing.id, new_status)
        
        return passes, reasons
    
    def get_candidates(self, limit: Optional[int] = None) -> List[ListingORM]:
        """Get listings that passed pre-filter."""
        return self.repo.get_by_status(ListingStatus.PREFILTER_PASS, limit)
