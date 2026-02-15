"""Abstract base class for listing fetchers."""
from abc import ABC, abstractmethod
from typing import List, Iterator
from business_searcher.models.listing import BusinessListing


class ListingFetcher(ABC):
    """Abstract base for all listing fetchers.
    
    Each fetcher is responsible for:
    1. Connecting to a specific source (API or scraped)
    2. Normalizing data to BusinessListing format
    3. Yielding listings one by one (memory efficient)
    """
    
    def __init__(self, source_name: str):
        self.source_name = source_name
    
    @abstractmethod
    def fetch(self, **kwargs) -> Iterator[BusinessListing]:
        """
        Fetch listings from source.
        
        Yields BusinessListing objects one at a time.
        Subclasses should implement pagination internally.
        
        Args:
            **kwargs: Source-specific parameters (location, category, etc.)
        
        Yields:
            BusinessListing: Normalized listing object
        """
        pass
    
    @abstractmethod
    def get_listing_detail(self, listing_id: str) -> BusinessListing:
        """
        Fetch full details for a specific listing.
        
        Some sources provide summary data in list view
        and require separate calls for full details.
        """
        pass
    
    def health_check(self) -> bool:
        """Check if source is accessible. Override if needed."""
        return True


class FetcherRegistry:
    """Registry for managing multiple fetchers."""
    
    _fetchers: dict[str, ListingFetcher] = {}
    
    @classmethod
    def register(cls, fetcher: ListingFetcher) -> None:
        """Register a fetcher instance."""
        cls._fetchers[fetcher.source_name] = fetcher
    
    @classmethod
    def get(cls, source_name: str) -> ListingFetcher:
        """Get fetcher by source name."""
        if source_name not in cls._fetchers:
            raise KeyError(f"No fetcher registered for source: {source_name}")
        return cls._fetchers[source_name]
    
    @classmethod
    def list_sources(cls) -> List[str]:
        """List all registered source names."""
        return list(cls._fetchers.keys())
    
    @classmethod
    def fetch_all(cls, **kwargs) -> Iterator[BusinessListing]:
        """Fetch from all registered sources."""
        for source_name, fetcher in cls._fetchers.items():
            try:
                for listing in fetcher.fetch(**kwargs):
                    yield listing
            except Exception as e:
                print(f"Error fetching from {source_name}: {e}")
                continue
