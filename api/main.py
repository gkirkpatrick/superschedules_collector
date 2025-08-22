"""FastAPI application for Superschedules Collector API."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import your existing modules
from scrapers.jsonld_scraper import scrape_events_from_jsonld
from scrapers.llm_scraper import scrape_events_from_llm, discover_event_hints
from scrapers.pagination_detector import detect_pagination
from api.hints_client import get_cached_hints, cache_hints, update_strategy_success

app = FastAPI(
    title="Superschedules Collector API",
    description="API for collecting and processing event data from websites",
    version="1.0.0",
)

# Thread pool for running sync code in async context
executor = ThreadPoolExecutor(max_workers=4)


class EventModel(BaseModel):
    """Event data model matching your current schema."""
    source_id: Optional[int] = None
    external_id: str
    title: str
    description: str
    location: str
    start_time: str  # ISO datetime string
    end_time: Optional[str] = None  # ISO datetime string
    url: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str


class ScrapeRequest(BaseModel):
    """Request model for scraping endpoints."""
    url: str
    search_methods: Optional[List[str]] = ["jsonld", "llm"]
    event_tags: Optional[List[str]] = None
    hints: Optional[Dict] = None  # CSS selectors and other scraping hints
    auto_discover_hints: Optional[bool] = False  # Enable automatic hint discovery
    follow_event_urls: Optional[bool] = False  # Follow individual event URLs
    use_cached_hints: Optional[bool] = True  # Use cached hints from previous scrapes
    cache_discovered_hints: Optional[bool] = True  # Cache newly discovered hints
    additional_info: Optional[Dict] = None


class ScrapeResponse(BaseModel):
    """Response model for scraping operations."""
    url: str
    events_found: int
    events: List[EventModel]
    pagination_detected: bool
    next_pages: Optional[List[str]] = None
    hints_used: Optional[Dict] = None  # Hints that were used for scraping
    hints_discovered: Optional[Dict] = None  # New hints discovered during scraping
    hints_cached: Optional[bool] = None  # Whether hints were stored in backend
    processing_time_seconds: float


def _scrape_sync(url: str, search_methods: List[str], hints: Optional[Dict] = None, 
                auto_discover_hints: bool = False, follow_event_urls: bool = False,
                use_cached_hints: bool = True, cache_discovered_hints: bool = True) -> Dict:
    """Synchronous scraping function to run in thread pool."""
    all_events = []
    hints_used = hints
    hints_discovered = None
    hints_cached = False
    
    # Try to get cached hints if no manual hints provided and caching is enabled
    if use_cached_hints and not hints:
        cached_hints = get_cached_hints(url)
        if cached_hints:
            hints_used = cached_hints
            print(f"Using cached hints for {url}: {cached_hints.get('event_containers', [])}")
    
    # Try JSON-LD first if requested
    if "jsonld" in search_methods:
        try:
            jsonld_events = scrape_events_from_jsonld(url)
            all_events.extend(jsonld_events)
        except Exception as e:
            print(f"JSON-LD extraction failed: {e}")
    
    # Try LLM scraping if no events found or explicitly requested
    if "llm" in search_methods and len(all_events) == 0:
        try:
            # Auto-discover hints if requested and no manual/cached hints provided
            if auto_discover_hints and not hints_used:
                print(f"Auto-discovering hints for {url}")
                discovered_hints = discover_event_hints(url)
                if discovered_hints.get("event_containers"):
                    hints_used = discovered_hints
                    hints_discovered = discovered_hints
                    print(f"Discovered hints: {discovered_hints['event_containers']}")
            
            # Scrape with hints
            llm_events = scrape_events_from_llm(
                url,
                hints=hints_used,
                auto_discover_hints=auto_discover_hints,
                follow_event_urls=follow_event_urls
            )
            all_events.extend(llm_events)
        except Exception as e:
            print(f"LLM scraping failed: {e}")
    
    # Cache discovered hints if enabled and we found new ones
    if cache_discovered_hints and hints_discovered and len(all_events) > 0:
        try:
            hints_cached = cache_hints(url, hints_discovered, success=True)
            if hints_cached:
                print(f"Cached discovered hints for {url}")
        except Exception as e:
            print(f"Failed to cache hints: {e}")
    
    # Update success rate
    try:
        update_strategy_success(url, len(all_events) > 0)
    except Exception as e:
        print(f"Failed to update success rate: {e}")
    
    return {
        "events": all_events,
        "hints_used": hints_used,
        "hints_discovered": hints_discovered,
        "hints_cached": hints_cached
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0"
    )


@app.get("/live", response_model=HealthResponse)
async def liveness_check():
    """Liveness check endpoint for container orchestration."""
    return HealthResponse(
        status="alive",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0"
    )


@app.get("/ready", response_model=HealthResponse)
async def readiness_check():
    """Readiness check endpoint for container orchestration."""
    # You can add actual dependency checks here later
    # e.g., database connectivity, external API availability
    return HealthResponse(
        status="ready",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0"
    )


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_events(request: ScrapeRequest):
    """
    Scrape events from a given URL using specified methods with hints support.
    
    This endpoint supports:
    - Manual hints (CSS selectors for event containers)
    - Automatic hint discovery using LLM
    - URL following strategy for complex calendars
    """
    start_time = datetime.utcnow()
    
    try:
        # Run scraping in thread pool to avoid asyncio conflicts with Playwright
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            _scrape_sync,
            request.url,
            request.search_methods,
            request.hints,
            request.auto_discover_hints,
            request.follow_event_urls,
            request.use_cached_hints,
            request.cache_discovered_hints
        )
        
        all_events = result["events"]
        hints_used = result["hints_used"]
        hints_discovered = result["hints_discovered"]
        hints_cached = result["hints_cached"]
        
        # Basic pagination detection - you can enhance this later
        pagination_detected = False
        next_pages = []
        
        # Calculate processing time
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        return ScrapeResponse(
            url=request.url,
            events_found=len(all_events),
            events=[EventModel(**event) for event in all_events],
            pagination_detected=pagination_detected,
            next_pages=next_pages,
            hints_used=hints_used,
            hints_discovered=hints_discovered,
            hints_cached=hints_cached,
            processing_time_seconds=processing_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


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