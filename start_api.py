#!/usr/bin/env python3
"""
Startup script for the Superschedules Collector API server.

Usage:
    python start_api.py              # Development mode
    python start_api.py --prod       # Production mode
    python start_api.py --port 8080  # Custom port
"""

import argparse
import uvicorn


def main():
    """Start the FastAPI server with configurable options."""
    parser = argparse.ArgumentParser(description="Start Superschedules Collector API")
    parser.add_argument(
        "--host", 
        default="0.0.0.0", 
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8001, 
        help="Port to bind to (default: 8001)"
    )
    parser.add_argument(
        "--prod", 
        action="store_true", 
        help="Run in production mode (no auto-reload, optimized)"
    )
    parser.add_argument(
        "--workers", 
        type=int, 
        default=1, 
        help="Number of worker processes (default: 1)"
    )
    
    args = parser.parse_args()
    
    if args.prod:
        print(f"🚀 Starting Superschedules Collector API in PRODUCTION mode")
        print(f"   📍 http://{args.host}:{args.port}")
        print(f"   👷 {args.workers} worker(s)")
        
        uvicorn.run(
            "api.main:app",
            host=args.host,
            port=args.port,
            workers=args.workers,
            log_level="info"
        )
    else:
        print(f"🔧 Starting Superschedules Collector API in DEVELOPMENT mode")
        print(f"   📍 http://{args.host}:{args.port}")
        print(f"   🔄 Auto-reload enabled")
        print(f"   📚 API docs: http://{args.host}:{args.port}/docs")
        print(f"   ℹ️  Port 8001 avoids conflict with main backend on port 8000")
        
        uvicorn.run(
            "api.main:app",
            host=args.host,
            port=args.port,
            reload=True,
            log_level="debug"
        )


if __name__ == "__main__":
    main()