"""Client for posting events to the Superschedules API."""
from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")
AUTH_TOKEN = os.getenv("API_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
}


def post_event(event: dict[str, Any]) -> dict[str, Any]:
    """Post an event dictionary to the Superschedules backend."""
    url = f"{API_BASE_URL}/events/"
    response = requests.post(url, json=event, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()
