"""FastAPI application for Superschedules Collector API."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import your existing modules
from scrapers.jsonld_scraper import scrape_events_from_jsonld
from scrapers.llm_scraper import scrape_events_from_llm
from scrapers.event_validator import validate_and_enhance_events

app = FastAPI(
    title="Superschedules Collector API",
    description="API for collecting and processing event data from websites",
    version="1.0.0",
)

# Thread pool for running sync code in async context
executor = ThreadPoolExecutor(max_workers=4)


class EventModel(BaseModel):
    """Event data model with LLM-enhanced tags."""
    external_id: str
    title: str
    description: str
    location: str
    start_time: str  # ISO datetime string
    end_time: Optional[str] = None  # ISO datetime string
    url: Optional[str] = None
    tags: Optional[List[str]] = None  # LLM-generated tags from description
    validation_score: Optional[float] = None  # LLM confidence in extraction accuracy


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str


class ExtractionHints(BaseModel):
    """Hints to help with extraction."""
    expected_event_count: Optional[int] = None
    date_format_hints: Optional[List[str]] = None
    content_selectors: Optional[List[str]] = None
    additional_hints: Optional[Dict] = None


class SchemaRequirements(BaseModel):
    """Schema requirements for extracted events."""
    required_fields: List[str] = ["title", "date"]
    optional_fields: List[str] = ["description", "location", "url"]


class ExtractRequest(BaseModel):
    """Request model for event extraction."""
    url: str
    extraction_hints: Optional[ExtractionHints] = None
    schema_requirements: Optional[SchemaRequirements] = None


class ExtractResponse(BaseModel):
    """Response model for event extraction."""
    success: bool
    events: List[EventModel]
    metadata: Dict
    processing_time_seconds: float


def _extract_events_sync(url: str, hints: Optional[ExtractionHints] = None) -> Dict:
    """Synchronous event extraction function to run in thread pool."""
    all_events = []
    extraction_method = "none"
    
    # Try JSON-LD first (fastest, most reliable)
    try:
        jsonld_events = scrape_events_from_jsonld(url)
        if jsonld_events:
            all_events.extend(jsonld_events)
            extraction_method = "jsonld"
            print(f"JSON-LD extraction successful: {len(jsonld_events)} events")
    except Exception as e:
        print(f"JSON-LD extraction failed: {e}")
    
    # Try LLM scraping if no events found
    if len(all_events) == 0:
        try:
            # Convert hints to old format if provided
            old_hints = None
            if hints and hints.content_selectors:
                old_hints = {"event_containers": hints.content_selectors}
            
            llm_events = scrape_events_from_llm(url, hints=old_hints)
            if llm_events:
                all_events.extend(llm_events)
                extraction_method = "llm"
                print(f"LLM extraction successful: {len(llm_events)} events")
        except Exception as e:
            print(f"LLM scraping failed: {e}")
            extraction_method = "failed"
    
    # Validate and enhance events with LLM tags
    if all_events:
        try:
            enhanced_events = validate_and_enhance_events(all_events)
            all_events = enhanced_events
            print(f"Events validated and enhanced with tags")
        except Exception as e:
            print(f"Event validation failed: {e}")
    
    return {
        "events": all_events,
        "extraction_method": extraction_method
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0"
    )


@app.get("/live", response_model=HealthResponse)
async def liveness_check():
    """Liveness check endpoint for container orchestration."""
    return HealthResponse(
        status="alive",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0"
    )


@app.get("/ready", response_model=HealthResponse)
async def readiness_check():
    """Readiness check endpoint for container orchestration."""
    # You can add actual dependency checks here later
    # e.g., database connectivity, external API availability
    return HealthResponse(
        status="ready",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0"
    )


@app.post("/extract", response_model=ExtractResponse)
async def extract_events(request: ExtractRequest):
    """
    Extract events from a single URL with optional hints and validation.
    
    This endpoint:
    - Tries JSON-LD first, falls back to LLM extraction
    - Validates events and generates semantic tags using LLM
    - Returns structured events ready for Django backend
    """
    start_time = datetime.now(timezone.utc)
    
    try:
        # Run extraction in thread pool to avoid asyncio conflicts with Playwright
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            _extract_events_sync,
            request.url,
            request.extraction_hints
        )
        
        events = result["events"]
        extraction_method = result["extraction_method"]
        
        # Calculate processing time
        end_time = datetime.now(timezone.utc)
        processing_time = (end_time - start_time).total_seconds()
        
        # Get page title for metadata (simple approach)
        page_title = "Unknown"
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(request.url)
                page_title = page.title()
                browser.close()
        except Exception:
            pass  # Not critical if we can't get title
        
        return ExtractResponse(
            success=len(events) > 0,
            events=[EventModel(**event) for event in events],
            metadata={
                "extraction_method": extraction_method,
                "page_title": page_title,
                "total_found": len(events)
            },
            processing_time_seconds=processing_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Superschedules Collector API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)