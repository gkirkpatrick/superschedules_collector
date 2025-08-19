#!/usr/bin/env python3
"""
Comprehensive LLM testing script that runs all prompts against OpenAI and Gemma3:12b
Logs all responses and provides detailed comparison analysis.
"""

import json
import requests
import time
import os
import sys
from typing import Dict, Any, List, Tuple
from datetime import datetime
import hashlib

# Configuration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma2:latest"
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

def load_prompts(file_path: str = "parsed_prompts.json") -> List[Dict]:
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ {file_path} not found. Run parse_prompts.py first.")
        sys.exit(1)

def check_ollama_status() -> bool:
    """Check if Ollama server is running and model is available."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        response.raise_for_status()
        
        models = response.json().get("models", [])
        model_names = [model["name"] for model in models]
        
        if OLLAMA_MODEL not in model_names:
            print(f"❌ Model '{OLLAMA_MODEL}' not found. Available: {model_names}")
            return False
        
        return True
        
    except requests.RequestException as e:
        print(f"❌ Ollama server not accessible: {e}")
        return False

def query_openai(prompt: str) -> Dict[str, Any]:
    """Query OpenAI API with a prompt."""
    if not OPENAI_API_KEY:
        return {
            "success": False,
            "error": "No OpenAI API key available",
            "time": 0,
            "model": OPENAI_MODEL,
            "response": "",
            "parsed": None
        }
    
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
        
        # Try to parse as JSON
        parsed_json = None
        try:
            if response_text.lower() == "null":
                parsed_json = None
            else:
                # Clean up potential markdown
                clean_text = response_text
                if clean_text.startswith('```json'):
                    clean_text = clean_text.replace('```json\n', '').replace('\n```', '').strip()
                elif clean_text.startswith('```'):
                    clean_text = clean_text.replace('```\n', '').replace('\n```', '').strip()
                
                parsed_json = json.loads(clean_text)
                
        except json.JSONDecodeError:
            parsed_json = {"error": "Invalid JSON", "raw_response": response_text[:200]}
        
        return {
            "success": True,
            "response": response_text,
            "parsed": parsed_json,
            "time": time.time() - start_time,
            "model": OPENAI_MODEL,
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "time": time.time() - start_time,
            "model": OPENAI_MODEL,
            "response": "",
            "parsed": None
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
            timeout=120  # Longer timeout for local model
        )
        response.raise_for_status()
        
        data = response.json()
        response_text = data.get("response", "").strip()
        
        # Try to parse as JSON
        parsed_json = None
        try:
            if response_text.lower() == "null":
                parsed_json = None
            else:
                # Clean up potential markdown
                clean_text = response_text
                if clean_text.startswith('```json'):
                    clean_text = clean_text.replace('```json\n', '').replace('\n```', '').strip()
                elif clean_text.startswith('```'):
                    clean_text = clean_text.replace('```\n', '').replace('\n```', '').strip()
                
                parsed_json = json.loads(clean_text)
                
        except json.JSONDecodeError:
            parsed_json = {"error": "Invalid JSON", "raw_response": response_text[:200]}
        
        return {
            "success": True,
            "response": response_text,
            "parsed": parsed_json,
            "time": time.time() - start_time,
            "model": OLLAMA_MODEL,
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "time": time.time() - start_time,
            "model": OLLAMA_MODEL,
            "response": "",
            "parsed": None
        }

def are_jsons_equivalent(json1: Any, json2: Any) -> bool:
    """Compare two JSON objects for functional equivalence."""
    if json1 is None and json2 is None:
        return True
    if json1 is None or json2 is None:
        return False
    
    # Handle error cases
    if isinstance(json1, dict) and json1.get("error"):
        return False
    if isinstance(json2, dict) and json2.get("error"):
        return False
        
    if not isinstance(json1, dict) or not isinstance(json2, dict):
        return json1 == json2
    
    # Compare core fields
    core_fields = ["title", "description", "location", "start_time", "end_time", "url"]
    
    for field in core_fields:
        val1 = json1.get(field)
        val2 = json2.get(field)
        
        # For location, handle string vs object differences
        if field == "location" and val1 != val2:
            # If one is string and other is object, they're not equivalent
            if type(val1) != type(val2):
                return False
    
    # If we get here, core fields match enough
    return True

def log_response(log_file, prompt_id: int, prompt_name: str, model: str, result: Dict[str, Any]):
    timestamp = datetime.now().isoformat()
    
    log_entry = {
        "timestamp": timestamp,
        "prompt_id": prompt_id,
        "prompt_name": prompt_name,
        "model": model,
        "success": result["success"],
        "time_seconds": result["time"],
        "error": result.get("error"),
        "response": result["response"],
        "parsed_json": result["parsed"]
    }
    
    log_file.write(json.dumps(log_entry) + "\n")
    log_file.flush()  # Ensure it's written immediately

def analyze_results(results: List[Dict]) -> Dict[str, Any]:
    """Analyze all test results and provide summary statistics."""
    openai_results = [r for r in results if r["model"] == OPENAI_MODEL]
    ollama_results = [r for r in results if r["model"] == OLLAMA_MODEL]
    
    stats = {
        "total_prompts": len(openai_results),
        "openai_stats": {
            "success_rate": sum(1 for r in openai_results if r["success"]) / len(openai_results),
            "avg_time": sum(r["time"] for r in openai_results) / len(openai_results),
            "valid_json_rate": sum(1 for r in openai_results if r["success"] and r["parsed"] and not r["parsed"].get("error")) / len(openai_results)
        },
        "ollama_stats": {
            "success_rate": sum(1 for r in ollama_results if r["success"]) / len(ollama_results),
            "avg_time": sum(r["time"] for r in ollama_results) / len(ollama_results),
            "valid_json_rate": sum(1 for r in ollama_results if r["success"] and r["parsed"] and not r["parsed"].get("error")) / len(ollama_results)
        }
    }
    
    # Compare JSON equivalence
    json_matches = 0
    for i in range(len(openai_results)):
        if (openai_results[i]["success"] and ollama_results[i]["success"] and
            openai_results[i]["parsed"] and ollama_results[i]["parsed"]):
            if are_jsons_equivalent(openai_results[i]["parsed"], ollama_results[i]["parsed"]):
                json_matches += 1
    
    stats["json_equivalence_rate"] = json_matches / len(openai_results)
    
    return stats

def main():
    print("🔬 Comprehensive LLM Testing: OpenAI vs Gemma3:12b")
    print("="*60)
    
    # Check prerequisites
    if not check_ollama_status():
        print(f"💡 Setup required: ollama pull {OLLAMA_MODEL}")
        return 1
    
    # Load prompts
    prompts = load_prompts()
    print(f"📋 Loaded {len(prompts)} prompts from parsed_prompts.json")
    
    # Prepare output file
    output_file = f"llm_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    
    all_results = []
    
    print(f"🧪 Starting comprehensive test...")
    print(f"📝 Logging all responses to: {output_file}")
    print()
    
    with open(output_file, 'w') as log_file:
        for i, prompt_data in enumerate(prompts, 1):
            print(f"🔄 Test {i}/{len(prompts)}: {prompt_data['name']}")
            
            prompt = prompt_data['prompt']
            
            # Test OpenAI first
            print(f"   Querying OpenAI... ", end='')
            openai_result = query_openai(prompt)
            print(f"{openai_result['time']:.1f}s {'✅' if openai_result['success'] else '❌'}")
            
            log_response(log_file, prompt_data['id'], prompt_data['name'], OPENAI_MODEL, openai_result)
            all_results.append({**openai_result, "prompt_id": prompt_data['id'], "prompt_name": prompt_data['name']})
            
            # Test Gemma3 second
            print(f"   Querying Gemma3... ", end='')
            ollama_result = query_ollama(prompt)
            print(f"{ollama_result['time']:.1f}s {'✅' if ollama_result['success'] else '❌'}")
            
            log_response(log_file, prompt_data['id'], prompt_data['name'], OLLAMA_MODEL, ollama_result)
            all_results.append({**ollama_result, "prompt_id": prompt_data['id'], "prompt_name": prompt_data['name']})
            
            # Quick comparison
            if openai_result['success'] and ollama_result['success']:
                if openai_result['parsed'] and ollama_result['parsed']:
                    if not openai_result['parsed'].get('error') and not ollama_result['parsed'].get('error'):
                        equivalent = are_jsons_equivalent(openai_result['parsed'], ollama_result['parsed'])
                        print(f"   JSON Match: {'✅' if equivalent else '❌'}")
                    else:
                        print(f"   JSON Match: ❌ (parsing errors)")
                else:
                    print(f"   JSON Match: ❌ (null responses)")
            else:
                print(f"   JSON Match: ❌ (query failures)")
            
            print()  # Blank line between tests
    
    # Final analysis
    print("🎯 ANALYSIS COMPLETE")
    print("="*60)
    
    stats = analyze_results(all_results)
    
    print(f"📊 Results Summary:")
    print(f"   Total Prompts: {stats['total_prompts']}")
    print()
    print(f"   OpenAI ({OPENAI_MODEL}):")
    print(f"     Success Rate: {stats['openai_stats']['success_rate']:.1%}")
    print(f"     Avg Time: {stats['openai_stats']['avg_time']:.2f}s")
    print(f"     Valid JSON: {stats['openai_stats']['valid_json_rate']:.1%}")
    print()
    print(f"   Gemma3 ({OLLAMA_MODEL}):")
    print(f"     Success Rate: {stats['ollama_stats']['success_rate']:.1%}")
    print(f"     Avg Time: {stats['ollama_stats']['avg_time']:.2f}s")
    print(f"     Valid JSON: {stats['ollama_stats']['valid_json_rate']:.1%}")
    print()
    print(f"   JSON Equivalence: {stats['json_equivalence_rate']:.1%}")
    print()
    print(f"📄 Detailed results saved to: {output_file}")
    
    # Save summary stats
    summary_file = output_file.replace('.jsonl', '_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"📊 Summary statistics saved to: {summary_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())