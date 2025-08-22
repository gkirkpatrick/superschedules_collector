#!/usr/bin/env python3
"""
Test script for LLM hints system and URL following strategy.

Tests the new LLM-powered event extraction features using local HTML snapshots.
Use --live flag to fetch from live sites instead.
"""

import argparse
import os
import sys
from unittest.mock import Mock, patch
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test cases with expected results
HINT_TEST_CASES = [
    {
        "name": "Brookline Library Events",
        "url": "https://www.brooklinelibrary.org/events",
        "local_file": "tests/test_data/pagination_samples/brooklinelibrary_events.html",
        "expected_hints": [".media.s-lc-c-evt", ".s-lc-c-evt"],
        "expected_min_events": 15,
        "test_auto_discovery": True
    },
    {
        "name": "Cambridge City Calendar", 
        "url": "https://www.cambridgema.gov/citycalendar",
        "local_file": "tests/test_data/pagination_samples/cambridgema_citycalendar.html",
        "expected_hints": [".eventItem"],
        "expected_min_events": 8,
        "test_url_following": True
    }
]

def load_html_content(test_case, use_live=False):
    """Load HTML content from local file or live URL."""
    if use_live:
        import requests
        print(f"   📡 Fetching live: {test_case['url']}")
        response = requests.get(test_case['url'], headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        return response.text
    else:
        local_file = test_case["local_file"]
        if not os.path.exists(local_file):
            raise FileNotFoundError(f"Local snapshot not found: {local_file}")
        
        print(f"   📄 Loading snapshot: {local_file}")
        with open(local_file, 'r', encoding='utf-8') as f:
            return f.read()

def mock_playwright_for_local_html(html_content, target_url):
    """Create a mock playwright page that returns local HTML content."""
    
    # Mock the page object
    mock_page = Mock()
    mock_page.content.return_value = html_content
    mock_page.goto.return_value = None
    mock_page.wait_for_load_state.return_value = None
    mock_page.wait_for_timeout.return_value = None
    mock_page.query_selector.return_value = None
    mock_page.query_selector_all.return_value = []
    mock_page.evaluate.return_value = ""
    
    # Mock the browser
    mock_browser = Mock()
    mock_browser.new_page.return_value = mock_page
    mock_browser.close.return_value = None
    
    # Mock the playwright context manager
    mock_pw = Mock()
    mock_pw.chromium.launch.return_value = mock_browser
    
    return mock_pw

def test_hint_discovery_with_local_html(use_live=False):
    """Test LLM hint discovery using local HTML snapshots."""
    
    # Try to load OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        try:
            with open(os.path.expanduser("~/.secret_keys"), "r") as f:
                openai_api_key = f.read().strip()
        except FileNotFoundError:
            openai_api_key = None
    
    if not openai_api_key:
        print("❌ No OpenAI API key found. Set OPENAI_API_KEY or ~/.secret_keys")
        return
        
    os.environ["OPENAI_API_KEY"] = openai_api_key
    
    source = "live sites" if use_live else "local snapshots"
    print(f"🔍 Testing LLM Hints System ({source})")
    print("=" * 50)
    
    from scrapers.llm_scraper import discover_event_hints, scrape_events_from_llm
    
    for test_case in HINT_TEST_CASES:
        print(f"\n📄 Testing: {test_case['name']}")
        print(f"   URL: {test_case['url']}")
        
        try:
            if use_live:
                # Test with live sites
                if test_case.get("test_auto_discovery"):
                    print("   🔍 Testing auto-discovery...")
                    events = scrape_events_from_llm(test_case['url'], auto_discover_hints=True)
                    print(f"   ✅ Auto-discovery found {len(events)} events")
                
                if test_case.get("test_url_following"):
                    print("   🔗 Testing URL following...")
                    hints = {"event_containers": test_case["expected_hints"]}
                    events = scrape_events_from_llm(test_case['url'], hints=hints, follow_event_urls=True)
                    print(f"   ✅ URL following found {len(events)} events")
                    
            else:
                # Test with local snapshots (no actual scraping, just structure)
                html_content = load_html_content(test_case, use_live=False)
                print(f"   📊 Loaded {len(html_content):,} chars of HTML")
                
                # Basic validation
                for hint in test_case["expected_hints"]:
                    if hint.replace(".", "") in html_content:
                        print(f"   ✅ Found expected CSS class: {hint}")
                    else:
                        print(f"   ⚠️  Expected CSS class not found: {hint}")
                        
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n🎯 Hint Discovery Test Complete!")

def test_manual_hints(use_live=False):
    """Test manual hints with known good selectors."""
    
    # Try to load OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        try:
            with open(os.path.expanduser("~/.secret_keys"), "r") as f:
                openai_api_key = f.read().strip()
        except FileNotFoundError:
            print("❌ No OpenAI API key found. Skipping LLM tests.")
            return
            
    os.environ["OPENAI_API_KEY"] = openai_api_key
    
    if not use_live:
        print("⚠️  Manual hints testing requires live sites. Use --live flag.")
        return
    
    print(f"\n🎯 Testing Manual Hints (live sites)")
    print("=" * 50)
    
    from scrapers.llm_scraper import scrape_events_from_llm
    
    # Test Brookline with manual hints
    print("\n📄 Testing Brookline Library with manual .media.s-lc-c-evt hint")
    hints = {"event_containers": [".media.s-lc-c-evt"]}
    events = scrape_events_from_llm("https://www.brooklinelibrary.org/events", hints=hints)
    print(f"   Found {len(events)} events")
    if events:
        print(f"   Sample: {events[0]['title']} - {events[0]['start_time']}")
    
    # Test Cambridge with URL following
    print("\n📄 Testing Cambridge Calendar with URL following")
    hints = {"event_containers": [".eventItem"]}
    events = scrape_events_from_llm("https://www.cambridgema.gov/citycalendar", hints=hints, follow_event_urls=True)
    print(f"   Found {len(events)} events")
    if events:
        print(f"   Sample: {events[0]['title']} - {events[0]['start_time']}")

def main():
    """Main entry point with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Test LLM hints system using local HTML snapshots or live sites"
    )
    parser.add_argument(
        "--live", 
        action="store_true", 
        help="Test against live sites instead of using local snapshots"
    )
    parser.add_argument(
        "--manual-only",
        action="store_true",
        help="Only run manual hints tests (requires --live)"
    )
    
    args = parser.parse_args()
    
    if args.manual_only:
        test_manual_hints(use_live=args.live)
    else:
        test_hint_discovery_with_local_html(use_live=args.live)
        if args.live:
            test_manual_hints(use_live=args.live)

if __name__ == "__main__":
    main()