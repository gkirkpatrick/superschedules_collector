from ingest.source_catalog import load_sources


def test_load_sources_minimum_count():
    sources = load_sources()
    assert len(sources) >= 50
    first = sources[0]
    assert first.name and first.url
