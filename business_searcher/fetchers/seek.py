"""Seek Business (seekbusiness.com.au) fetcher using Playwright."""
import re
import time
import random
from typing import Iterator, Optional, Dict, Any
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup

from business_searcher.fetchers.base import ListingFetcher, FetcherRegistry
from business_searcher.models.listing import BusinessListing


class SeekBusinessFetcher(ListingFetcher):
    """
    Fetcher for seekbusiness.com.au
    
    Focus: Capture rich description text for research agent analysis.
    Financial data on Seek is inconsistently disclosed, so we prioritize
    the business description which contains valuable qualitative information.
    """
    
    BASE_URL = "https://www.seekbusiness.com.au"
    
    def __init__(self):
        super().__init__("seekbusiness")
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
    
    def _init_browser(self):
        """Initialize Playwright browser (lazy loading)."""
        if self._browser is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
        return self._browser
    
    def _close_browser(self):
        """Clean up browser resources."""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
    
    def _get_context_and_page(self):
        """Get or create browser context and page."""
        if self._context is None:
            browser = self._init_browser()
            self._context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            self._page = self._context.new_page()
        return self._page
    
    def _close_context(self):
        """Close context but keep browser for reuse."""
        if self._context:
            self._context.close()
            self._context = None
            self._page = None
    
    def fetch(
        self,
        location: str = "sunshine-coast-qld",
        radius_km: int = 50,
        count: int = 20,
        fetch_details: bool = True,
        known_ids: set = None,
        **kwargs
    ) -> Iterator[BusinessListing]:
        """
        Fetch listings from Seek Business.

        Args:
            location: Location slug (e.g., 'sunshine-coast-qld')
            radius_km: Search radius in kilometers
            count: Maximum listings to fetch
            fetch_details: Whether to fetch detail pages for full description
            known_ids: Set of listing IDs already in DB (skip detail fetch for these)

        Yields:
            BusinessListing objects with full description
        """
        known_ids = known_ids or set()
        page = self._get_context_and_page()
        fetched = 0
        page_num = 1

        try:
            search_url = self._build_search_url(location, radius_km)
            skipped = 0
            print(f"🔍 Fetching from: {search_url} (target: {count} listings)")

            while fetched < count:
                page_url = f"{search_url}&pg={page_num}"
                print(f"\n  📄 Page {page_num} — Progress: {fetched}/{count} fetched, {skipped} skipped")
                
                listing_elements = self._fetch_list_page(page, page_url)
                if not listing_elements:
                    print(f"  No more listings on page {page_num}")
                    break

                print(f"    Found {len(listing_elements)} listings")

                consecutive_failures = 0

                for element in listing_elements:
                    if fetched >= count:
                        break

                    try:
                        basic_info = self._parse_listing_basic(element)
                        if not basic_info:
                            continue

                        # Skip SOLD listings from search results
                        if 'sold' in basic_info['title'].lower():
                            skipped += 1
                            print(f"    ⏭️  Skipping SOLD: {basic_info['title'][:50]}...")
                            continue

                        # Skip listings already in DB — no need to re-fetch detail page
                        if basic_info['id'] in known_ids:
                            skipped += 1
                            print(f"    ⏩ Already in DB: {basic_info['title'][:50]}...")
                            continue

                        # Fetch detail page for real title + description + posted date + structured data
                        real_title = None
                        description = None
                        posted_relative = None
                        posted_calculated = None
                        structured_data = {}
                        detail_failed = False

                        if fetch_details and basic_info.get('url'):
                            result = self._fetch_detail_page(page, basic_info['url'])

                            # SOLD detected on detail page — skip entirely
                            if result[0] == "__SOLD__":
                                skipped += 1
                                print(f"    ⏭️  Skipping SOLD (detail): {basic_info['title'][:50]}...")
                                continue

                            real_title, description, posted_relative, posted_calculated, structured_data = result

                            # Detail fetch failed — we'll still yield with basic info
                            if real_title is None and description is None:
                                detail_failed = True

                            # Use real title from detail page if available
                            if real_title:
                                basic_info['title'] = real_title

                        # Track consecutive detail failures to detect sustained blocking
                        if detail_failed:
                            consecutive_failures += 1
                            if consecutive_failures >= 5:
                                print(f"    🔄 {consecutive_failures} consecutive detail failures, refreshing browser context...")
                                self._close_context()
                                page = self._get_context_and_page()
                                consecutive_failures = 0
                                time.sleep(random.uniform(5.0, 10.0))
                            # Still yield the listing with basic info from the search page
                            print(f"    📋 Yielding with basic info only: {basic_info['title'][:50]}...")
                        else:
                            consecutive_failures = 0

                        # Merge structured data with raw_data
                        raw_data = {
                            'broker_name': basic_info.get('broker_name'),
                            'listing_type': basic_info.get('listing_type'),
                            'posted_date_relative': posted_relative,
                            'structured_data': structured_data,
                            'detail_fetched': not detail_failed,
                        }

                        listing = BusinessListing(
                            id=basic_info['id'],
                            source="seekbusiness",
                            title=basic_info['title'],
                            description=description,
                            price=basic_info.get('price'),
                            revenue=None,  # Not reliably available
                            ebitda=None,   # Not reliably available
                            location=basic_info.get('location'),
                            industry=basic_info.get('industry'),
                            url=basic_info['url'],
                            posted_date=posted_calculated,  # ISO format date
                            raw_data=raw_data
                        )

                        fetched += 1
                        has_desc = "✓" if description else "✗"
                        print(f"    [{fetched}/{count}] {basic_info['title'][:50]} (desc: {has_desc})")
                        yield listing

                    except Exception as e:
                        print(f"    ⚠️  Parse error: {e}")
                        continue

                page_num += 1
                        
        finally:
            self._close_context()
            self._close_browser()
    
    def _build_search_url(self, location: str, radius_km: int) -> str:
        """Build the search URL with location and radius."""
        return f"{self.BASE_URL}/businesses-for-sale/in-{location}?rad={radius_km}"
    
    def _fetch_list_page(self, page: Page, url: str, max_retries: int = 3) -> list:
        """Fetch a single search page and extract listing cards."""
        for attempt in range(1, max_retries + 1):
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_selector('[data-testid="search-listings-result-item"]', timeout=10000)

                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')
                return soup.find_all(attrs={"data-testid": "search-listings-result-item"})

            except Exception as e:
                if attempt < max_retries:
                    backoff = 3.0 * attempt + random.uniform(0, 2.0)
                    print(f"  ❌ Error fetching page (attempt {attempt}/{max_retries}): {e}, retrying in {backoff:.0f}s...")
                    time.sleep(backoff)
                else:
                    print(f"  ❌ Error fetching page after {max_retries} attempts: {e}")
                    return []
    
    def _is_blocked_page(self, title: Optional[str]) -> bool:
        """Check if the page is a block/auth wall instead of real content."""
        if not title:
            return False
        t = title.lower()
        return 'sign in' in t or 'log in' in t or title == 'Verified Businesses'

    # Sentinel to distinguish SOLD listings from failures in _fetch_detail_page
    SOLD_SENTINEL = ("__SOLD__", None, None, None, {})

    def _fetch_detail_page(self, page: Page, detail_url: str, max_retries: int = 3) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], Dict]:
        """
        Fetch detail page and extract title + description + posted date + structured data.

        Retries on transient failures (timeouts, blocked pages) with backoff.

        Returns:
            (title, description, posted_date_relative, posted_date_calculated, structured_data)
            SOLD_SENTINEL if listing is sold
            (None, None, None, None, {}) on failure after retries
        """
        for attempt in range(1, max_retries + 1):
            try:
                # Rate-limit: random delay between requests to avoid being blocked
                delay = random.uniform(1.0, 3.0)
                time.sleep(delay)

                page.goto(detail_url, wait_until="networkidle", timeout=30000)

                # Wait for meaningful content rather than a fixed sleep
                try:
                    page.wait_for_selector('h1', timeout=5000)
                except Exception:
                    pass  # h1 may not exist, continue with what we have

                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')

                # Extract real title from h1 (not the badge from list view)
                title = self._extract_detail_title(soup)

                # Skip SOLD listings (not retryable)
                if title and 'sold' in title.lower():
                    print(f"      ⏭️  SOLD listing detected")
                    return self.SOLD_SENTINEL

                # If we hit a block/auth page, retry with longer backoff
                if self._is_blocked_page(title):
                    if attempt < max_retries:
                        backoff = 5.0 * attempt + random.uniform(0, 3.0)
                        print(f"      🚧 Blocked (attempt {attempt}/{max_retries}), waiting {backoff:.0f}s...")
                        time.sleep(backoff)
                        continue
                    else:
                        print(f"      🚧 Blocked after {max_retries} attempts, using URL title fallback")
                        title = self._extract_title_from_url(detail_url)

                description = self._extract_description(soup)
                posted_relative, posted_calculated = self._extract_posted_date(soup)
                structured_data = self._extract_structured_data(soup)

                return title, description, posted_relative, posted_calculated, structured_data

            except Exception as e:
                if attempt < max_retries:
                    backoff = 3.0 * attempt + random.uniform(0, 2.0)
                    print(f"      ⚠️  Error (attempt {attempt}/{max_retries}): {e}, retrying in {backoff:.0f}s...")
                    time.sleep(backoff)
                else:
                    print(f"      ⚠️  Error fetching detail after {max_retries} attempts: {e}")
                    return None, None, None, None, {}
    
    def _extract_detail_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the real business title from detail page h1."""
        # Try h1 first (most reliable)
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
            # Clean up common suffixes
            title = title.split('|')[0].strip()
            if title and len(title) > 3:
                return title
        
        # Fallback: extract from page title tag
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Format: "Business Name | SEEK Business" or "Business Name | something"
            title = title.split('|')[0].strip()
            # Remove location suffix if present: "Business in Location | ..."
            title = re.sub(r'\s+in\s+[^|]+$', '', title)
            if title and len(title) > 3:
                return title
        
        return None
    
    def _extract_title_from_url(self, url: str) -> Optional[str]:
        """Extract title from URL slug as fallback."""
        # URL format: .../business-listing/slug-title-here/123456
        match = re.search(r'/business-listing/([^/]+)/\d+', url)
        if match:
            slug = match.group(1)
            # Convert slug to title: "business-name-here" -> "Business Name Here"
            words = slug.replace('-', ' ').split()
            # Filter out location codes and clean up
            filtered = [w for w in words if w.lower() not in ['in', 'qld', 'nsw', 'vic', 'wa', 'sa', 'act', 'nt'] or len(w) > 3]
            title = ' '.join(word.capitalize() for word in filtered)
            return title
        return None
    
    def _extract_posted_date(self, soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
        """
        Extract posted date.
        Returns: (relative_date, calculated_iso_date)
        """
        from datetime import datetime, timedelta
        
        page_text = soup.get_text()
        
        # Look for patterns like "6 days ago", "1 day ago", "29 days ago"
        match = re.search(r'(\d+)\s+(day|days|hour|hours|week|weeks|month|months)\s+ago', page_text, re.IGNORECASE)
        if match:
            relative = match.group(0).lower()
            num = int(match.group(1))
            unit = match.group(2).lower().rstrip('s')  # 'days' -> 'day'
            
            # Calculate actual date
            delta = {
                'day': timedelta(days=num),
                'hour': timedelta(hours=num),
                'week': timedelta(weeks=num),
                'month': timedelta(days=num*30),  # Approximate
            }.get(unit, timedelta(days=num))
            
            calculated_date = (datetime.utcnow() - delta).strftime('%Y-%m-%d')
            return relative, calculated_date
        
        return None, None
    
    def _extract_structured_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract structured data from JavaScript variables in the page."""
        import json
        
        structured_data = {}
        html_str = str(soup)
        
        # Extract loopaData
        loopa_match = re.search(r'var loopaData = ({.+?});', html_str, re.DOTALL)
        if loopa_match:
            try:
                # Clean up HTML entities
                json_str = loopa_match.group(1).replace('&amp;', '&').replace('\\u0026', '&')
                loopa_data = json.loads(json_str)
                structured_data['loopa'] = loopa_data
            except json.JSONDecodeError:
                pass
        
        # Extract heapListingData
        heap_match = re.search(r'var heapListingData = ({.+?});', html_str, re.DOTALL)
        if heap_match:
            try:
                json_str = heap_match.group(1).replace('&amp;', '&').replace('\\u0026', '&')
                heap_data = json.loads(json_str)
                structured_data['heap'] = heap_data
            except json.JSONDecodeError:
                pass
        
        # Extract seekDmpData
        dmp_match = re.search(r'var seekDmpData = ({.+?});', html_str, re.DOTALL)
        if dmp_match:
            try:
                json_str = dmp_match.group(1).replace('&amp;', '&').replace('\\u0026', '&')
                dmp_data = json.loads(json_str)
                structured_data['dmp'] = dmp_data
            except json.JSONDecodeError:
                pass
        
        return structured_data
    
    def _parse_price(self, text: str) -> Optional[int]:
        """Parse price from text, handling various formats."""
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Pattern 1: $2 million, $1.5 million, $2m, $1.5m
        million_match = re.search(r'\$\s*(\d+\.?\d*)\s*(million|m\b)', text_lower)
        if million_match:
            try:
                return int(float(million_match.group(1)) * 1_000_000)
            except ValueError:
                pass
        
        # Pattern 2: $475,000 or $475000
        standard_match = re.search(r'\$\s*([\d,]+)', text)
        if standard_match:
            try:
                price_str = standard_match.group(1).replace(',', '')
                return int(price_str)
            except ValueError:
                pass
        
        return None
    
    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        # Method 1: Look for Seek Business specific structure - div.infoItem with h4 "About the Business"
        about_header = soup.find('h4', string=lambda text: text and 'About the Business' in text)
        if about_header:
            info_item = about_header.find_parent('div', class_='infoItem')
            if info_item:
                # Get all text after the h4 header
                content = info_item.get_text(separator=' ', strip=True)
                # Remove the header text
                content = content.replace('About the Business', '', 1).strip()
                if len(content) > 100:
                    return content
        
        # Method 2: Try specific description containers
        selectors = [
            '[data-testid="listing-description"]',
            '[data-testid="description"]',
            '.listing-description',
            '#listing-description',
            '[class*="description" i]',
            'main [class*="content" i]',
            'article',
            '[role="main"]',
            '#sbus-ad-detail-cont',  # Main content container on Seek Business
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(separator=' ', strip=True)
                text = ' '.join(text.split())
                # Filter out template text
                text = self._clean_description(text)
                if 100 < len(text) < 5000:
                    return text
        
        # Fallback: substantial paragraphs, excluding template/alert messages
        paragraphs = []
        exclude_patterns = [
            'all communication is now over to you',
            'thanks for confirming',
            "you'll be one of the first to know",
            'why not make another enquiry',
            'sign in', 'register', 'menu', 'cookie', 'privacy'
        ]
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            text_lower = text.lower()
            if len(text) > 100 and not any(x in text_lower for x in exclude_patterns):
                paragraphs.append(text)
        
        if paragraphs:
            return ' '.join(paragraphs[:3])  # Use top 3 substantial paragraphs
        
        return None
    
    def _clean_description(self, text: str) -> str:
        """Remove template/alert text from description."""
        # Remove common template phrases
        template_phrases = [
            r'All communication is now over to you and the advertiser\. Why not make another enquiry to compare it with a similar business\?',
            r"Thanks for confirming\. You'll be one of the first to know when a new business matches your preferences\.",
            r'NOW UNDER OFFER',
        ]
        import re
        for phrase in template_phrases:
            text = re.sub(phrase, '', text, flags=re.IGNORECASE)
        # Clean up extra whitespace
        text = ' '.join(text.split())
        return text.strip()
    
    def _parse_listing_basic(self, element) -> Optional[Dict[str, Any]]:
        """Parse basic listing info from search result element."""
        try:
            h2_elem = element.find('h2')
            if not h2_elem:
                return None
            
            link_elem = h2_elem.find('a', href=True)
            if not link_elem:
                return None
            
            href = link_elem.get('href', '')
            
            # Extract ID from URL
            match = re.search(r'/business-listing/[^/]+/(\d+)$', href)
            if not match:
                return None
            
            listing_id = f"seek_{match.group(1)}"
            detail_url = href if href.startswith('http') else urljoin(self.BASE_URL, href)
            
            # Title
            title = link_elem.get_text(strip=True)
            if not title:
                title = element.get('aria-label', 'Unknown Business')
            title = title.split('|')[0].strip()
            
            # Broker name
            broker_elem = element.find(attrs={"data-testid": "serp-listing-business-name"})
            broker_name = broker_elem.get_text(strip=True) if broker_elem else None
            
            # Price - handle formats like "$475,000", "$2 million", "$1.5M"
            price = self._parse_price(element.get_text())
            
            # Location
            location_elem = element.find(attrs={"data-testid": "search-result-item-location-breadcrumbs"})
            location = location_elem.get_text(strip=True) if location_elem else None
            
            # Industry
            industry_elem = element.find(attrs={"data-testid": "search-result-item-industry-breadcrumbs"})
            industry = industry_elem.get_text(strip=True).replace('>', ' > ') if industry_elem else None
            
            # Listing type
            listing_type_elem = element.find(attrs={"data-testid": "serp-listing-item-type"})
            listing_type = listing_type_elem.get_text(strip=True) if listing_type_elem else None
            
            return {
                'id': listing_id,
                'title': title,
                'price': price,
                'location': location,
                'industry': industry,
                'url': detail_url,
                'broker_name': broker_name,
                'listing_type': listing_type,
            }
            
        except Exception as e:
            print(f"    Parse error: {e}")
            return None
    
    def get_listing_detail(self, listing_id: str) -> BusinessListing:
        """Fetch full details for a specific listing by ID."""
        numeric_id = listing_id.replace('seek_', '')
        page = self._get_context_and_page()
        
        try:
            search_url = f"{self.BASE_URL}/businesses-for-sale?page=1&id={numeric_id}"
            page.goto(search_url, wait_until="networkidle")
            
            link = page.query_selector(f'a[href*="{numeric_id}"]')
            if link:
                detail_url = link.get_attribute('href')
                if not detail_url.startswith('http'):
                    detail_url = urljoin(self.BASE_URL, detail_url)
                
                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')
                element = soup.find(attrs={"data-testid": "search-listings-result-item"})
                
                if element:
                    basic_info = self._parse_listing_basic(element)
                    if basic_info:
                        real_title, description, posted_relative, posted_calculated, structured_data = self._fetch_detail_page(page, detail_url)
                        
                        if real_title:
                            basic_info['title'] = real_title
                        
                        raw_data = {
                            'broker_name': basic_info.get('broker_name'),
                            'listing_type': basic_info.get('listing_type'),
                            'posted_date_relative': posted_relative,
                            'structured_data': structured_data,
                        }
                        
                        return BusinessListing(
                            id=basic_info['id'],
                            source="seekbusiness",
                            title=basic_info['title'],
                            description=description,
                            price=basic_info.get('price'),
                            revenue=None,
                            ebitda=None,
                            location=basic_info.get('location'),
                            industry=basic_info.get('industry'),
                            url=detail_url,
                            posted_date=posted_calculated,
                            raw_data=raw_data
                        )
            
            raise ValueError(f"Could not find listing with ID {numeric_id}")
            
        finally:
            self._close_context()
            self._close_browser()
    
    def health_check(self) -> bool:
        """Check if Seek Business is accessible."""
        try:
            page = self._get_context_and_page()
            page.goto(self.BASE_URL, timeout=10000)
            title = page.title()
            self._close_context()
            self._close_browser()
            return "business" in title.lower()
        except:
            return False


# Register the fetcher
FetcherRegistry.register(SeekBusinessFetcher())
