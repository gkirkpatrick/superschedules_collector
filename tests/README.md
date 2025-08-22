# Test Suite

This directory contains tests for the superschedules collector functionality.

## Test Files

### `test_pagination.py`
Tests pagination detection on various event listing sites.

**Usage:**
```bash
# Test with local HTML snapshots
python tests/test_pagination.py

# Test with live sites
python tests/test_pagination.py --live

# Test LLM features (requires --live and OPENAI_API_KEY)
python tests/test_pagination.py --live --test-llm

# Refresh local snapshots
python tests/test_pagination.py --refresh-snapshots
```

### `test_llm_hints.py`
Tests LLM-powered hints system and URL following strategy.

**Usage:**
```bash
# Test with local HTML snapshots (structure validation only)
python tests/test_llm_hints.py

# Test with live sites (full LLM functionality)
python tests/test_llm_hints.py --live

# Test only manual hints (faster)
python tests/test_llm_hints.py --live --manual-only
```

## Test Data

### `test_data/pagination_samples/`
Contains HTML snapshots from various event sites:

- `boston_gov.html` - Boston.gov events page
- `needhamlibrary_org.html` - Needham Library events  
- `brooklinelibrary_org.html` - Brookline Library events (old)
- `brooklinelibrary_events.html` - Brookline Library events (current)
- `cambridgema_gov.html` - Cambridge MA calendars page
- `cambridgema_citycalendar.html` - Cambridge MA city calendar

## Environment Setup

**Required:**
```bash
source collector_dev/bin/activate
```

**For LLM tests:**
```bash
export OPENAI_API_KEY="your-key-here"
# OR create ~/.secret_keys file with your key
```

## Test Coverage

**Pagination Detection:**
- CSS-based pagination (Boston, Cambridge)
- JavaScript pagination detection
- Numbered pagination patterns

**LLM Features:**
- Automatic hint discovery 
- Manual hints with CSS selectors
- URL following strategy for complex calendars
- Event extraction from individual pages

**Sites Tested:**
- ✅ Boston.gov - CSS pagination
- ✅ Needham Library - No pagination, JSON-LD events
- ✅ Brookline Library - Hints system (`.media.s-lc-c-evt`)
- ✅ Cambridge Calendar - URL following strategy (`.eventItem`)