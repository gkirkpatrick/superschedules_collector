"""Utilities for managing event source catalog."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup

BASE_PATH = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = BASE_PATH / "sources" / "eastern_massachusetts.json"


@dataclass
class EventSource:
    """Represents a single event source."""
    name: str
    url: str
    type: str
    city: str
    score: float | None = None


def load_sources(path: str | Path = DEFAULT_CATALOG) -> list[EventSource]:
    """Load event sources from a JSON catalog file."""
    data = json.loads(Path(path).read_text())
    return [EventSource(**item) for item in data]


def discover_from_seed(seed_url: str) -> list[str]:
    """Discover potential event pages from a seed URL.

    Looks for links containing common event keywords.
    """
    try:
        resp = requests.get(seed_url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if any(k in href.lower() for k in ("event", "calendar")):
            if href.startswith("/"):
                href = requests.compat.urljoin(seed_url, href)
            if href not in urls:
                urls.append(href)
    return urls


def validate_source(url: str) -> bool:
    """Return True if the URL appears reachable."""
    try:
        resp = requests.head(url, timeout=10)
        if resp.status_code >= 400:
            resp = requests.get(url, timeout=10)
        return resp.status_code < 400
    except requests.RequestException:
        return False


def score_source(url: str) -> float:
    """Compute a basic quality score for an event source.

    Scoring is heuristic:
      * +0.5 if JSON-LD structured data is present
      * +0.5 if the word "event" appears in page text
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return 0.0

    soup = BeautifulSoup(resp.text, "html.parser")
    score = 0.0
    if soup.find("script", {"type": "application/ld+json"}):
        score += 0.5
    if soup.find(string=lambda s: isinstance(s, str) and "event" in s.lower()):
        score += 0.5
    return round(score, 2)


def export_sources(sources: Iterable[EventSource], path: str | Path) -> None:
    """Export event sources to JSON."""
    Path(path).write_text(
        json.dumps([asdict(s) for s in sources], indent=2)
    )

