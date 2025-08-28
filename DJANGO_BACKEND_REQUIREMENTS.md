# Django Backend Requirements for Collector Refactoring

## Overview
The collector is being refactored from a decision-making orchestrator to a pure extraction service. The Django backend needs to take over URL management, pagination, and orchestration logic.

## New Collector Interface (After Refactoring)

### Single Endpoint
```
POST /extract
{
  "url": "https://example.com/events",
  "extraction_hints": {
    "expected_event_count": 10,
    "date_format_hints": ["MM/dd/yyyy", "yyyy-MM-dd"],
    "content_selectors": [".event-item", "[data-event]"]
  },
  "schema_requirements": {
    "required_fields": ["title", "date"],
    "optional_fields": ["description", "location", "url"]
  }
}
```

### Response
```json
{
  "success": true,
  "events": [...],
  "metadata": {
    "extraction_method": "jsonld|llm|enhanced",
    "page_title": "Events Calendar",
    "total_found": 15
  }
}
```

## Django Backend Needs to Implement

### 1. URL Queue Management
```python
# models.py
class EventSource(models.Model):
    base_url = models.URLField()
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    last_scraped = models.DateTimeField(null=True)
    scrape_frequency = models.DurationField(default=timedelta(hours=24))

class ScrapingJob(models.Model):
    source = models.ForeignKey(EventSource, on_delete=models.CASCADE)
    url = models.URLField()  # specific page URL
    status = models.CharField(choices=[('pending', 'pending'), ('running', 'running'), ('completed', 'completed'), ('failed', 'failed')])
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
    error_message = models.TextField(blank=True)
    events_found = models.IntegerField(default=0)
```

### 2. Pagination Discovery & Management
The collector currently has pagination logic in:
- `scrapers/page_event_scraper.py:detect_pagination()` (lines 400-450)
- `test_pagination.py` - various pagination detection methods

**Backend should implement:**
```python
class PaginationManager:
    def discover_pages(self, base_url: str) -> List[str]:
        """Call collector to detect pagination, return list of URLs to scrape"""
        
    def queue_pagination_jobs(self, source: EventSource, discovered_urls: List[str]):
        """Create ScrapingJob entries for each discovered page"""
```

### 3. Orchestration Service
```python
class ScrapingOrchestrator:
    def schedule_source_scraping(self, source: EventSource):
        """Main entry point - discover pages and queue jobs"""
        
    def process_scraping_job(self, job: ScrapingJob):
        """Call collector extraction service for single URL"""
        
    def handle_extraction_result(self, job: ScrapingJob, result: dict):
        """Process events from collector, handle duplicates, store in Event model"""
```

### 4. Event Deduplication
```python
class EventDeduplicator:
    def find_duplicates(self, new_event: dict, source: EventSource) -> QuerySet:
        """Detect potential duplicate events"""
        
    def merge_or_update(self, existing_event: Event, new_data: dict):
        """Handle duplicate resolution"""
```

## Migration Strategy

### Phase 1: Extract Current Logic
From collector, move to Django:
- URL discovery patterns from `scrapers/page_event_scraper.py:detect_pagination()`
- Retry logic from `jobs/process_url.py`
- Error handling patterns

### Phase 2: API Integration
- Update Django to call simplified collector API
- Implement job queue processing
- Add admin interface for monitoring scraping jobs

### Phase 3: Remove from Collector
- Delete pagination logic
- Delete URL management
- Delete job processing
- Keep only: single URL → JSON extraction

## Current Collector Files to Reference

### Keep & Simplify
- `scrapers/jsonld_scraper.py` - core extraction logic
- `scrapers/llm_scraper.py` - LLM fallback extraction  
- `scrapers/page_event_scraper.py` - enhanced scraping (remove pagination parts)
- `api/main.py` - FastAPI endpoints (simplify to single /extract)

### Logic to Port to Django
- `jobs/process_url.py` - job orchestration
- `test_pagination.py` - pagination detection methods
- `scrapers/page_event_scraper.py:detect_pagination()` - pagination discovery

### Remove Completely
- `llm_testing/` directory - comparison tools
- All bulk scraper files (`jobs/bulk_*.py`)
- Test files with "bulk", "overnight", "harvard" in name
- `ingest/api_client.py` - backend posting (Django will handle storage directly)

## Benefits of This Refactoring
1. **Single Responsibility:** Collector only extracts, Django only orchestrates
2. **Scalability:** Django can manage multiple collector instances
3. **Reliability:** Better error handling and retry logic in Django
4. **Monitoring:** Django admin for scraping job status
5. **Flexibility:** Easy to add new event sources without touching collector

## Questions for Implementation
1. How do you want to handle authentication between Django and collector?
2. Should collector still validate against OpenAI schema, or just return raw extraction?
3. Do you want real-time scraping or batch job processing?
4. How should duplicate detection work across multiple sources?