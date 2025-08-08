"""Scrape a single URL for events and post them to the API."""
from __future__ import annotations

import sys
from typing import List

import requests

from ingest.api_client import post_event
from scrapers.jsonld_scraper import scrape_events_from_jsonld


def run(url: str) -> None:
    """Scrape events from ``url`` and post them to the backend."""
    try:
        events: List[dict] = scrape_events_from_jsonld(url)
    except requests.RequestException as exc:
        print("❌ Failed to fetch page:", exc)
        return

    if not events:
        print("No events found at", url)
        return

    for event in events:
        try:
            result = post_event(event)
            print("✅ Posted:", result.get("title", "<unknown>"))
        except Exception as exc:  # pragma: no cover - logging only
            print("❌ Failed to post event:", event.get("title", "<unknown>"), exc)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m jobs.process_url <url>")
        raise SystemExit(1)
    run(sys.argv[1])
