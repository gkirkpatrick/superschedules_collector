# Stub: call an LLM to get structured event data
from __future__ import annotations


def find_events_near_location(location: str) -> list[dict]:
    """Return a list of events near a location.

    This is a placeholder that would eventually call an LLM or another
    service to discover events. For now it returns static data so the
    rest of the pipeline can be exercised.
    """
    return [
        {
            "title": "Jazz Night at the Park",
            "description": "Live jazz concert in the town park",
            "location": "Needham Town Park",
            "start_time": "2025-08-10T18:00:00Z",
            "end_time": "2025-08-10T20:00:00Z",
            "url": "https://example.com/jazz-night",
        }
    ]
