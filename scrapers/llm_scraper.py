"""Extract events from page text via OpenAI's structured output API."""
from __future__ import annotations

from typing import Any, List

import trafilatura
from openai import OpenAI

client = OpenAI()

EVENT_SCHEMA = {
    "name": "Events",
    "schema": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["title", "start"],
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "start": {"type": "string", "description": "ISO 8601 datetime or date"},
                        "end": {"type": "string"},
                        "timezone": {"type": "string"},
                        "location": {"type": "string"},
                        "organizer": {"type": "string"},
                        "price": {"type": "string"},
                        "url": {"type": "string", "format": "uri"},
                    },
                },
            },
        },
        "required": ["source", "events"],
        "additionalProperties": False,
    },
}

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

    resp = client.responses.create(
        model="o4-mini",
        reasoning={"effort": "low"},
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"URL: {url}\n\nPAGE_TEXT:\n{text[:120000]}"},
        ],
        response_format={"type": "json_schema", "json_schema": EVENT_SCHEMA},
    )
    data = resp.output_parsed  # already a dict matching EVENT_SCHEMA
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
