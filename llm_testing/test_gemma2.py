#!/usr/bin/env python3
"""
Quick test comparing OpenAI vs Gemma2:latest (7B) for speed comparison
"""

import json
import requests
import time
import os
import sys
from typing import Dict, Any, List

# Configuration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma2:latest"  # 7B model for speed
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

# Load OpenAI key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    try:
        with open(os.path.expanduser("~/.secret_keys"), "r") as f:
            OPENAI_API_KEY = f.read().strip()
    except FileNotFoundError:
        OPENAI_API_KEY = None

def query_openai(prompt: str) -> Dict[str, Any]:
    """Query OpenAI API with a prompt."""
    start_time = time.time()
    
    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        response_text = data["choices"][0]["message"]["content"].strip()
        
        return {
            "success": True,
            "response": response_text,
            "time": time.time() - start_time,
            "model": OPENAI_MODEL
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "time": time.time() - start_time,
            "model": OPENAI_MODEL
        }

def query_ollama(prompt: str) -> Dict[str, Any]:
    """Query Ollama API with a prompt."""
    start_time = time.time()
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "top_p": 1,
        }
    }
    
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate", 
            json=payload, 
            timeout=60
        )
        response.raise_for_status()
        
        data = response.json()
        response_text = data.get("response", "").strip()
        
        return {
            "success": True,
            "response": response_text,
            "time": time.time() - start_time,
            "model": OLLAMA_MODEL
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "time": time.time() - start_time,
            "model": OLLAMA_MODEL
        }

def main():
    print("🚀 Speed Test: OpenAI vs Gemma2:7b")
    print("="*50)
    
    # Test with one real prompt
    test_prompt = """Return only valid JSON, no markdown or other text.

Schema: {"source_id": null, "external_id": "url_or_id", "title": "required", "description": "text", "location": "place", "start_time": "2024-01-01T10:00:00-05:00", "end_time": "time", "url": "link", "metadata_tags": ["categories", "event_types", "keywords"]}

Use Eastern timezone. Extract all relevant categories and keywords as tags. Return null if no event.

Content: 10:00am-11:30am
City Hall On The Go: West Roxbury
Roche Bros. West Roxbury
1800 Centre Street
Boston, MA 02132, United States
Price: FREE
Join us on August 19, 2025, for a scheduled stop at Roche Bros. West Roxbury at 1800 Centre Street, from 10:00 - 11:30 a.m.
URL: https://www.boston.gov/events"""

    # Test multiple runs for average
    runs = 3
    openai_times = []
    gemma2_times = []
    
    print(f"Running {runs} tests each...")
    
    for i in range(runs):
        print(f"\n--- Run {i+1}/{runs} ---")
        
        # Test OpenAI
        print("Testing OpenAI...", end=' ')
        openai_result = query_openai(test_prompt)
        if openai_result['success']:
            openai_times.append(openai_result['time'])
            print(f"{openai_result['time']:.2f}s ✅")
        else:
            print(f"❌ {openai_result['error']}")
        
        # Test Gemma2
        print("Testing Gemma2...", end=' ')
        gemma2_result = query_ollama(test_prompt)
        if gemma2_result['success']:
            gemma2_times.append(gemma2_result['time'])
            print(f"{gemma2_result['time']:.2f}s ✅")
        else:
            print(f"❌ {gemma2_result['error']}")
    
    # Calculate averages
    if openai_times and gemma2_times:
        openai_avg = sum(openai_times) / len(openai_times)
        gemma2_avg = sum(gemma2_times) / len(gemma2_times)
        speedup = openai_avg / gemma2_avg if gemma2_avg > 0 else 0
        
        print(f"\n🏆 RESULTS:")
        print(f"OpenAI Average: {openai_avg:.2f}s")
        print(f"Gemma2 Average: {gemma2_avg:.2f}s")
        print(f"Speed Comparison: Gemma2 is {speedup:.1f}x {'faster' if speedup > 1 else 'slower'} than OpenAI")
        
        # Show one response comparison
        if openai_result['success'] and gemma2_result['success']:
            print(f"\n📝 Sample Response Comparison:")
            print(f"\nOpenAI response length: {len(openai_result['response'])} chars")
            print(f"Gemma2 response length: {len(gemma2_result['response'])} chars")
            
            # Try to parse JSON from both
            try:
                openai_json = json.loads(openai_result['response'])
                print(f"OpenAI JSON: ✅ Valid")
            except:
                print(f"OpenAI JSON: ❌ Invalid")
            
            try:
                # Clean up markdown if present
                response = gemma2_result['response']
                if response.startswith('```json'):
                    response = response.replace('```json\n', '').replace('\n```', '').strip()
                gemma2_json = json.loads(response)
                print(f"Gemma2 JSON: ✅ Valid")
            except:
                print(f"Gemma2 JSON: ❌ Invalid")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())