"""Scrape a single URL for events and post them to the API."""
from __future__ import annotations

import sys
from typing import List

from ingest.api_client import post_event
from scrapers.jsonld_scraper import scrape_events_from_jsonld
from scrapers.llm_scraper import scrape_events_from_llm


def run(url: str) -> None:
    """Scrape events from ``url`` and post them to the backend."""
    try:
        events: List[dict] = scrape_events_from_jsonld(url)
        if not events:
            events = scrape_events_from_llm(url)
    except Exception as exc:
        print("❌ Failed to fetch or parse page:", exc)
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
