"""Send a dummy source to the backend to verify auth."""
from __future__ import annotations

from ingest.api_client import post_dummy_source


if __name__ == "__main__":
    try:
        result = post_dummy_source()
        print("Response:", result)
    except Exception as exc:  # pragma: no cover - debugging script
        print("Request failed:", exc)
