"""Scrape a single URL for events and post them to the API."""
from __future__ import annotations

import os
import sys
import logging
from typing import List

from ingest.api_client import post_event
from ingest.description_generator import generate_description
from scrapers.jsonld_scraper import scrape_events_from_jsonld
from scrapers.llm_scraper import scrape_events_from_llm

logger = logging.getLogger(__name__)
if os.getenv("SCRAPER_DEBUG"):
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def run(url: str) -> None:
    """Scrape events from ``url`` and post them to the backend."""
    events: List[dict] = []
    method = ""

    logger.info("Attempting JSON-LD scrape")
    try:
        events = scrape_events_from_jsonld(url)
        logger.info("JSON-LD scraper returned %d event(s)", len(events))
        method = "jsonld"
    except Exception as exc:
        logger.info("JSON-LD scraper failed: %s", exc)

    if not events:
        logger.info("Falling back to LLM scrape")
        try:
            events = scrape_events_from_llm(url)
            logger.info("LLM scraper returned %d event(s)", len(events))
            method = "llm"
        except Exception as exc:
            print("❌ Failed to fetch or parse page:", exc)
            return

    logger.info("Using %s scraper", method)

    if not events:
        print("No events found at", url)
        return

    if logger.isEnabledFor(logging.INFO):
        logger.info("Events found:")
        for event in events:
            logger.info("  %s", event)

    for event in events:
        if not event.get("description"):
            event["description"] = generate_description(event)
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
