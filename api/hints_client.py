"""
API client for managing hints storage using the backend's Site Strategy API.

This module provides functions to store and retrieve scraping hints from the
backend's site strategy system, which uses the best_selectors field to cache
CSS selectors and other scraping metadata.
"""

import os
import requests
from typing import Dict, Optional
from urllib.parse import urlparse


class HintsClient:
    """Client for storing/retrieving hints from backend Site Strategy API."""
    
    def __init__(self, api_url: Optional[str] = None, api_token: Optional[str] = None):
        """Initialize the hints client with backend API credentials."""
        self.api_url = api_url or os.getenv("API_URL", "http://localhost:8000/api/v1")
        self.api_token = api_token or os.getenv("API_TOKEN")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.api_token}" if self.api_token else ""
        }
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL for use as strategy key."""
        parsed = urlparse(url)
        return parsed.netloc.lower()
    
    def get_hints(self, url: str) -> Optional[Dict]:
        """
        Retrieve cached hints for a URL's domain from the backend.
        
        Args:
            url: The URL to get hints for
            
        Returns:
            Dictionary with hint data or None if not found
        """
        domain = self._get_domain(url)
        
        try:
            response = requests.get(
                f"{self.api_url}/sites/{domain}/strategy",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                best_selectors = data.get("best_selectors")
                
                if best_selectors and isinstance(best_selectors, dict):
                    # Convert backend format to our hints format
                    hints = {}
                    if "event_containers" in best_selectors:
                        hints["event_containers"] = best_selectors["event_containers"]
                    if "pagination_selectors" in best_selectors:
                        hints["pagination_selectors"] = best_selectors["pagination_selectors"]
                    
                    return hints if hints else None
            
            elif response.status_code == 404:
                # No strategy found for this domain yet
                return None
            else:
                print(f"Error retrieving hints for {domain}: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            print(f"Failed to retrieve hints for {domain}: {e}")
            return None
    
    def store_hints(self, url: str, hints: Dict, success: bool = True) -> bool:
        """
        Store discovered hints for a URL's domain in the backend.
        
        Args:
            url: The URL the hints were discovered for
            hints: Dictionary containing the hints (event_containers, etc.)
            success: Whether the scraping was successful with these hints
            
        Returns:
            True if storage was successful, False otherwise
        """
        domain = self._get_domain(url)
        
        try:
            # Format hints for backend storage
            best_selectors = {}
            if "event_containers" in hints:
                best_selectors["event_containers"] = hints["event_containers"]
            if "pagination_selectors" in hints:
                best_selectors["pagination_selectors"] = hints["pagination_selectors"]
            
            # Prepare the update payload
            payload = {
                "best_selectors": best_selectors,
                "success": success,
                "notes": f"Auto-discovered hints from collector API"
            }
            
            # Try POST (report) first, then PUT (override) if needed
            response = requests.post(
                f"{self.api_url}/sites/{domain}/strategy",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                print(f"Successfully stored hints for {domain}")
                return True
            elif response.status_code == 404:
                # Domain doesn't exist, try PUT to create/override
                response = requests.put(
                    f"{self.api_url}/sites/{domain}/strategy",
                    headers=self.headers,
                    json=payload,
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    print(f"Successfully created strategy with hints for {domain}")
                    return True
            
            print(f"Failed to store hints for {domain}: {response.status_code}")
            return False
            
        except requests.RequestException as e:
            print(f"Failed to store hints for {domain}: {e}")
            return False
    
    def update_success_rate(self, url: str, success: bool) -> bool:
        """
        Update the success rate for a domain's strategy.
        
        Args:
            url: The URL that was scraped
            success: Whether the scraping was successful
            
        Returns:
            True if update was successful, False otherwise
        """
        domain = self._get_domain(url)
        
        try:
            payload = {"success": success}
            
            response = requests.post(
                f"{self.api_url}/sites/{domain}/strategy",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            
            return response.status_code in [200, 201]
            
        except requests.RequestException as e:
            print(f"Failed to update success rate for {domain}: {e}")
            return False


# Convenience functions
def get_cached_hints(url: str) -> Optional[Dict]:
    """Get cached hints for a URL."""
    client = HintsClient()
    return client.get_hints(url)


def cache_hints(url: str, hints: Dict, success: bool = True) -> bool:
    """Cache hints for a URL."""
    client = HintsClient()
    return client.store_hints(url, hints, success)


def update_strategy_success(url: str, success: bool) -> bool:
    """Update success rate for a URL's domain strategy."""
    client = HintsClient()
    return client.update_success_rate(url, success)