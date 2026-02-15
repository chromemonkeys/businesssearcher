"""Configuration settings for the business searcher."""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Application settings with sensible defaults."""
    
    # Database
    DATABASE_URL: str = "sqlite:///business_searcher.db"
    
    # API Keys (load from environment)
    SERPAPI_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    
    # Model Configuration
    CHEAP_MODEL: str = "gpt-4o-mini"
    PREMIUM_MODEL: str = "claude-sonnet-4-20250514"
    
    # Agent Constraints
    MAX_RESEARCH_DEPTH: int = 5
    CONFIDENCE_THRESHOLD: float = 0.8
    MAX_SEARCHES_PER_LISTING: int = 10
    
    # Pre-filter thresholds
    MAX_PRICE: int = 1_000_000  # $1M
    MIN_REVENUE: int = 500_000  # $500k
    MIN_EBITDA_MARGIN: float = 0.15  # 15%
    
    # Cost Control
    MAX_TOKENS_PER_LISTING: int = 50_000
    DAILY_BUDGET_USD: float = 5.0
    
    def __post_init__(self):
        # Override with environment variables if present
        object.__setattr__(
            self, 
            'DATABASE_URL', 
            os.getenv('DATABASE_URL', self.DATABASE_URL)
        )
        object.__setattr__(
            self, 
            'SERPAPI_KEY', 
            os.getenv('SERPAPI_KEY')
        )
        object.__setattr__(
            self, 
            'OPENAI_API_KEY', 
            os.getenv('OPENAI_API_KEY')
        )
        object.__setattr__(
            self, 
            'ANTHROPIC_API_KEY', 
            os.getenv('ANTHROPIC_API_KEY')
        )


# Global settings instance
settings = Settings()
