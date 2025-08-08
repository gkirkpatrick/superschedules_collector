"""Scraper helpers for Boston Public Library events.

This module demonstrates two approaches for grabbing event cards from the
BPL events site.  The first fetches the static HTML and pulls out the event
blocks using :mod:`BeautifulSoup`.  The second renders the page with a headless
browser via :mod:`requests_html` before applying the same extraction logic.

Both functions return a list of simple dictionaries that contain the most
useful fields we can reliably scrape without an additional LLM step.
"""
from __future__ import annotations

from typing import Any, Iterable

import re
import requests
from bs4 import BeautifulSoup

try:  # ``requests_html`` pulls in pyppeteer and is optional.
    from requests_html import HTMLSession
except Exception:  # pragma: no cover - optional dependency
    HTMLSession = None  # type: ignore


def _extract_from_soup(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Return event dictionaries extracted from a parsed document."""
    events: list[dict[str, Any]] = []
    for card in soup.select(".cp-events-search-item"):
        title = (
            card.select_one("h3, .event-title")
            .get_text(strip=True)
            if card.select_one("h3, .event-title")
            else None
        )
        date_text = (
            card.select_one(
                ".event-date, .cp-event-date-stamp, .event-time"
            ).get_text(" ", strip=True)
            if card.select_one(".event-date, .cp-event-date-stamp, .event-time")
            else ""
        )
        location = (
            card.select_one(".event-details .branch, .event-details .location")
            .get_text(strip=True)
            if card.select_one(".event-details")
            else None
        )
        desc = (
            card.select_one(".event-details p")
            .get_text(" ", strip=True)
            if card.select_one(".event-details p")
            else ""
        )

        # heuristics
        all_day = "All day" in date_text
        canceled = "Canceled" in card.get_text(" ", strip=True)
        times = re.search(
            r"(\d{1,2}:\d{2}\s*[ap]m)\s*\u2013\s*(\d{1,2}:\d{2}\s*[ap]m)",
            date_text,
            re.I,
        )
        start_time, end_time = (times.group(1), times.group(2)) if times else (None, None)

        events.append(
            {
                "title": title,
                "date_text": date_text,
                "location": location,
                "all_day": all_day,
                "canceled": canceled,
                "start_time": start_time,
                "end_time": end_time,
                "description": desc,
            }
        )
    return events


def scrape_static(url: str) -> list[dict[str, Any]]:
    """Scrape ``url`` using simple ``requests`` + ``BeautifulSoup``."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    return _extract_from_soup(soup)


def scrape_rendered(url: str) -> list[dict[str, Any]]:
    """Render ``url`` with a headless browser then scrape the resulting HTML.

    This requires :mod:`requests_html`.  If the dependency is missing the
    function raises a :class:`RuntimeError`.
    """
    if HTMLSession is None:  # pragma: no cover - executed when dependency missing
        raise RuntimeError("requests_html is not installed")

    session = HTMLSession()
    resp = session.get(url)
    resp.html.render(timeout=40)
    soup = BeautifulSoup(resp.html.html, "lxml")
    return _extract_from_soup(soup)
