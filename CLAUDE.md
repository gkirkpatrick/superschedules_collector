# Superschedules Project Summary

## Vision
AI-powered local events discovery platform where users ask natural language questions like:
> "I have a 3 and 5 year old, I'm in Newton, MA and need something to do in the next 3 hours"

Instead of browsing calendars, get intelligent, contextual event recommendations powered by RAG.

## Architecture Overview
```
URLs → Collector → Backend → RAG → Natural Language Interface
```

## Four Repositories

### 1. **superschedules_frontend** (React)
- **Status:** Basic working state
- **Features:** 
  - Authentication system working
  - URL submission for parsing
  - Calendar display for events
  - No other event viewing methods yet

### 2. **superschedules** (Django Backend)
- **Status:** Basic working state  
- **Features:**
  - Event storage API
  - Authentication with API tokens

### 3. **superschedules_collector** (Python - This Repo)
- **Status:** Refactored to extraction-only service
- **Features:**
  - Single URL → JSON events extraction
  - Hierarchical scraping: JSON-LD → LLM fallback
  - LLM validation and semantic tagging
  - FastAPI server with `/extract` endpoint (port 8001)
  - Playwright rendering for dynamic content
  - OpenAI structured output with confidence scoring

### 4. **superschedules_IAC** (Terraform)
- **Status:** Basic deployment setup
- **Purpose:** Infrastructure as Code for deployment

## Current Collector Architecture (Extraction-Only)

### Simplified Flow
1. **Django Backend** → POST `/extract` with URL + hints
2. **JSON-LD Scraper** → `scrapers/jsonld_scraper.py` (first attempt)
3. **LLM Scraper** → `scrapers/llm_scraper.py` (fallback)
4. **Event Validator** → `scrapers/event_validator.py` (LLM tagging & validation)
5. **Return JSON** → Structured events back to Django

### Key Files
- `api/main.py` - FastAPI server with `/extract` endpoint
- `scrapers/event_validator.py` - LLM validation and tagging
- `start_api.py` - Server startup script

### Removed (Django Backend Handles)
- URL queue management
- Pagination detection and following
- Event storage and deduplication
- Job orchestration and retry logic

### Environment Setup
- Virtual env: `collector_dev/`
- Dependencies: `requirements.txt` (FastAPI, OpenAI, Playwright, etc.)
- Config: `.env` file with `API_URL`, `API_TOKEN`, `OPENAI_API_KEY`
- Secret keys: `~/.secret_keys` (fallback for OpenAI key)

## Next Phase: RAG Implementation

### Planned Data Flow
```
User Query: "Activities for 3-5 year olds in Newton, next 3 hours"
     ↓
LLM Query Parser: Extract ages=3-5, location=Newton, time=next 3h  
     ↓
Database Filter: Filter events by time/location/age constraints
     ↓
Vector Search: Find semantically similar events for "activities for young children"
     ↓
LLM Response: Generate natural language recommendations
```

### Vector Embedding Strategy
- **Implementation:** Needs exploration and prototyping
- **Key decisions:** What to embed, storage approach, search ranking

## Current Status
- ✅ **Event Collection:** Fully working with 49 events extracted from Needham Library
- ✅ **Backend Integration:** Successfully posting events with proper authentication
- ✅ **FastAPI Server:** Ready for frontend integration
- ⏳ **RAG System:** Planning phase - vector embeddings and natural language interface
- ⏳ **Frontend Integration:** Connect React app to collector API
- ⏳ **Production Deployment:** Terraform infrastructure scaling

## Portfolio Value
This project demonstrates:
- **Full-stack development** (React, Django, Python services)
- **AI/ML integration** (LLM-powered scraping, planned RAG system)
- **Modern API design** (FastAPI with proper models, health endpoints)
- **Real-world complexity** (authentication, pagination, error handling)
- **Infrastructure as Code** (Terraform deployment)
- **Intelligent web scraping** (hierarchical fallbacks, dynamic content)

## Future Generalization: "get-my-JSON"
Long-term vision to generalize the collector into a universal web data extraction engine:
- Give it any schema + URL + hints → get structured JSON
- Market applications: e-commerce, real estate, job listings, etc.
- See GitHub Issue #35 for detailed concept

---

*Last updated: [Current Date]*
*Current focus: Planning RAG implementation for natural language event discovery*