"""Client for posting events to the Superschedules API."""
from __future__ import annotations

import os
import logging
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

logger = logging.getLogger(__name__)
if os.getenv("SCRAPER_DEBUG"):
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def _make_headers() -> dict[str, str]:
    """Return headers for API requests, including the auth token if set."""
    token = os.getenv("API_TOKEN")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _log_request(method: str, url: str, headers: dict[str, str], payload: Any | None = None) -> None:
    """Log details about an outgoing HTTP request."""
    logger.info("%s %s", method.upper(), url)
    logger.info("Headers: %s", headers)
    if payload is not None:
        logger.info("Payload: %s", payload)


def post_event(event: dict[str, Any]) -> dict[str, Any]:
    """Post an event dictionary to the Superschedules backend."""
    url = f"{API_BASE_URL}/events/"
    headers = _make_headers()
    _log_request("post", url, headers, event)
    response = requests.post(url, json=event, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def post_dummy_source() -> dict[str, Any]:
    """Send a placeholder source to the backend for debugging auth issues."""
    url = f"{API_BASE_URL}/sources/"
    payload = {"name": "Dummy Source", "url": "https://example.com"}
    headers = _make_headers()
    _log_request("post", url, headers, payload)
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()
