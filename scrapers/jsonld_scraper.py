"""Scrape JSON-LD event data from webpages."""
from __future__ import annotations

import json
from typing import Any, List

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .utils import make_external_id, to_iso_datetime


def scrape_events_from_jsonld(url: str, source_id: int = None) -> List[dict[str, Any]]:
    """Fetch a page and extract events described in JSON-LD.

    This scraper also follows a single iframe when no JSON-LD is found on the
    initial page, which is common for sites that embed external calendars.

    Args:
        url: Page URL containing JSON-LD event data.
        source_id: Numeric source identifier to include on each event.

    Returns:
        A list of event dictionaries matching the API schema.
    """

    def _fetch(url_to_fetch: str) -> BeautifulSoup:
        """Return a BeautifulSoup for ``url_to_fetch`` with a browser UA."""
        resp = requests.get(
            url_to_fetch,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def _parse(soup: BeautifulSoup, base_url: str) -> List[dict[str, Any]]:
        events: List[dict[str, Any]] = []
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                # Clean HTML entities from JSON-LD content
                json_content = tag.string or ""
                json_content = json_content.replace('&#039;', "'").replace('&quot;', '"').replace('&amp;', '&')
                data = json.loads(json_content)
            except json.JSONDecodeError:
                continue

            for item in _extract_event_objects(data):
                start_raw = item.get("startDate")
                
                # Handle different time field formats
                start_time = item.get("startTime") or item.get("doorTime")
                if start_raw and "T" not in start_raw and start_time:
                    start_raw = f"{start_raw}T{start_time}"
                start = to_iso_datetime(start_raw)

                end_raw = item.get("endDate")
                end_time = item.get("endTime")
                
                # Calculate end time from duration if available
                if not end_time and item.get("duration") and start_raw:
                    duration_str = item.get("duration")
                    if duration_str and duration_str.startswith("PT") and "S" in duration_str:
                        # Parse ISO 8601 duration (e.g., "PT1800S" = 1800 seconds)
                        seconds = int(duration_str.replace("PT", "").replace("S", ""))
                        from datetime import datetime, timedelta
                        if start_raw and "T" in start_raw:
                            try:
                                start_dt = datetime.fromisoformat(start_raw.replace("+00:00", ""))
                                end_dt = start_dt + timedelta(seconds=seconds)
                                end_raw = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
                            except:
                                pass
                
                if end_raw and "T" not in end_raw and end_time:
                    end_raw = f"{end_raw}T{end_time}"
                elif not end_raw and end_time and start_raw:
                    start_date = start_raw.split("T")[0]
                    end_raw = f"{start_date}T{end_time}"
                end = to_iso_datetime(end_raw, end=(end_raw is not None and "T" not in end_raw))
                ext_id = item.get("@id") or item.get("url")
                if not ext_id:
                    ext_id = make_external_id(base_url, item.get("name", ""), start or "")

                title = item.get("name", "")
                event_url = item.get("url")
                if not event_url:
                    event_url = _find_url_for_title(soup, title, base_url) or base_url

                events.append(
                    {
                        "source_id": source_id,
                        "external_id": ext_id,
                        "title": title,
                        "description": item.get("description") or "",
                        "location": _parse_location(item.get("location")),
                        "start_time": start,
                        "end_time": end,
                        "url": event_url,
                        # Schema.org fields
                        "organizer": _extract_organizer(item.get("organizer")),
                        "event_status": item.get("eventStatus", ""),
                        "event_attendance_mode": item.get("eventAttendanceMode", ""),
                    }
                )
        return events

    soup = _fetch(url)
    events = _parse(soup, url)

    # Check for iframe (common for embedded calendars like Needham Library)
    iframe = soup.find("iframe")
    iframe_url = None
    if iframe and iframe.get("src"):
        iframe_url = urljoin(url, iframe["src"])
        print(f"Found iframe: {iframe_url}")
        
        try:
            # Try iframe with Playwright for better compatibility
            iframe_events = _fetch_iframe_with_playwright(iframe_url, source_id)
            if iframe_events:
                print(f"Successfully scraped {len(iframe_events)} events from iframe")
                events.extend(iframe_events)
        except Exception as e:
            print(f"Playwright iframe scraping failed: {e}")
            
            # Fallback to simple requests for iframe
            try:
                iframe_soup = _fetch(iframe_url)
                iframe_events = _parse(iframe_soup, iframe_url)
                if iframe_events:
                    print(f"Fallback iframe scraping found {len(iframe_events)} events")
                    events.extend(iframe_events)
            except Exception as e:
                print(f"Simple iframe scraping also failed: {e}")

    # Try calendar pagination if URL looks like a calendar (this is where month-by-month happens)
    if _is_calendar_url(url) or (iframe_url and _is_calendar_url(iframe_url)):
        calendar_url = iframe_url if iframe_url and _is_calendar_url(iframe_url) else url
        print(f"Attempting calendar pagination on: {calendar_url}")
        try:
            calendar_events = scrape_calendar_with_pagination(calendar_url, source_id)
            if calendar_events:
                print(f"Calendar pagination found {len(calendar_events)} additional events")
                # Add pagination events to any iframe events we already found
                events.extend(calendar_events)
        except Exception as e:
            print(f"Calendar pagination failed: {e}")
    
    return events


def _fetch_iframe_with_playwright(iframe_url: str, source_id: int = None) -> List[dict[str, Any]]:
    """Fetch iframe content using Playwright for better compatibility."""
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Navigate to iframe URL
        page.goto(iframe_url, timeout=30000)
        
        # Wait for content to load
        page.wait_for_timeout(2000)
        
        # Get page content
        content = page.content()
        browser.close()
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(content, "html.parser")
        events = []
        
        # Parse JSON-LD from the page
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                # Clean HTML entities from JSON-LD content
                json_content = tag.string or ""
                # Basic HTML entity cleaning for common issues
                json_content = json_content.replace('&#039;', "'").replace('&quot;', '"').replace('&amp;', '&')
                data = json.loads(json_content)
                for item in _extract_event_objects(data):
                    # Process event data (similar to _parse function)
                    start_raw = item.get("startDate")
                    start_time = item.get("startTime") or item.get("doorTime")
                    if start_raw and "T" not in start_raw and start_time:
                        start_raw = f"{start_raw}T{start_time}"
                    start = to_iso_datetime(start_raw)

                    end_raw = item.get("endDate")
                    end_time = item.get("endTime")
                    if end_raw and "T" not in end_raw and end_time:
                        end_raw = f"{end_raw}T{end_time}"
                    end = to_iso_datetime(end_raw, end=(end_raw is not None and "T" not in end_raw))
                    
                    ext_id = item.get("@id") or item.get("url")
                    if not ext_id:
                        ext_id = make_external_id(iframe_url, item.get("name", ""), start or "")

                    title = item.get("name", "")
                    event_url = item.get("url") or iframe_url

                    events.append({
                        "source_id": source_id,
                        "external_id": ext_id,
                        "title": title,
                        "description": item.get("description") or "",
                        "location": _parse_location(item.get("location")),
                        "start_time": start,
                        "end_time": end,
                        "url": event_url,
                        # Schema.org fields
                        "organizer": _extract_organizer(item.get("organizer")),
                        "event_status": item.get("eventStatus", ""),
                        "event_attendance_mode": item.get("eventAttendanceMode", ""),
                    })
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error parsing iframe JSON-LD: {e}")
                continue
                
        return events


def _is_calendar_url(url: str) -> bool:
    """Check if URL appears to be a calendar that might support pagination."""
    calendar_indicators = ['/calendar/', '/events/', 'assabetinteractive.com']
    return any(indicator in url.lower() for indicator in calendar_indicators)


def scrape_calendar_with_pagination(base_url: str, source_id: int = None) -> List[dict[str, Any]]:
    """Scrape a calendar across multiple months to get future events."""
    from datetime import datetime, timedelta
    import re
    import requests
    from bs4 import BeautifulSoup
    
    # Helper functions (recreate since they're nested in main function)
    def _fetch_page(url_to_fetch: str) -> BeautifulSoup:
        """Return a BeautifulSoup for ``url_to_fetch`` with a browser UA and shorter timeout."""
        resp = requests.get(
            url_to_fetch,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,  # Reduced timeout to prevent hanging
        )
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def _parse_page(soup: BeautifulSoup, base_url: str) -> List[dict[str, Any]]:
        events: List[dict[str, Any]] = []
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                # Clean HTML entities from JSON-LD content
                json_content = tag.string or ""
                json_content = json_content.replace('&#039;', "'").replace('&quot;', '"').replace('&amp;', '&')
                data = json.loads(json_content)
                event_objects = _extract_event_objects(data)
                for item in event_objects:
                    # Handle simple calendar dates (YYYY-MM-DD format)
                    start_date_str = item.get("startDate", "")
                    end_date_str = item.get("endDate", "")
                    
                    if not start_date_str:
                        continue
                    
                    # Convert dates to ISO format, handling time fields
                    try:
                        if len(start_date_str) == 10 and start_date_str.count('-') == 2:
                            # Simple YYYY-MM-DD format - check for time fields
                            start_time = item.get("startTime") or item.get("doorTime")
                            end_time = item.get("endTime")
                            
                            if start_time:
                                start = f"{start_date_str}T{start_time}+00:00"
                            else:
                                start = f"{start_date_str}T00:00:00+00:00"
                            
                            # Calculate end time from duration or use end_time
                            if not end_time and item.get("duration"):
                                duration_str = item.get("duration")
                                if duration_str and duration_str.startswith("PT") and "S" in duration_str:
                                    # Parse ISO 8601 duration (e.g., "PT1800S" = 1800 seconds)
                                    try:
                                        seconds = int(duration_str.replace("PT", "").replace("S", ""))
                                        from datetime import datetime, timedelta
                                        start_dt = datetime.fromisoformat(start.replace("+00:00", ""))
                                        end_dt = start_dt + timedelta(seconds=seconds)
                                        end = end_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                                    except:
                                        end = f"{end_date_str}T23:59:59+00:00" if end_date_str else f"{start_date_str}T23:59:59+00:00"
                                else:
                                    end = f"{end_date_str}T23:59:59+00:00" if end_date_str else f"{start_date_str}T23:59:59+00:00"
                            elif end_time:
                                end_date = end_date_str or start_date_str
                                end = f"{end_date}T{end_time}+00:00"
                            else:
                                end = f"{end_date_str}T23:59:59+00:00" if end_date_str else f"{start_date_str}T23:59:59+00:00"
                        else:
                            # Try the complex datetime utility for other formats
                            start, end = to_iso_datetime(start_date_str, end_date_str)
                            if not start:
                                continue
                    except Exception as e:
                        print(f"Date parsing error for {start_date_str}: {e}")
                        continue

                    ext_id = item.get("@id") or item.get("url")
                    if not ext_id:
                        ext_id = make_external_id(base_url, item.get("name", ""), start or "")

                    title = item.get("name", "")
                    event_url = item.get("url")
                    if not event_url:
                        event_url = _find_url_for_title(soup, title, base_url) or base_url

                    events.append(
                        {
                            "source_id": source_id,
                            "external_id": ext_id,
                            "title": title,
                            "description": item.get("description") or "",
                            "location": _parse_location(item.get("location")),
                            "start_time": start,
                            "end_time": end,
                            "url": event_url,
                            # Schema.org fields
                            "organizer": _extract_organizer(item.get("organizer")),
                            "event_status": item.get("eventStatus", ""),
                            "event_attendance_mode": item.get("eventAttendanceMode", ""),
                        }
                    )
            except (json.JSONDecodeError, KeyError, AttributeError) as e:
                print(f"Error parsing JSON-LD: {e}")
                continue
        return events
    
    all_events = []
    
    # Get current date and calculate next 30 days (more reasonable scope)
    today = datetime.now()
    end_date = today + timedelta(days=30)
    
    # Generate month URLs - start with current month, then next month
    months_to_check = []
    current_month = today.replace(day=1)
    
    for i in range(2):  # Check current month + next month only
        month_date = current_month + timedelta(days=32 * i)  # Move to next month
        month_date = month_date.replace(day=1)  # First of month
        
        # Format: "2025-october", "2025-november", etc.
        month_str = month_date.strftime("%Y-%B").lower()
        months_to_check.append(month_str)
    
    print(f"Checking months: {months_to_check}")
    
    # Try each month URL with timeouts
    for month_str in months_to_check:
        try:
            # Build month-specific URL
            if any(f"/{existing_month}/" in base_url for existing_month in ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]):
                # Extract base URL without month specification
                calendar_base = base_url.split("/202")[0] + "/"
                month_url = f"{calendar_base.rstrip('/')}/{month_str}/"
            else:
                month_url = f"{base_url.rstrip('/')}/{month_str}/"
            
            print(f"Fetching calendar events for {month_str}: {month_url}")
            
            # Fetch and parse this month's events with timeout
            try:
                month_soup = _fetch_page(month_url)
                month_events = _parse_page(month_soup, month_url)
                
                if month_events:
                    # Filter events to only include future events within 30 days
                    filtered_events = []
                    for event in month_events:
                        try:
                            event_date_str = event.get('start_time', '')
                            if event_date_str:
                                # Parse date (handle various formats)
                                event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
                                event_date_naive = event_date.replace(tzinfo=None)
                                
                                # Include both past and future events from this month for better coverage
                                # But prioritize future events
                                if event_date_naive >= today - timedelta(days=7):  # Include recent past events too
                                    filtered_events.append(event)
                            else:
                                # Include events without clear dates
                                filtered_events.append(event)
                        except (ValueError, TypeError) as e:
                            # If we can't parse the date, include the event anyway
                            filtered_events.append(event)
                    
                    all_events.extend(filtered_events)
                    print(f"Added {len(filtered_events)} events from {month_str}")
                    
                    # If we found good events in this month, continue to next
                    if len(filtered_events) > 10:  # Good month, likely to find more
                        continue
                else:
                    print(f"No events found for {month_str}")
                    
            except requests.exceptions.Timeout:
                print(f"Timeout fetching {month_str}, skipping")
                continue
            except Exception as fetch_error:
                print(f"Error fetching {month_str}: {fetch_error}")
                continue
            
        except Exception as e:
            print(f"Failed to process month {month_str}: {e}")
            continue
    
    print(f"Total calendar events collected: {len(all_events)}")
    return all_events


def _extract_event_objects(data: Any) -> List[dict[str, Any]]:
    """Return event dicts from a JSON-LD blob."""
    items: List[dict[str, Any]] = []

    if isinstance(data, list):
        for obj in data:
            if isinstance(obj, dict) and obj.get("@type") == "Event":
                items.append(obj)
    elif isinstance(data, dict):
        if data.get("@type") == "Event":
            items.append(data)
        elif isinstance(data.get("@graph"), list):
            for obj in data["@graph"]:
                if isinstance(obj, dict) and obj.get("@type") == "Event":
                    items.append(obj)

    return items


def _extract_organizer(organizer: Any) -> str:
    """Extract organizer name from Schema.org organizer data."""
    if isinstance(organizer, dict):
        return organizer.get("name", "")
    if isinstance(organizer, str):
        return organizer
    return ""


def _parse_location(location: Any) -> Any:
    """Extract location data, preserving Schema.org Place objects when available."""
    if isinstance(location, dict):
        # Check if this is a Schema.org Place object
        if location.get("@type") == "Place":
            # Preserve the full Place object for rich location data
            return location
        else:
            # Simple dict, convert to string
            return location.get("name") or location.get("address", "")
    if isinstance(location, list) and location:
        # Handle array of location objects, take the first one
        first_location = location[0]
        if isinstance(first_location, dict):
            # Check if first item is a Schema.org Place
            if first_location.get("@type") == "Place":
                return first_location
            else:
                return first_location.get("name") or first_location.get("address", "")
    if isinstance(location, str):
        return location
    return ""


def _find_url_for_title(soup: BeautifulSoup, title: str, base_url: str) -> str | None:
    """Search ``soup`` for an anchor matching ``title`` and return its href."""
    if not title:
        return None
    title_lower = title.strip().lower()
    for a_tag in soup.find_all("a"):
        text = a_tag.get_text(strip=True).lower()
        if title_lower in text:
            href = a_tag.get("href")
            if href:
                return urljoin(base_url, href)
    return None
