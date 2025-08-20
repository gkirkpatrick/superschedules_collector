"""
Pagination detection system for event listing pages.

Uses multiple strategies:
1. CSS selector patterns for common pagination
2. Playwright for JavaScript-based pagination
3. LLM analysis for complex/unusual pagination patterns
"""

import re
import json
import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .pagination_failure_logger import log_pagination_failure

logger = logging.getLogger(__name__)


@dataclass
class PaginationResult:
    """Result from pagination detection."""
    next_urls: List[str]
    pagination_type: str  # 'css', 'javascript', 'llm_detected'
    confidence: float
    total_pages_estimate: Optional[int]
    current_page: Optional[int]
    pattern_used: str


class PaginationDetector:
    """Detects pagination patterns on event listing pages."""
    
    # Common CSS selectors for pagination
    CSS_PATTERNS = [
        # Rel attribute (most reliable)
        "a[rel='next']",
        "link[rel='next']",
        
        # Common class patterns
        ".pagination a:last-child",
        ".pager-next a",
        ".next a",
        ".page-next a",
        
        # Text-based patterns
        "a:contains('Next')",
        "a:contains('next')",
        "a:contains('›')",
        "a:contains('→')",
        "a:contains('>>')",
        
        # Government site patterns
        ".views-more-link a",
        ".pager-item--next a",
        
        # Load more buttons
        ".load-more",
        ".show-more",
        "[data-load-more]",
    ]
    
    # Patterns that suggest infinite scroll
    INFINITE_SCROLL_INDICATORS = [
        "[data-infinite-scroll]",
        ".infinite-scroll",
        "[data-auto-load]",
        ".lazy-load"
    ]
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key
        
    def detect_pagination(self, url: str, html_content: str) -> PaginationResult:
        """
        Detect pagination using multiple strategies.
        
        Returns the best pagination result found.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Strategy 1: Check for iframes with calendar/event content
        iframe_result = self._detect_iframe_pagination(soup, url)
        if iframe_result.next_urls and iframe_result.confidence > 0.8:
            logger.info(f"High-confidence iframe pagination detected: {iframe_result.pattern_used}")
            return iframe_result
        
        # Strategy 2: CSS selector patterns
        css_result = self._detect_css_pagination(soup, url)
        if css_result.next_urls and css_result.confidence > 0.8:
            logger.info(f"High-confidence CSS pagination detected: {css_result.pattern_used}")
            return css_result
            
        # Strategy 3: JavaScript/dynamic content detection
        js_result = self._detect_js_pagination(url)
        if js_result.next_urls and js_result.confidence > 0.7:
            logger.info(f"JavaScript pagination detected: {js_result.pattern_used}")
            return js_result
            
        # Strategy 4: LLM analysis for complex patterns
        if self.openai_api_key:
            llm_result = self._detect_llm_pagination(soup, url)
            if llm_result.next_urls:
                logger.info(f"LLM pagination detected: {llm_result.pattern_used}")
                return llm_result
                
        # Return best result or empty result (including iframe result)
        best_result = max([iframe_result, css_result, js_result], key=lambda r: len(r.next_urls))
        
        if best_result.next_urls:
            return best_result
        else:
            # Log pagination failure for analysis
            context = {
                "strategies_attempted": ["iframe", "css", "javascript"] + (["llm"] if self.openai_api_key else []),
                "iframe_confidence": iframe_result.confidence,
                "css_confidence": css_result.confidence,
                "js_confidence": js_result.confidence,
                "playwright_available": True  # We have playwright, just missing deps
            }
            
            try:
                log_pagination_failure(url, html_content, context)
            except Exception as e:
                logger.warning(f"Failed to log pagination failure: {e}")
            
            return PaginationResult(
                next_urls=[], pagination_type='none', confidence=0.0,
                total_pages_estimate=None, current_page=1, pattern_used='none'
            )
        
    def _detect_iframe_pagination(self, soup: BeautifulSoup, base_url: str) -> PaginationResult:
        """Detect pagination within iframes (especially calendar widgets)."""
        next_urls = []
        pattern_used = 'none'
        confidence = 0.0
        
        # Find iframes that might contain calendars/events
        iframes = soup.find_all('iframe', src=True)
        
        for iframe in iframes:
            iframe_src = iframe.get('src')
            if not iframe_src:
                continue
                
            # Make iframe URL absolute
            iframe_url = urljoin(base_url, iframe_src)
            
            # Check if iframe looks like a calendar/event system
            calendar_indicators = [
                'calendar', 'event', 'schedule', 'booking',
                'libcal', 'springshare', 'assabet', 'evanced'
            ]
            
            if any(indicator in iframe_url.lower() for indicator in calendar_indicators):
                try:
                    logger.info(f"Analyzing iframe calendar: {iframe_url}")
                    
                    # Fetch iframe content
                    response = requests.get(
                        iframe_url, 
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=10
                    )
                    response.raise_for_status()
                    
                    iframe_soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Look for calendar navigation within iframe
                    calendar_nav_patterns = [
                        # Common calendar navigation
                        "a[title*='next']",
                        "a[title*='Next']", 
                        "button[title*='next']",
                        ".next-month",
                        ".calendar-next",
                        "a:contains('›')",
                        "a:contains('→')",
                        "a:contains('Next')",
                        "a:contains('Next Month')",  # Added for Assabet Interactive
                        
                        # LibCal specific patterns
                        ".fc-next-button",
                        ".fc-button-next",
                        
                        # Generic month navigation
                        "[data-action='next']",
                        ".month-next",
                        ".nav-next"
                    ]
                    
                    # First, try simple text-based search for common navigation terms
                    nav_search_terms = [
                        'Next Month', 'next month', 'Next', 'next',
                        '›', '→', '>>', 'forward'
                    ]
                    
                    for search_term in nav_search_terms:
                        for link in iframe_soup.find_all('a', href=True):
                            text = link.get_text(strip=True)
                            if search_term.lower() in text.lower() and len(text) < 50:  # Avoid long text blocks
                                href = link.get('href')
                                if href and not href.startswith('javascript:'):
                                    full_url = urljoin(iframe_url, href)
                                    next_urls.append(full_url)
                                    pattern_used = f'iframe:text_search:{search_term}'
                                    confidence = 0.85
                                    logger.info(f"Found iframe navigation: '{text}' -> {full_url}")
                        
                        if next_urls:
                            break  # Found navigation, stop searching
                    
                    # If text search didn't work, try CSS patterns
                    if not next_urls:
                        for pattern in calendar_nav_patterns:
                            try:
                                nav_links = iframe_soup.select(pattern) if not ':contains(' in pattern else []
                                
                                for link in nav_links:
                                    href = link.get('href')
                                    onclick = link.get('onclick')
                                    data_url = link.get('data-url')
                                    
                                    if href and not href.startswith('javascript:'):
                                        # Standard link
                                        full_url = urljoin(iframe_url, href)
                                        next_urls.append(full_url)
                                        pattern_used = f'iframe:{pattern}'
                                        confidence = 0.85
                                        
                                    elif onclick and 'month' in onclick.lower():
                                        # JavaScript-based month navigation
                                        # Try to extract month parameter or construct next month URL
                                        if 'month=' in iframe_url:
                                            # URL-based month navigation
                                            next_urls.append(self._construct_next_month_url(iframe_url))
                                            pattern_used = f'iframe:js_month_nav'
                                            confidence = 0.75
                                            
                                    elif data_url:
                                        full_url = urljoin(iframe_url, data_url)
                                        next_urls.append(full_url)
                                        pattern_used = f'iframe:data-url'
                                        confidence = 0.8
                                        
                                if next_urls:
                                    break  # Found navigation, stop looking
                                    
                            except Exception as e:
                                logger.debug(f"Calendar nav pattern {pattern} failed: {e}")
                                continue
                            
                    if next_urls:
                        break  # Found pagination in this iframe
                        
                except Exception as e:
                    logger.warning(f"Failed to analyze iframe {iframe_url}: {e}")
                    continue
                    
        return PaginationResult(
            next_urls=next_urls,
            pagination_type='iframe',
            confidence=confidence,
            total_pages_estimate=None,  # Calendars don't usually show total pages
            current_page=None,
            pattern_used=pattern_used
        )
        
    def _construct_next_month_url(self, current_url: str) -> str:
        """Construct next month URL from current calendar URL."""
        # Simple heuristic for month-based calendar URLs
        import datetime
        from urllib.parse import parse_qs, urlsplit, urlunsplit
        
        try:
            parsed = urlsplit(current_url)
            query_params = parse_qs(parsed.query)
            
            # Common month parameter patterns
            if 'month' in query_params:
                current_month = int(query_params['month'][0])
                year = int(query_params.get('year', [datetime.datetime.now().year])[0])
                
                # Calculate next month
                if current_month == 12:
                    next_month, next_year = 1, year + 1
                else:
                    next_month, next_year = current_month + 1, year
                    
                # Update parameters
                query_params['month'] = [str(next_month)]
                query_params['year'] = [str(next_year)]
                
                # Reconstruct URL
                from urllib.parse import urlencode
                new_query = urlencode(query_params, doseq=True)
                return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))
                
        except (ValueError, KeyError, IndexError):
            pass
            
        return current_url  # Return original if we can't construct next month
        
    def _detect_css_pagination(self, soup: BeautifulSoup, base_url: str) -> PaginationResult:
        """Detect pagination using CSS selectors."""
        next_urls = []
        pattern_used = None
        confidence = 0.0
        
        for pattern in self.CSS_PATTERNS:
            try:
                if ':contains(' in pattern:
                    # Handle text-based selectors differently
                    text_pattern = pattern.split(':contains(')[1].rstrip(')')
                    text_pattern = text_pattern.strip("'\"")
                    
                    links = soup.find_all('a', string=re.compile(text_pattern, re.I))
                else:
                    # Regular CSS selector
                    links = soup.select(pattern)
                
                for link in links:
                    href = link.get('href')
                    if href:
                        full_url = urljoin(base_url, href)
                        next_urls.append(full_url)
                        
                if next_urls:
                    pattern_used = pattern
                    confidence = self._calculate_css_confidence(pattern, links)
                    break
                    
            except Exception as e:
                logger.debug(f"CSS pattern {pattern} failed: {e}")
                continue
                
        # Check for infinite scroll indicators
        infinite_scroll = any(soup.select(pattern) for pattern in self.INFINITE_SCROLL_INDICATORS)
        
        # Estimate total pages from numbered pagination
        total_pages = self._estimate_total_pages(soup)
        current_page = self._detect_current_page(soup)
        
        # Check for numbered pagination specifically (like /calendar/2, /calendar/3, etc.)
        if not next_urls:
            numbered_pages = self._detect_numbered_pagination(soup, base_url)
            if numbered_pages:
                next_urls.extend(numbered_pages)
                pattern_used = 'numbered_pagination'
                confidence = 0.9  # High confidence for numbered pagination
        
        return PaginationResult(
            next_urls=next_urls,
            pagination_type='css',
            confidence=confidence,
            total_pages_estimate=total_pages,
            current_page=current_page,
            pattern_used=pattern_used or 'none'
        )
        
    def _detect_js_pagination(self, url: str) -> PaginationResult:
        """Detect JavaScript-based pagination using Playwright."""
        next_urls = []
        pattern_used = 'none'
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Navigate to page
                page.goto(url, timeout=30000)
                page.wait_for_load_state('networkidle')
                
                # Look for next buttons/links that might be JavaScript-powered
                next_selectors = [
                    'button:has-text("Next")',
                    'button:has-text("Load More")',
                    'a:has-text("Next")',
                    '[data-next]',
                    '.next-page',
                    '.load-more-btn'
                ]
                
                for selector in next_selectors:
                    try:
                        elements = page.query_selector_all(selector)
                        for element in elements:
                            # Check if element is visible and clickable
                            if element.is_visible() and element.is_enabled():
                                # Try to get URL from href or data attributes
                                href = element.get_attribute('href')
                                data_url = element.get_attribute('data-url') or element.get_attribute('data-next-url')
                                
                                if href:
                                    next_urls.append(urljoin(url, href))
                                    pattern_used = f'js:{selector}'
                                elif data_url:
                                    next_urls.append(urljoin(url, data_url))
                                    pattern_used = f'js:{selector}[data-url]'
                                    
                    except Exception as e:
                        logger.debug(f"JavaScript selector {selector} failed: {e}")
                        continue
                        
                browser.close()
                
        except Exception as e:
            logger.warning(f"Playwright pagination detection failed: {e}")
            
        confidence = 0.7 if next_urls else 0.0
        
        return PaginationResult(
            next_urls=next_urls,
            pagination_type='javascript',
            confidence=confidence,
            total_pages_estimate=None,
            current_page=None,
            pattern_used=pattern_used
        )
        
    def _detect_llm_pagination(self, soup: BeautifulSoup, base_url: str) -> PaginationResult:
        """Use LLM to detect complex pagination patterns."""
        if not self.openai_api_key:
            return PaginationResult(
                next_urls=[], pagination_type='llm', confidence=0.0,
                total_pages_estimate=None, current_page=None, pattern_used='no_api_key'
            )
            
        # Extract potential pagination links
        all_links = []
        for link in soup.find_all('a', href=True)[:50]:  # Limit to first 50 links
            text = link.get_text(strip=True)
            href = link.get('href')
            classes = ' '.join(link.get('class', []))
            
            all_links.append({
                'text': text,
                'href': href,
                'classes': classes,
                'full_url': urljoin(base_url, href)
            })
            
        if not all_links:
            return PaginationResult(
                next_urls=[], pagination_type='llm', confidence=0.0,
                total_pages_estimate=None, current_page=None, pattern_used='no_links'
            )
            
        # Prepare prompt for LLM
        prompt = self._create_llm_pagination_prompt(all_links, base_url)
        
        try:
            response = self._query_openai(prompt)
            result = self._parse_llm_response(response)
            
            return PaginationResult(
                next_urls=result.get('next_urls', []),
                pagination_type='llm',
                confidence=result.get('confidence', 0.0),
                total_pages_estimate=result.get('total_pages'),
                current_page=result.get('current_page'),
                pattern_used=f"llm:{result.get('reasoning', 'unknown')}"
            )
            
        except Exception as e:
            logger.error(f"LLM pagination detection failed: {e}")
            return PaginationResult(
                next_urls=[], pagination_type='llm', confidence=0.0,
                total_pages_estimate=None, current_page=None, pattern_used=f'error:{str(e)}'
            )
            
    def _create_llm_pagination_prompt(self, links: List[Dict], base_url: str) -> str:
        """Create a prompt for LLM pagination detection."""
        links_json = json.dumps(links[:20], indent=2)  # Limit for token efficiency
        
        return f"""You are analyzing a webpage to find pagination links for an event listing page.

Current URL: {base_url}

Here are the links found on the page:
{links_json}

Return only valid JSON with this schema:
{{
  "next_urls": ["url1", "url2"],  // URLs that lead to next pages of events
  "confidence": 0.0-1.0,          // How confident you are (0.8+ is high confidence)
  "current_page": 1,              // Current page number if detectable
  "total_pages": 10,              // Total pages if detectable (null if unknown)
  "reasoning": "found 'Next' link" // Brief explanation
}}

Look for:
- Links with text like "Next", "More", "→", "›", ">>"
- Numbered pagination (2, 3, 4, etc.)
- "Load More" or "Show More" buttons
- Calendar navigation (next month, etc.)
- Page 2, Page 3 links

Ignore:
- Social media links
- Navigation menu items  
- Footer links
- Unrelated content links

Return null for next_urls if no pagination found."""

    def _query_openai(self, prompt: str) -> str:
        """Query OpenAI API."""
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 500
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"].strip()
        
    def _parse_llm_response(self, response: str) -> Dict:
        """Parse LLM response JSON."""
        try:
            # Clean up potential markdown formatting
            clean_response = response
            if clean_response.startswith('```json'):
                clean_response = clean_response.replace('```json\n', '').replace('\n```', '').strip()
            elif clean_response.startswith('```'):
                clean_response = clean_response.replace('```\n', '').replace('\n```', '').strip()
                
            return json.loads(clean_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Raw response: {response}")
            return {'next_urls': [], 'confidence': 0.0, 'reasoning': 'parse_error'}
            
    def _calculate_css_confidence(self, pattern: str, links: List) -> float:
        """Calculate confidence score for CSS-detected pagination."""
        base_confidence = 0.5
        
        # High confidence patterns
        if 'rel=\'next\'' in pattern:
            base_confidence = 0.95
        elif 'Next' in pattern or 'next' in pattern:
            base_confidence = 0.8
        elif any(symbol in pattern for symbol in ['›', '→', '>>']):
            base_confidence = 0.75
            
        # Adjust based on number of matches (too many might be false positives)
        if len(links) == 1:
            confidence_multiplier = 1.0
        elif len(links) <= 3:
            confidence_multiplier = 0.9
        else:
            confidence_multiplier = 0.6
            
        return min(base_confidence * confidence_multiplier, 1.0)
        
    def _estimate_total_pages(self, soup: BeautifulSoup) -> Optional[int]:
        """Try to estimate total pages from numbered pagination."""
        # Look for numbered pagination links
        page_links = soup.select('.pagination a, .pager a, .page-numbers a')
        
        page_numbers = []
        for link in page_links:
            text = link.get_text(strip=True)
            if text.isdigit():
                page_numbers.append(int(text))
                
        return max(page_numbers) if page_numbers else None
        
    def _detect_current_page(self, soup: BeautifulSoup) -> Optional[int]:
        """Try to detect current page number."""
        # Look for active/current page indicators
        current_selectors = [
            '.pagination .active',
            '.pagination .current',
            '.pager .is-active',
            '.page-numbers.current'
        ]
        
        for selector in current_selectors:
            current = soup.select_one(selector)
            if current:
                text = current.get_text(strip=True)
                if text.isdigit():
                    return int(text)
                    
        return None
        
    def _detect_numbered_pagination(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Detect numbered pagination links (2, 3, 4, etc.)."""
        numbered_urls = []
        
        # Look for links that are just numbers
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True)
            href = link.get('href')
            
            # Check if link text is a number (page number)
            if text.isdigit() and int(text) > 1:  # Skip page 1 (usually current)
                full_url = urljoin(base_url, href)
                numbered_urls.append(full_url)
                logger.info(f"Found numbered pagination: '{text}' -> {full_url}")
                
        # Remove duplicates while preserving order
        seen = set()
        unique_numbered_urls = []
        for url in numbered_urls:
            if url not in seen:
                seen.add(url)
                unique_numbered_urls.append(url)
                
        return unique_numbered_urls


def detect_pagination(url: str, html_content: str, openai_api_key: Optional[str] = None) -> PaginationResult:
    """
    Convenience function to detect pagination on a page.
    
    Args:
        url: The current page URL
        html_content: HTML content of the page
        openai_api_key: OpenAI API key for LLM analysis (optional)
        
    Returns:
        PaginationResult with detected pagination information
    """
    detector = PaginationDetector(openai_api_key)
    return detector.detect_pagination(url, html_content)