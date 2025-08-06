"""Entrypoint script to run scrapers and LLM agent and post events."""
from __future__ import annotations

from ingest.api_client import post_event
from mcp.agent import find_events_near_location
from scrapers.sample_scraper import scrape_events


def run() -> None:
    """Run all data collection jobs and post events to API."""
    all_events: list[dict] = []

    # From scrapers
    all_events.extend(scrape_events())

    # From LLM agent
    all_events.extend(find_events_near_location("Needham, MA"))

    # Post all to backend
    for event in all_events:
        try:
            result = post_event(event)
            print("✅ Posted:", result.get("title", "<unknown>"))
        except Exception as exc:  # pragma: no cover - logging only
            print("❌ Failed to post event:", event.get("title", "<unknown>"), exc)


if __name__ == "__main__":
    run()
