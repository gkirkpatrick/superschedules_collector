"""FastAPI application for Superschedules Collector API."""
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import your existing modules
from scrapers.jsonld_scraper import extract_events_from_page
from scrapers.llm_scraper import scrape_events_with_llm
from scrapers.pagination_detector import detect_pagination

app = FastAPI(
    title="Superschedules Collector API",
    description="API for collecting and processing event data from websites",
    version="1.0.0",
)


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
    additional_info: Optional[Dict] = None


class ScrapeResponse(BaseModel):
    """Response model for scraping operations."""
    url: str
    events_found: int
    events: List[EventModel]
    pagination_detected: bool
    next_pages: Optional[List[str]] = None
    processing_time_seconds: float


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
    Scrape events from a given URL using specified methods.
    
    This is the main endpoint that would be used by your tool.
    """
    start_time = datetime.utcnow()
    
    try:
        # Start with empty results
        all_events = []
        pagination_info = None
        
        # Try JSON-LD first if requested
        if "jsonld" in request.search_methods:
            try:
                jsonld_events = extract_events_from_page(request.url)
                all_events.extend(jsonld_events)
            except Exception as e:
                # Log error but continue with other methods
                print(f"JSON-LD extraction failed: {e}")
        
        # Try LLM scraping if no events found or explicitly requested
        if "llm" in request.search_methods and len(all_events) == 0:
            try:
                llm_events = scrape_events_with_llm(
                    request.url, 
                    target_tags=request.event_tags or []
                )
                all_events.extend(llm_events)
            except Exception as e:
                print(f"LLM scraping failed: {e}")
        
        # Check for pagination
        try:
            # You'll need to implement this based on your pagination detector
            # pagination_info = detect_pagination(request.url, html_content)
            pagination_detected = False
            next_pages = []
        except Exception as e:
            print(f"Pagination detection failed: {e}")
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