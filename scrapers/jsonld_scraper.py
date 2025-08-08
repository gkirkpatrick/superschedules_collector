"""Scrape JSON-LD event data from webpages."""
from __future__ import annotations

import json
from typing import Any, List

import requests
from bs4 import BeautifulSoup


def scrape_events_from_jsonld(url: str, source_id: int = 0) -> List[dict[str, Any]]:
    """Fetch a page and extract events described in JSON-LD.

    Args:
        url: Page URL containing JSON-LD event data.
        source_id: Numeric source identifier to include on each event.

    Returns:
        A list of event dictionaries matching the API schema.
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    events: List[dict[str, Any]] = []

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue

        for item in _extract_event_objects(data):
            events.append(
                {
                    "source_id": source_id,
                    "external_id": item.get("@id") or item.get("url"),
                    "title": item.get("name", ""),
                    "description": item.get("description", ""),
                    "location": _parse_location(item.get("location")),
                    "start_time": item.get("startDate"),
                    "end_time": item.get("endDate"),
                    "url": item.get("url", url),
                }
            )

    return events


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


def _parse_location(location: Any) -> str:
    """Extract a human-readable location string."""
    if isinstance(location, dict):
        return location.get("name") or location.get("address", "")
    if isinstance(location, str):
        return location
    return ""
