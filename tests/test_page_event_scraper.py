from unittest.mock import Mock, patch
import os
import sys
import json

# Ensure the project root is on the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scrapers.page_event_scraper import (
    find_event_containing_tags,
    extract_relevant_sections,
    process_section_with_llm,
    scrape_page_events
)
from bs4 import BeautifulSoup


SAMPLE_EVENT_HTML = '''
<html>
<body>
    <div class="event-listing">
        <h2>Community Concert</h2>
        <p>Join us for an evening of music on January 15th, 2025 at 7:00 PM</p>
        <p>Location: Main Street Theater</p>
        <a href="https://example.com/concert">More details</a>
    </div>
    <div class="news-item">
        <p>This is just news content without any dates or events</p>
    </div>
    <script>
        console.log("This should be stripped out");
    </script>
</body>
</html>
'''

MULTI_EVENT_HTML = '''
<html>
<body>
    <article class="calendar-event">
        <h3>Workshop: Photography Basics</h3>
        <div>Date: March 10, 2025</div>
        <div>Time: 2:00 PM - 4:00 PM</div>
        <div>Location: Community Center</div>
    </article>
    <article class="calendar-event">
        <h3>Book Club Meeting</h3>
        <div>Date: March 12, 2025</div>
        <div>Time: 6:30 PM</div>
        <div>Location: Library</div>
    </article>
</body>
</html>
'''

def fake_get(url, **kwargs):
    """Mock HTTP GET responses."""
    resp = Mock()
    resp.raise_for_status = lambda: None
    if url == "http://example.com/events":
        resp.text = SAMPLE_EVENT_HTML
    elif url == "http://example.com/multi-events":
        resp.text = MULTI_EVENT_HTML
    else:
        resp.text = "<html><body>No events here</body></html>"
    return resp


def fake_openai_response(*args, **kwargs):
    """Mock OpenAI API response."""
    resp = Mock()
    resp.raise_for_status = lambda: None
    
    # Simulate different responses based on content
    payload = kwargs.get('json', {})
    content = payload.get('messages', [{}])[0].get('content', '')
    
    if 'Community Concert' in content:
        mock_event = {
            "source_id": None,
            "external_id": "https://example.com/concert",
            "title": "Community Concert",
            "description": "Join us for an evening of music",
            "location": "Main Street Theater",
            "start_time": "2025-01-15T19:00:00-05:00",
            "end_time": None,
            "url": "https://example.com/concert"
        }
    elif 'Photography Basics' in content:
        mock_event = {
            "source_id": None,
            "external_id": "workshop-photography-2025-03-10",
            "title": "Workshop: Photography Basics", 
            "description": "Learn the basics of photography",
            "location": "Community Center",
            "start_time": "2025-03-10T14:00:00-05:00",
            "end_time": "2025-03-10T16:00:00-05:00",
            "url": "http://example.com/multi-events"
        }
    else:
        # Return null for content without clear events
        resp.json = lambda: {
            "choices": [{"message": {"content": "null"}}]
        }
        return resp
    
    resp.json = lambda: {
        "choices": [{"message": {"content": json.dumps(mock_event)}}]
    }
    return resp


def test_find_event_containing_tags():
    """Test finding tags that contain event information."""
    soup = BeautifulSoup(SAMPLE_EVENT_HTML, 'html.parser')
    event_tags = find_event_containing_tags(soup)
    
    assert len(event_tags) >= 1
    # Should find the div with class "event-listing" since it contains date/time patterns
    event_classes = [tag.get('class', []) for tag in event_tags]
    assert any('event-listing' in classes for classes in event_classes)


def test_extract_relevant_sections():
    """Test extracting clean text from event tags."""
    soup = BeautifulSoup(SAMPLE_EVENT_HTML, 'html.parser')
    event_tags = find_event_containing_tags(soup)
    sections = extract_relevant_sections(event_tags)
    
    assert len(sections) >= 1
    # Should contain the event content but not the script
    assert any('Community Concert' in section for section in sections)
    assert not any('console.log' in section for section in sections)


@patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
def test_process_section_with_llm():
    """Test processing a text section with mocked LLM."""
    section = "Community Concert\nJoin us for an evening of music on January 15th, 2025 at 7:00 PM\nLocation: Main Street Theater"
    
    with patch('scrapers.page_event_scraper.requests.post', side_effect=fake_openai_response):
        event = process_section_with_llm(section, "http://example.com/events")
    
    assert event is not None
    assert event['title'] == 'Community Concert'
    assert event['location'] == 'Main Street Theater'
    assert '2025-01-15' in event['start_time']


@patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
def test_scrape_page_events():
    """Test the full page event scraping process."""
    with patch('scrapers.page_event_scraper.requests.get', side_effect=fake_get), \
         patch('scrapers.page_event_scraper.requests.post', side_effect=fake_openai_response):
        
        events = scrape_page_events("http://example.com/events")
    
    assert len(events) >= 1
    event = events[0]
    assert event['title'] == 'Community Concert'
    # source_id removed from new API


def test_scrape_page_events_multiple():
    """Test scraping a page with multiple events."""
    with patch('scrapers.page_event_scraper.requests.get', side_effect=fake_get), \
         patch('scrapers.page_event_scraper.requests.post', side_effect=fake_openai_response):
        
        events = scrape_page_events("http://example.com/multi-events")
    
    # Should find multiple events
    assert len(events) >= 1
    titles = [event['title'] for event in events]
    assert any('Photography' in title for title in titles)


def test_scrape_page_events_no_openai_key():
    """Test scraping without OpenAI API key."""
    with patch('scrapers.page_event_scraper.requests.get', side_effect=fake_get):
        events = scrape_page_events("http://example.com/events")
    
    # Should return empty list when no API key is available
    assert events == []