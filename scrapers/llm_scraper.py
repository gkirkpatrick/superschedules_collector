"""Extract events from page text via OpenAI's structured output API."""
from __future__ import annotations

from typing import Any, List

import trafilatura
from openai import OpenAI
from pydantic import BaseModel, Field

client = OpenAI()


class Event(BaseModel):
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
    "You extract events from arbitrary webpage text.\n"
    "- Output *only* fields defined by the schema.\n"
    "- Normalize dates to ISO 8601; if only a day is given, use YYYY-MM-DD.\n"
    "- If timezone is implied by the venue or page, include it (IANA tz).\n"
    "- Include the canonical event URL when present."
)


def fetch_text(url: str) -> str:
    """Return clean text content for ``url`` using Trafilatura."""
    downloaded = trafilatura.fetch_url(url, no_ssl=False)
    if not downloaded:
        raise RuntimeError("Failed to fetch")
    return trafilatura.extract(downloaded, include_comments=False, include_tables=True) or ""


def parse_events(url: str) -> dict[str, Any]:
    """Use OpenAI to parse events from ``url`` into the structured schema."""
    text = fetch_text(url)
    if not text or len(text) < 200:
        return {"source": url, "events": []}

    resp = client.responses.parse(
        model="o4-mini",
        reasoning={"effort": "low"},
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"URL: {url}\n\nPAGE_TEXT:\n{text[:120000]}"},
        ],
        text_format=Events,
    )
    data = resp.output_parsed.model_dump()
    data["source"] = data.get("source") or url
    return data


def scrape_events_from_llm(url: str, source_id: int = 0) -> List[dict[str, Any]]:
    """Fetch ``url`` and convert extracted events to the API schema."""
    data = parse_events(url)
    events: List[dict[str, Any]] = []
    for item in data.get("events", []):
        events.append(
            {
                "source_id": source_id,
                "external_id": item.get("url"),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "location": item.get("location", ""),
                "start_time": item.get("start"),
                "end_time": item.get("end"),
                "url": item.get("url", url),
            }
        )
    return events
