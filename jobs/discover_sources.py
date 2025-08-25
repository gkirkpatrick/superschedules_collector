"""Build and expand the catalog of Eastern Massachusetts event sources."""
from __future__ import annotations
from pathlib import Path

from ingest.source_catalog import (
    EventSource,
    discover_from_seed,
    export_sources,
    load_sources,
    score_source,
    validate_source,
)

CATALOG_PATH = Path(__file__).resolve().parent.parent / "sources" / "eastern_massachusetts.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "sources" / "discovered_sources.json"


def main() -> None:
    """Load seed sources, discover new ones, and write results."""
    seeds = load_sources(CATALOG_PATH)
    discovered: list[EventSource] = []

    for seed in seeds:
        for url in discover_from_seed(seed.url):
            if validate_source(url):
                discovered.append(EventSource(name=url, url=url, type="unknown", city=""))

    for src in discovered:
        src.score = score_source(src.url)

    export_sources(discovered, OUTPUT_PATH)
    print(f"Discovered {len(discovered)} sources -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
