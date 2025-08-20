#!/usr/bin/env python3
"""
Test script for pagination detection.

Tests pagination detection on various event listing sites.
"""

import os
import requests
from scrapers.pagination_detector import detect_pagination

# Test URLs with known pagination
TEST_URLS = [
    "https://www.boston.gov/events",
    "https://www.needhamlibrary.org/events", 
    "https://www.brooklinelibrary.org/events",
    "https://www.cambridgema.gov/calendars"
]

def test_pagination_detection():
    """Test pagination detection on various sites."""
    
    # Try to load OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        try:
            with open(os.path.expanduser("~/.secret_keys"), "r") as f:
                openai_api_key = f.read().strip()
        except FileNotFoundError:
            openai_api_key = None
            
    print("🔍 Testing Pagination Detection")
    print("=" * 50)
    
    for url in TEST_URLS:
        print(f"\n📄 Testing: {url}")
        
        try:
            # Fetch page content
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            response.raise_for_status()
            
            # Detect pagination
            result = detect_pagination(url, response.text, openai_api_key)
            
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

if __name__ == "__main__":
    test_pagination_detection()