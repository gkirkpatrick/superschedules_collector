"""Example scraper module."""


def scrape_events() -> list[dict]:
    """Return example events scraped from the web.

    Real scrapers would fetch and parse HTML pages, APIs, etc. For now
    we simply return static data.
    """
    return [
        {
            "title": "Farmers Market",
            "description": "Weekly farmers market with local vendors.",
            "location": "Needham Center",
            "start_time": "2025-08-09T09:00:00Z",
            "end_time": "2025-08-09T12:00:00Z",
            "url": "https://example.com/farmers-market",
        }
    ]
