"""Shared data models for the collector service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Event:
    """Simple event schema used throughout the collector service."""

    title: str
    description: str
    location: str
    start_time: str
    end_time: str
    url: str
    image_url: Optional[str] = None
