"""Client for posting events to the Superschedules API."""
from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")


def _make_headers() -> dict[str, str]:
    """Return headers for API requests, including the auth token if set."""
    token = os.getenv("API_TOKEN")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def post_event(event: dict[str, Any]) -> dict[str, Any]:
    """Post an event dictionary to the Superschedules backend."""
    url = f"{API_BASE_URL}/events/"
    headers = _make_headers()
    response = requests.post(url, json=event, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()
