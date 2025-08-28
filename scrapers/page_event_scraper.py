"""Page event collection scraper implementing the 5-step process requested in Issue #25."""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

# Removed pagination and API client imports - Django backend handles these now

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def get_openai_api_key() -> str | None:
    """Load OpenAI API key from environment or ~/.secret_keys."""
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    try:
        with open(os.path.expanduser("~/.secret_keys"), "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

# Optimized event extraction prompt with date filtering
EVENT_EXTRACTION_PROMPT = """Return only valid JSON, no markdown or other text.

Schema: {{"source_id": null, "external_id": "url_or_id", "title": "required", "description": "text", "location": "place", "start_time": "2024-01-01T10:00:00-05:00", "end_time": "time", "url": "link", "metadata_tags": ["categories", "event_types", "keywords"]}}

IMPORTANT: Only extract events that are CURRENT or FUTURE. Today is {current_date}. Return null for past events.

Use Eastern timezone. Extract all relevant categories and keywords as tags. Return null if no event or if event is in the past.

Content: {content}
URL: {context_url}"""

def find_event_containing_tags(soup: BeautifulSoup) -> List[Tag]:
    """
    Step 1: Find tags that likely contain events by looking for common patterns.
    
    Returns a list of BeautifulSoup Tag objects that appear to contain event information.
    """
    event_containers = []
    
    # More specific selectors that often contain individual events
    # Order matters - more specific selectors first
    event_selectors = [
        # Specific event patterns found on government sites
        'article[class*="calendar"]',
        'div[class*="calendar-item"]',
        'div[class*="event-item"]',
        '.views-row',
        '.node-event',
        # Class-based selectors for events
        '[class*="event"]:not(body):not(html)',
        '[class*="calendar"]:not(body):not(html)', 
        '[class*="schedule"]:not(body):not(html)',
        '[class*="program"]:not(body):not(html)',
        '[class*="activity"]:not(body):not(html)',
        # ID-based selectors
        '[id*="event"]',
        '[id*="calendar"]',
        '[id*="schedule"]',
        # Semantic elements but only if they have date/time content
        'article',
        'section',
        # List items that might contain events
        'li',
    ]
    
    for selector in event_selectors:
        elements = soup.select(selector)
        for element in elements:
            # Skip if we already have this element or a parent/child of it
            if any(element == existing or element in existing.descendants or existing in element.descendants 
                   for existing in event_containers):
                continue
                
            # Filter by content - look for date/time patterns and size
            text = element.get_text().lower()
            text_length = len(text.strip())
            
            # Skip very large elements (likely page containers) or very small ones
            if text_length > 5000 or text_length < 50:
                continue
                
            if _contains_datetime_patterns(text):
                event_containers.append(element)
    
    return event_containers

def _contains_datetime_patterns(text: str) -> bool:
    """Check if text contains patterns suggesting date/time information."""
    patterns = [
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # dates like 12/25/2024
        r'\b\d{1,2}:\d{2}\s*(am|pm|AM|PM)?\b',  # times like 2:30 PM
        r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
        r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
        r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\b(mon|tue|wed|thu|fri|sat|sun)\b',
        r'\b\d{1,2}(st|nd|rd|th)\b',  # ordinal numbers like 1st, 2nd
    ]
    
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

def _remove_nested_elements(elements: List[Tag]) -> List[Tag]:
    """Remove elements that are nested inside other elements in the list."""
    result = []
    for element in elements:
        is_nested = False
        for other in elements:
            if element != other and element in other.descendants:
                is_nested = True
                break
        if not is_nested:
            result.append(element)
    return result

def extract_relevant_sections(event_tags: List[Tag]) -> List[str]:
    """
    Step 2: Extract clean text content from event-containing tags.
    
    Strips out scripts, styles, and other non-content elements.
    """
    sections = []
    
    for tag in event_tags:
        # Remove script and style elements
        for script in tag(["script", "style", "noscript"]):
            script.decompose()
        
        # Get clean text content
        text = tag.get_text(separator='\n', strip=True)
        
        # Only include sections with meaningful content
        if len(text.strip()) > 50:  # Minimum content threshold
            sections.append(text)
    
    return sections

def process_section_with_llm(section: str, source_url: str, section_html: Optional[Tag] = None) -> Optional[dict[str, Any]]:
    """
    Step 3: Process a text section with OpenAI to extract event JSON.
    
    Returns None if no valid event is found or if API call fails.
    """
    api_key = get_openai_api_key()
    if not api_key:
        logger.warning("OPENAI_API_KEY not set, cannot process with LLM")
        return None
    
    # Look for event URLs in the HTML if available
    event_url = None
    if section_html:
        # Look for links in the section
        links = section_html.find_all('a', href=True)
        for link in links:
            href = link.get('href')
            # Look for event detail links (skip mailto and tel links)
            if href and not href.startswith(('mailto:', 'tel:')):
                link_text = link.get_text(strip=True).lower()
                # Prefer links with "event details" or similar text
                if ('event' in link_text and 'detail' in link_text) or \
                   ('event website' in link_text) or \
                   ('/node/' in href):  # Boston.gov event detail pages
                    event_url = urljoin(source_url, href)
                    break
        
        # If no specific event link found, try any non-email/phone link
        if not event_url:
            for link in links:
                href = link.get('href')
                if href and not href.startswith(('mailto:', 'tel:', '#')):
                    event_url = urljoin(source_url, href)
                    break
    
    # Include more context in the content for better date extraction
    enhanced_content = section
    if section_html:
        # Look for date headers above this section
        previous_siblings = []
        current = section_html.previous_sibling
        count = 0
        while current and count < 3:  # Check 3 previous elements
            if hasattr(current, 'get_text'):
                sibling_text = current.get_text(strip=True)
                if sibling_text and _contains_datetime_patterns(sibling_text.lower()):
                    previous_siblings.append(sibling_text)
            current = current.previous_sibling
            count += 1
        
        if previous_siblings:
            enhanced_content = "\n".join(reversed(previous_siblings)) + "\n" + section
    
    from datetime import datetime, timezone
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prompt = EVENT_EXTRACTION_PROMPT.format(
        content=enhanced_content, 
        context_url=source_url,
        current_date=current_date
    )
    
    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        # Log the prompt for testing with local LLMs
        logger.info(f"=== PROMPT BEING SENT TO LLM ===")
        logger.info(f"Model: {OPENAI_MODEL}")
        logger.info(f"Prompt: {prompt}")
        logger.info(f"=== END PROMPT ===")
        
        response = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        
        # Clean up potential markdown-wrapped JSON
        clean_content = content
        if content.startswith('```json'):
            clean_content = content.replace('```json\n', '').replace('\n```', '').strip()
        elif content.startswith('```'):
            clean_content = content.replace('```\n', '').replace('\n```', '').strip()
        
        # Try to parse as JSON
        event_data = json.loads(clean_content)
        
        # Return None if LLM determined no event was present
        if event_data is None:
            return None
            
        # Ensure required fields and set defaults
        if not event_data.get("title"):
            return None
            
        # Set event URL - prioritize detected URL over LLM response
        if event_url:
            event_data["url"] = event_url
        elif not event_data.get("url"):
            event_data["url"] = source_url
            
        # Ensure metadata_tags exists
        if "metadata_tags" not in event_data:
            event_data["metadata_tags"] = []
            
        return event_data
        
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to process section with LLM: {e}")
        return None

def find_urls_in_section(section: str, base_url: str) -> List[str]:
    """
    Step 4 helper: Extract URLs from a text section.
    """
    # This is a simplified version - in practice you might want to 
    # parse the original HTML to find actual href attributes
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, section)
    
    # Also look for relative URLs if we have the original HTML
    return list(set(urls))

def detect_iframe_calendar(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """
    Detect if the page contains an iframe that likely holds calendar/event content.
    
    Returns the iframe URL if found, None otherwise.
    """
    iframes = soup.find_all('iframe')
    
    for iframe in iframes:
        src = iframe.get('src')
        if not src:
            continue
            
        # Convert to absolute URL
        iframe_url = urljoin(base_url, src)
        
        # Check if iframe likely contains calendar/events
        iframe_indicators = ['calendar', 'event', 'schedule', 'booking']
        src_lower = src.lower()
        
        if any(indicator in src_lower for indicator in iframe_indicators):
            logger.info(f"Found potential calendar iframe: {iframe_url}")
            return iframe_url
    
    return None

def scrape_page_events(
    url: str, 
    source_id: Optional[int] = None,
    max_depth: int = 2,
    visited_urls: Optional[Set[str]] = None,
    follow_pagination: bool = True
) -> List[dict[str, Any]]:
    """
    Main function implementing the 5-step page event collection process with pagination support.
    
    Args:
        url: URL to scrape
        source_id: Optional source ID for the events
        max_depth: Maximum recursion depth for following URLs
        visited_urls: Set of already visited URLs to avoid loops
        follow_pagination: Whether to detect and follow pagination links
        
    Returns:
        List of extracted events
    """
    if visited_urls is None:
        visited_urls = set()
    
    if url in visited_urls or max_depth <= 0:
        return []

    visited_urls.add(url)
    events = []
    api_key = get_openai_api_key()
    
    try:
        # Fetch the page
        response = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Step 1: Find tags that likely contain events
        event_tags = find_event_containing_tags(soup)
        
        # Step 2 & 3: Process each event tag directly (keeping HTML context)
        for event_tag in event_tags:
            # Extract clean text
            for script in event_tag(["script", "style", "noscript"]):
                script.decompose()
            
            section = event_tag.get_text(separator='\n', strip=True)
            
            # Only process sections with meaningful content
            if len(section.strip()) < 50:
                continue
            
            # Step 3: Try to extract event JSON with LLM (passing HTML context)
            event_data = process_section_with_llm(section, url, event_tag)
            
            if event_data:
                # Step 5: Valid event found - set source_id and collect
                if source_id is not None:
                    event_data["source_id"] = source_id
                events.append(event_data)
            else:
                # Step 4: No valid event - look for URLs in this section
                if max_depth > 1:
                    section_urls = find_urls_in_section(section, url)
                    for section_url in section_urls:
                        # Recursively process URLs found in failed sections
                        recursive_events = scrape_page_events(
                            section_url, 
                            source_id, 
                            max_depth - 1, 
                            visited_urls,
                            follow_pagination=False  # Don't follow pagination for recursive URL extraction
                        )
                        events.extend(recursive_events)
        
        # Pagination handling removed - Django backend manages this now

        # Enhanced Step 4: If no events found, check for calendar iframes
        if not events and max_depth > 0:
            iframe_url = detect_iframe_calendar(soup, url)
            if iframe_url and iframe_url not in visited_urls:
                logger.info(f"No events found on main page, trying iframe: {iframe_url}")
                iframe_events = scrape_page_events(
                    iframe_url, 
                    source_id, 
                    max_depth - 1, 
                    visited_urls,
                    follow_pagination=follow_pagination
                )
                events.extend(iframe_events)
                
                if iframe_events:
                    logger.info(f"Successfully extracted {len(iframe_events)} events from iframe")
    
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
    
    return events

# scrape_and_save_events removed - Django backend handles saving now