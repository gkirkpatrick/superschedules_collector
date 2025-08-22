"""Extract events from rendered webpage text via OpenAI's structured output API."""
from __future__ import annotations

from typing import Any, List

import requests
from openai import APIStatusError, OpenAI
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from .utils import make_external_id, to_iso_datetime

client = OpenAI()


class HintDiscovery(BaseModel):
    event_containers: List[str] = Field(default_factory=list, description="CSS selectors for elements that contain individual events")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0 for the discovered selectors")
    reasoning: str = Field(description="Brief explanation of why these selectors were chosen")


class Event(BaseModel):
    external_id: str | None = None
    title: str
    description: str | None = None
    start: str
    end: str | None = None
    timezone: str | None = None
    location: str | None = None
    organizer: str | None = None
    price: str | None = None
    url: str | None = None


class Events(BaseModel):
    source: str | None = None
    events: List[Event] = Field(default_factory=list)

SYSTEM_PROMPT = (
    "You extract events from the text content of arbitrary webpages.\n"
    "- Output *only* fields defined by the schema.\n"
    "- Normalize dates to ISO 8601; if only a day is given, use YYYY-MM-DD.\n"
    "- If timezone is implied by the venue or page, include it (IANA tz).\n"
    "- Include the canonical event URL when present.\n"
    "- Include external_id when a stable ID (like a URL) exists."
)

HINT_DISCOVERY_PROMPT = (
    "You analyze HTML structure to find CSS selectors for event containers.\n"
    "Look for repeating elements that likely contain individual events.\n"
    "Focus on elements with classes/IDs that suggest events, cards, items, etc.\n"
    "Return specific CSS selectors that would target event container elements.\n"
    "Be conservative - only suggest selectors you're confident about."
)


def discover_event_hints(url: str) -> dict:
    """Use LLM to analyze page HTML and discover event container selectors."""
    target = _discover_iframe(url) or url
    
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(user_agent="Mozilla/5.0")
        page.goto(target, wait_until="domcontentloaded")
        
        if target == url:
            iframe_el = page.query_selector("iframe")
            if iframe_el:
                src = iframe_el.get_attribute("src")
                if src:
                    target = urljoin(url, src)
                    page.goto(target, wait_until="networkidle")
        else:
            page.wait_for_load_state("networkidle")
        
        # Wait for dynamic content to load
        page.wait_for_timeout(3000)
        
        # Get HTML structure but limit size for LLM processing
        html_content = page.content()
        browser.close()
    
    # Truncate HTML if too large (keep structure but limit tokens)
    if len(html_content) > 50000:
        soup = BeautifulSoup(html_content, 'html.parser')
        # Remove script and style tags entirely
        for tag in soup(['script', 'style']):
            tag.decompose()
        # Keep only the first 50k chars of cleaned HTML
        html_content = str(soup)[:50000]
    
    try:
        resp = client.responses.parse(
            model="o4-mini",
            reasoning={"effort": "medium"},
            input=[
                {"role": "system", "content": HINT_DISCOVERY_PROMPT},
                {"role": "user", "content": f"URL: {url}\n\nHTML_STRUCTURE:\n{html_content}"},
            ],
            text_format=HintDiscovery,
        )
        result = resp.output_parsed.model_dump()
        return {"event_containers": result["event_containers"]}
    except APIStatusError as exc:
        if exc.response.status_code == 429:
            raise RuntimeError("OpenAI API returned status 429: out of credits") from exc
        raise
    except Exception:
        # Fallback to empty hints on any error
        return {"event_containers": []}


def _discover_iframe(url: str) -> str | None:
    """Return iframe source URL for ``url`` if one exists."""
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    iframe = soup.find("iframe")
    if iframe and iframe.get("src"):
        return urljoin(url, iframe["src"])
    return None


def fetch_rendered_text(url: str, hints: dict = None) -> str:
    """Return rendered text content for ``url`` or its iframe."""
    hints = hints or {}
    target = _discover_iframe(url) or url
    
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(user_agent="Mozilla/5.0")
        page.goto(target, wait_until="domcontentloaded")
        if target == url:
            iframe_el = page.query_selector("iframe")
            if iframe_el:
                src = iframe_el.get_attribute("src")
                if src:
                    target = urljoin(url, src)
                    page.goto(target, wait_until="networkidle")
        else:
            page.wait_for_load_state("networkidle")

        # Remove common noise elements
        page.evaluate("const h=document.querySelector('header'); if(h) h.remove();")
        page.evaluate("const f=document.querySelector('footer'); if(f) f.remove();")
        page.evaluate("const n=document.querySelector('nav'); if(n) n.remove();")
        
        # Remove scripts and styles for cleaner content
        page.evaluate("""
            document.querySelectorAll('script, style').forEach(el => el.remove());
        """)
        
        # If we have event container hints, extract only those
        event_containers = hints.get('event_containers', [])
        if event_containers:
            # Wait a bit longer for dynamic content
            page.wait_for_timeout(3000)
            
            chunks = []
            for selector in event_containers:
                elements = page.query_selector_all(selector)
                for element in elements:
                    chunk_text = element.inner_text().strip()
                    if chunk_text and len(chunk_text) > 50:  # Skip tiny chunks
                        chunks.append(chunk_text)
            
            if chunks:
                browser.close()
                return "\n\n---EVENT-CHUNK---\n\n".join(chunks)
        
        # Fallback to full page text if no specific containers found
        text = page.evaluate("document.body.innerText")
        browser.close()
    return text.strip()


def parse_events(url: str, hints: dict = None) -> dict[str, Any]:
    """Use OpenAI to parse events from ``url`` into the structured schema."""
    page_text = fetch_rendered_text(url, hints)
    if not page_text or len(page_text) < 200:
        return {"source": url, "events": []}

    try:
        resp = client.responses.parse(
            model="o4-mini",
            reasoning={"effort": "low"},
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"URL: {url}\n\nPAGE_TEXT:\n{page_text[:120000]}"},
            ],
            text_format=Events,
        )
    except APIStatusError as exc:  # pragma: no cover - network errors
        if exc.response.status_code == 429:
            raise RuntimeError(
                "OpenAI API returned status 429: there's a good chance the account is out of money."
            ) from exc
        raise
    data = resp.output_parsed.model_dump()
    data["source"] = data.get("source") or url
    return data


def extract_event_urls(url: str, hints: dict = None) -> List[str]:
    """Extract individual event URLs from a calendar page using hints."""
    target = _discover_iframe(url) or url
    
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(user_agent="Mozilla/5.0")
        page.goto(target, wait_until="domcontentloaded")
        
        if target == url:
            iframe_el = page.query_selector("iframe")
            if iframe_el:
                src = iframe_el.get_attribute("src")
                if src:
                    target = urljoin(url, src)
                    page.goto(target, wait_until="networkidle")
        else:
            page.wait_for_load_state("networkidle")
        
        page.wait_for_timeout(3000)
        
        # Look for links within event containers
        event_containers = hints.get('event_containers', []) if hints else []
        urls = []
        
        if event_containers:
            for selector in event_containers:
                elements = page.query_selector_all(f"{selector} a")
                for element in elements:
                    href = element.get_attribute("href")
                    if href:
                        full_url = urljoin(target, href)
                        if full_url not in urls:  # Avoid duplicates
                            urls.append(full_url)
        
        browser.close()
    return urls


def scrape_events_from_llm(url: str, source_id: int = None, hints: dict = None, auto_discover_hints: bool = False, follow_event_urls: bool = False) -> List[dict[str, Any]]:
    """Fetch ``url`` and convert extracted events to the API schema."""
    # If no hints provided but auto-discovery is enabled, try to discover them
    if not hints and auto_discover_hints:
        print(f"Auto-discovering event container hints for {url}...")
        try:
            hints = discover_event_hints(url)
            if hints.get("event_containers"):
                print(f"Discovered hints: {hints['event_containers']}")
            else:
                print("No suitable event containers discovered")
        except Exception as e:
            print(f"Hint discovery failed: {e}")
            hints = None
    
    # If following event URLs is enabled, extract URLs and scrape individual pages
    if follow_event_urls and hints:
        print(f"Extracting event URLs from {url}...")
        event_urls = extract_event_urls(url, hints)
        print(f"Found {len(event_urls)} event URLs")
        
        all_events = []
        for event_url in event_urls:
            try:
                # Scrape individual event page (without URL following to avoid recursion)
                page_events = scrape_events_from_llm(event_url, source_id, hints=None, auto_discover_hints=False, follow_event_urls=False)
                all_events.extend(page_events)
            except Exception as e:
                print(f"Failed to scrape {event_url}: {e}")
                continue
        
        return all_events
    
    # Normal scraping flow
    data = parse_events(url, hints)
    events: List[dict[str, Any]] = []
    for item in data.get("events", []):
        start = to_iso_datetime(item.get("start"), item.get("timezone"))
        end = to_iso_datetime(item.get("end"), item.get("timezone"), end=True)
        ext_id = item.get("external_id") or item.get("url")
        if not ext_id:
            ext_id = make_external_id(url, item.get("title", ""), start or "")
        events.append(
            {
                "source_id": source_id,
                "external_id": ext_id,
                "title": item.get("title", ""),
                "description": item.get("description") or "",
                "location": item.get("location", ""),
                "start_time": start,
                "end_time": end,
                "url": item.get("url", url),
            }
        )
    return events
