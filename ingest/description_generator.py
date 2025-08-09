"""Generate short event descriptions using OpenAI."""
from __future__ import annotations

from typing import Any

from openai import APIStatusError, OpenAI

client = OpenAI()

PROMPT_TEMPLATE = (
    "Write a brief, friendly description for a community calendar event.\n"
    "Title: {title}\n"
    "Location: {location}\n"
    "Start: {start_time}\n"
    "End: {end_time}\n"
    "Description:"
)


def generate_description(event: dict[str, Any]) -> str:
    """Return an LLM-generated description for ``event``.

    The event dict should have ``title``, ``location``, ``start_time`` and
    ``end_time`` fields. Missing fields are treated as blank strings.
    """
    prompt = PROMPT_TEMPLATE.format(
        title=event.get("title", ""),
        location=event.get("location", ""),
        start_time=event.get("start_time", ""),
        end_time=event.get("end_time", ""),
    )
    try:
        resp = client.responses.create(model="o4-mini", input=prompt)
    except APIStatusError as exc:  # pragma: no cover - network errors
        raise RuntimeError("OpenAI API request failed") from exc
    # ``output_text`` returns the combined text content from the response
    return resp.output_text.strip()
