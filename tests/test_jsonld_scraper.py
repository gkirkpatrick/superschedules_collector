from unittest.mock import Mock, patch
import os
import sys

# Ensure the project root is on the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scrapers.jsonld_scraper import scrape_events_from_jsonld


PARENT_URL = "http://example.com/events"
IFRAME_URL = "http://example.com/iframe.html"

PARENT_HTML = '<html><body><iframe src="iframe.html"></iframe></body></html>'
IFRAME_HTML = (
    '<html><body><script type="application/ld+json">'
    '{"@context":"http://schema.org","@type":"Event","name":"Sample Event",'
    '"startDate":"2025-08-11","url":"https://example.com/event"}'
    '</script></body></html>'
)


def fake_get(url, **kwargs):  # pylint: disable=unused-argument
    resp = Mock()
    resp.raise_for_status = lambda: None
    if url == PARENT_URL:
        resp.text = PARENT_HTML
    elif url == IFRAME_URL:
        resp.text = IFRAME_HTML
    else:
        raise ValueError(f"Unexpected URL {url}")
    return resp


def test_scrape_events_from_iframe_jsonld():
    with patch("scrapers.jsonld_scraper.requests.get", side_effect=fake_get):
        events = scrape_events_from_jsonld(PARENT_URL, source_id=1)
    assert len(events) == 1
    event = events[0]
    assert event["title"] == "Sample Event"
    assert event["url"] == "https://example.com/event"
    assert event["start_time"] == "2025-08-11T00:00:00+00:00"
    assert event["source_id"] == 1
