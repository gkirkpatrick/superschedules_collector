"""Scrape HTML event blocks and extract structured data via an LLM."""
from __future__ import annotations

import json
import os
from typing import Any, List, Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "o4-nano")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

PROMPT_TEMPLATE = (
    "Extract structured event data from this HTML. Return valid JSON with:\n"
    "title, start_time, end_time, location, description, image_url, tags (list), source_url\n\n"
    "HTML:\n{html}"
)


class LLMExtractionError(Exception):
    """Raised when the LLM response cannot be parsed as JSON."""


# pylint: disable=too-many-arguments

def scrape_and_extract_events(
    url: str,
    selector: str = "div.cp-events-search-item",
    debug_dir: Optional[str] = None,
) -> List[dict[str, Any]]:
    """Scrape a webpage and extract structured events using an LLM.

    Args:
        url: URL of the page containing event blocks.
        selector: CSS selector to identify event blocks.
        debug_dir: If provided, save raw HTML and parsed JSON for debugging.

    Returns:
        A list of event dictionaries.
    """

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    blocks = soup.select(selector)

    events: List[dict[str, Any]] = []

    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)

    for idx, block in enumerate(blocks, start=1):
        outer_html = str(block)
        try:
            event = _extract_event_via_llm(outer_html, url)
        except Exception:  # broad catch to skip bad blocks
            continue

        if not isinstance(event, dict):
            continue

        events.append(event)

        if debug_dir:
            with open(os.path.join(debug_dir, f"block_{idx}.html"), "w", encoding="utf-8") as f_html:
                f_html.write(outer_html)
            with open(os.path.join(debug_dir, f"block_{idx}.json"), "w", encoding="utf-8") as f_json:
                json.dump(event, f_json, indent=2)

    return events


def _extract_event_via_llm(html: str, source_url: str) -> dict[str, Any]:
    """Send HTML to an LLM and parse the resulting JSON."""
    if not OPENAI_API_KEY:
        raise LLMExtractionError("OPENAI_API_KEY environment variable not set")

    prompt = PROMPT_TEMPLATE.format(html=html)

    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=60)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:  # pragma: no cover - network errors
        if response.status_code == 429:
            raise RuntimeError(
                "OpenAI API returned status 429: there's a good chance the account is out of money."
            ) from exc
        raise

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
        event = json.loads(content)
    except (KeyError, json.JSONDecodeError) as exc:
        raise LLMExtractionError("Invalid JSON returned by LLM") from exc

    event.setdefault("source_url", source_url)
    if "tags" not in event or not isinstance(event["tags"], list):
        event["tags"] = []

    return event
