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


def fetch_rendered_text(url: str) -> str:
    """Return rendered text content for ``url`` or its iframe."""
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

        page.evaluate("const h=document.querySelector('header'); if(h) h.remove();")
        page.evaluate("const f=document.querySelector('footer'); if(f) f.remove();")
        text = page.evaluate("document.body.innerText")
        browser.close()
    return text.strip()


def parse_events(url: str) -> dict[str, Any]:
    """Use OpenAI to parse events from ``url`` into the structured schema."""
    page_text = fetch_rendered_text(url)
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


def scrape_events_from_llm(url: str, source_id: int = 0) -> List[dict[str, Any]]:
    """Fetch ``url`` and convert extracted events to the API schema."""
    data = parse_events(url)
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
