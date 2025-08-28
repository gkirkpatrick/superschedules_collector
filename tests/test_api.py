"""Tests for the simplified extraction API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data


def test_root_endpoint():
    """Test the root endpoint returns API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Superschedules Collector API" in data["name"]
    assert "docs" in data
    assert "health" in data


@pytest.fixture
def mock_jsonld_events():
    """Mock events from JSON-LD scraper."""
    return [
        {
            "external_id": "event-1",
            "title": "Test Event",
            "description": "A test event description",
            "location": "Test Location",
            "start_time": "2025-01-15T19:00:00-05:00",
            "end_time": "2025-01-15T21:00:00-05:00",
            "url": "https://example.com/event1"
        }
    ]


@pytest.fixture
def mock_enhanced_events():
    """Mock events after LLM enhancement."""
    return [
        {
            "external_id": "event-1",
            "title": "Test Event",
            "description": "A test event description",
            "location": "Test Location",
            "start_time": "2025-01-15T19:00:00-05:00",
            "end_time": "2025-01-15T21:00:00-05:00",
            "url": "https://example.com/event1",
            "tags": ["music", "evening", "indoor"],
            "validation_score": 0.85
        }
    ]


def test_extract_endpoint_success(mock_jsonld_events, mock_enhanced_events):
    """Test successful event extraction."""
    with patch("api.main._extract_events_sync") as mock_extract:
        mock_extract.return_value = {
            "events": mock_enhanced_events,
            "extraction_method": "jsonld"
        }
        
        response = client.post("/extract", json={
            "url": "https://example.com/events",
            "extraction_hints": {
                "expected_event_count": 1,
                "content_selectors": [".event"]
            }
        })
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert len(data["events"]) == 1
    assert data["events"][0]["title"] == "Test Event"
    assert data["events"][0]["tags"] == ["music", "evening", "indoor"]
    assert data["events"][0]["validation_score"] == 0.85
    assert data["metadata"]["extraction_method"] == "jsonld"
    assert data["metadata"]["total_found"] == 1
    assert "processing_time_seconds" in data


def test_extract_endpoint_llm_fallback(mock_enhanced_events):
    """Test LLM fallback when JSON-LD fails."""
    with patch("api.main._extract_events_sync") as mock_extract:
        mock_extract.return_value = {
            "events": mock_enhanced_events,
            "extraction_method": "llm"
        }
        
        response = client.post("/extract", json={
            "url": "https://example.com/events"
        })
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert len(data["events"]) == 1
    assert data["metadata"]["extraction_method"] == "llm"


def test_extract_endpoint_no_events():
    """Test extraction when no events are found."""
    with patch("api.main._extract_events_sync") as mock_extract:
        mock_extract.return_value = {
            "events": [],
            "extraction_method": "failed"
        }
        
        response = client.post("/extract", json={
            "url": "https://example.com/events"
        })
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is False
    assert len(data["events"]) == 0
    assert data["metadata"]["extraction_method"] == "failed"


def test_extract_endpoint_invalid_url():
    """Test extraction with missing URL."""
    response = client.post("/extract", json={})
    
    assert response.status_code == 422  # Validation error


def test_extract_endpoint_with_hints():
    """Test extraction with extraction hints."""
    with patch("api.main._extract_events_sync") as mock_extract:
        mock_extract.return_value = {
            "events": [],
            "extraction_method": "failed"
        }
        
        response = client.post("/extract", json={
            "url": "https://example.com/events",
            "extraction_hints": {
                "expected_event_count": 5,
                "content_selectors": [".event-item", ".calendar-entry"],
                "date_format_hints": ["MM/dd/yyyy", "yyyy-MM-dd"]
            }
        })
    
    assert response.status_code == 200
    # Verify the extraction function was called with hints
    mock_extract.assert_called_once()
    call_args = mock_extract.call_args[0]
    hints = call_args[1]  # Second argument is hints
    assert hints.content_selectors == [".event-item", ".calendar-entry"]