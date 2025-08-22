#!/usr/bin/env python3
"""
Test script for pagination detection.

Tests pagination detection on various event listing sites using local HTML snapshots.
Use --live flag to fetch from live sites instead.
"""

import argparse
import os
import sys
import requests

# Add parent directory to path so we can import scrapers
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.pagination_detector import detect_pagination

# Test cases with local HTML files
TEST_CASES = [
    {
        "url": "https://www.boston.gov/events",
        "local_file": "tests/test_data/pagination_samples/boston_gov.html"
    },
    {
        "url": "https://www.needhamlibrary.org/events", 
        "local_file": "tests/test_data/pagination_samples/needhamlibrary_org.html"
    },
    {
        "url": "https://www.brooklinelibrary.org/events",
        "local_file": "tests/test_data/pagination_samples/brooklinelibrary_org.html"
    },
    {
        "url": "https://www.cambridgema.gov/calendars",
        "local_file": "tests/test_data/pagination_samples/cambridgema_gov.html"
    },
    {
        "url": "https://www.brooklinelibrary.org/events",
        "local_file": "tests/test_data/pagination_samples/brooklinelibrary_events.html"
    },
    {
        "url": "https://www.cambridgema.gov/citycalendar",
        "local_file": "tests/test_data/pagination_samples/cambridgema_citycalendar.html"
    }
]

def load_html_content(test_case, use_live=False):
    """Load HTML content from local file or live URL."""
    url = test_case["url"]
    
    if use_live:
        print(f"   📡 Fetching live: {url}")
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        return response.text
    else:
        local_file = test_case["local_file"]
        if not os.path.exists(local_file):
            raise FileNotFoundError(f"Local snapshot not found: {local_file}")
        
        print(f"   📄 Loading snapshot: {local_file}")
        with open(local_file, 'r', encoding='utf-8') as f:
            return f.read()

def test_pagination_detection(use_live=False):
    """Test pagination detection on various sites."""
    
    # Try to load OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        try:
            with open(os.path.expanduser("~/.secret_keys"), "r") as f:
                openai_api_key = f.read().strip()
        except FileNotFoundError:
            openai_api_key = None
            
    source = "live sites" if use_live else "local snapshots"
    print(f"🔍 Testing Pagination Detection ({source})")
    print("=" * 50)
    
    for test_case in TEST_CASES:
        url = test_case["url"]
        print(f"\n📄 Testing: {url}")
        
        try:
            # Load page content
            html_content = load_html_content(test_case, use_live)
            
            # Detect pagination
            result = detect_pagination(url, html_content, openai_api_key)
            
            # Print results
            print(f"   Type: {result.pagination_type}")
            print(f"   Confidence: {result.confidence:.2f}")
            print(f"   Pattern: {result.pattern_used}")
            print(f"   Next URLs: {len(result.next_urls)}")
            
            if result.next_urls:
                for i, next_url in enumerate(result.next_urls[:3]):  # Show first 3
                    print(f"     [{i+1}] {next_url}")
                if len(result.next_urls) > 3:
                    print(f"     ... and {len(result.next_urls) - 3} more")
                    
            if result.current_page:
                print(f"   Current Page: {result.current_page}")
            if result.total_pages_estimate:
                print(f"   Total Pages: {result.total_pages_estimate}")
                
            # Status
            if result.next_urls:
                print(f"   ✅ Pagination detected!")
            else:
                print(f"   ❌ No pagination found")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            
    print("\n🎯 Test Complete!")

def test_llm_features(use_live=False):
    """Test LLM hints and URL following features."""
    
    # Check for OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        try:
            with open(os.path.expanduser("~/.secret_keys"), "r") as f:
                openai_api_key = f.read().strip()
        except FileNotFoundError:
            print("⚠️  No OpenAI API key found. Skipping LLM tests.")
            return
    
    os.environ["OPENAI_API_KEY"] = openai_api_key
    
    if not use_live:
        print("⚠️  LLM features require live sites. Use --live flag to test.")
        return
    
    print(f"\n🤖 Testing LLM Features")
    print("=" * 50)
    
    try:
        from scrapers.llm_scraper import scrape_events_from_llm
        
        # Test Brookline hints system
        print(f"\n📄 Testing: Brookline Library Events (Hints)")
        hints = {'event_containers': ['.media.s-lc-c-evt']}
        events = scrape_events_from_llm('https://www.brooklinelibrary.org/events', hints=hints)
        print(f"   ✅ Manual hints found {len(events)} events")
        
        # Test Cambridge URL following  
        print(f"\n📄 Testing: Cambridge Calendar (URL Following)")
        hints = {'event_containers': ['.eventItem']}
        events = scrape_events_from_llm('https://www.cambridgema.gov/citycalendar', hints=hints, follow_event_urls=True)
        print(f"   ✅ URL following found {len(events)} events")
        
    except Exception as e:
        print(f"   ❌ LLM test failed: {e}")
    
    print(f"\n🎯 LLM Features Test Complete!")

def main():
    """Main entry point with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Test pagination detection using local HTML snapshots or live sites"
    )
    parser.add_argument(
        "--live", 
        action="store_true", 
        help="Fetch content from live sites instead of using local snapshots"
    )
    parser.add_argument(
        "--refresh-snapshots",
        action="store_true",
        help="Update local HTML snapshots from live sites"
    )
    parser.add_argument(
        "--test-llm",
        action="store_true",
        help="Also test LLM hints and URL following features (requires --live)"
    )
    
    args = parser.parse_args()
    
    if args.refresh_snapshots:
        refresh_snapshots()
    else:
        test_pagination_detection(use_live=args.live)
        if args.test_llm:
            test_llm_features(use_live=args.live)

def refresh_snapshots():
    """Refresh local HTML snapshots from live sites."""
    print("🔄 Refreshing HTML snapshots from live sites")
    print("=" * 50)
    
    os.makedirs("tests/test_data/pagination_samples", exist_ok=True)
    
    for test_case in TEST_CASES:
        url = test_case["url"]
        local_file = test_case["local_file"]
        
        print(f"\n📡 Fetching: {url}")
        
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            response.raise_for_status()
            
            with open(local_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            print(f"✅ Saved: {local_file} ({len(response.text):,} chars)")
            
        except Exception as e:
            print(f"❌ Failed to fetch {url}: {e}")
    
    print("\n🎯 Snapshot refresh complete!")

if __name__ == "__main__":
    main()