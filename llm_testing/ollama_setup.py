#!/usr/bin/env python3
"""
Ollama setup and model management helper.

This script helps you set up and manage Ollama models for testing.
"""

import requests
import subprocess
import sys
import time

OLLAMA_BASE_URL = "http://localhost:11434"

# Recommended models for event extraction (ordered by performance vs speed)
RECOMMENDED_MODELS = [
    {
        "name": "llama3.2:1b", 
        "size": "~1GB", 
        "description": "Fastest, good for basic extraction",
        "good_for": "Quick testing, fast responses"
    },
    {
        "name": "llama3.2:3b", 
        "size": "~2GB", 
        "description": "Better accuracy, still fast",
        "good_for": "Good balance of speed and accuracy"
    },
    {
        "name": "qwen2.5:7b", 
        "size": "~4GB", 
        "description": "High accuracy, excellent JSON handling",
        "good_for": "Best results, if you have the resources"
    },
    {
        "name": "llama3.1:8b", 
        "size": "~4.7GB", 
        "description": "Very good accuracy, slower",
        "good_for": "High quality extraction"
    }
]

def check_ollama_installed():
    try:
        result = subprocess.run(['ollama', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Ollama installed: {result.stdout.strip()}")
            return True
        return False
    except FileNotFoundError:
        return False

def check_ollama_server():
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama server is running")
            return True
        return False
    except requests.RequestException:
        return False

def list_installed_models():
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            if models:
                print(f"\n📦 Installed models ({len(models)}):")
                for model in models:
                    name = model["name"]
                    size = model.get("size", 0)
                    size_gb = size / (1024**3) if size > 0 else 0
                    print(f"  • {name} ({size_gb:.1f}GB)")
                return [model["name"] for model in models]
            else:
                print("\n📦 No models installed")
                return []
    except requests.RequestException:
        print("❌ Could not connect to Ollama server")
        return []

def pull_model(model_name: str):
    print(f"\n⬇️  Pulling model: {model_name}")
    print("This may take a few minutes depending on model size...")
    
    try:
        # Use subprocess to show progress
        result = subprocess.run(['ollama', 'pull', model_name], 
                              capture_output=False, text=True)
        if result.returncode == 0:
            print(f"✅ Successfully pulled {model_name}")
            return True
        else:
            print(f"❌ Failed to pull {model_name}")
            return False
    except Exception as e:
        print(f"❌ Error pulling model: {e}")
        return False

def test_model(model_name: str):
    test_prompt = "Extract event info as JSON: 'Concert tonight at 8pm, City Hall, $20'"
    
    payload = {
        "model": model_name,
        "prompt": test_prompt,
        "stream": False
    }
    
    try:
        print(f"🧪 Testing {model_name}...")
        start_time = time.time()
        
        response = requests.post(f"{OLLAMA_BASE_URL}/api/generate", 
                               json=payload, timeout=30)
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json().get("response", "")
            print(f"✅ {model_name} responded in {elapsed:.1f}s")
            print(f"Response preview: {result[:100]}...")
            return True
        else:
            print(f"❌ {model_name} failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing {model_name}: {e}")
        return False

def main():
    print("🦙 Ollama Setup Helper")
    print("="*50)
    
    # Check if Ollama is installed
    if not check_ollama_installed():
        print("❌ Ollama not installed")
        print("\n💡 Install with:")
        print("curl -fsSL https://ollama.ai/install.sh | sh")
        return
    
    # Check if server is running
    if not check_ollama_server():
        print("❌ Ollama server not running")
        print("\n💡 Start server with:")
        print("ollama serve")
        print("\n(Run in a separate terminal window)")
        return
    
    # List installed models
    installed = list_installed_models()
    
    # Show recommendations
    print(f"\n🎯 Recommended models for event extraction:")
    for i, model in enumerate(RECOMMENDED_MODELS, 1):
        status = "✅ INSTALLED" if model["name"] in installed else "❌ Not installed"
        print(f"{i}. {model['name']} ({model['size']}) - {status}")
        print(f"   {model['description']}")
        print(f"   Good for: {model['good_for']}")
        print()
    
    # Interactive menu
    while True:
        print("\n🔧 What would you like to do?")
        print("1. Pull a recommended model")
        print("2. Test an installed model")
        print("3. Show installation status")
        print("4. Exit")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            print("\n📥 Select model to pull:")
            for i, model in enumerate(RECOMMENDED_MODELS, 1):
                print(f"{i}. {model['name']} ({model['size']})")
            
            try:
                model_choice = int(input("\nEnter model number: ")) - 1
                if 0 <= model_choice < len(RECOMMENDED_MODELS):
                    model = RECOMMENDED_MODELS[model_choice]
                    if pull_model(model["name"]):
                        test_model(model["name"])
                else:
                    print("Invalid choice")
            except ValueError:
                print("Please enter a number")
        
        elif choice == "2":
            installed = list_installed_models()
            if not installed:
                print("No models installed")
                continue
                
            print("\n🧪 Select model to test:")
            for i, model in enumerate(installed, 1):
                print(f"{i}. {model}")
            
            try:
                model_choice = int(input("\nEnter model number: ")) - 1
                if 0 <= model_choice < len(installed):
                    test_model(installed[model_choice])
                else:
                    print("Invalid choice")
            except ValueError:
                print("Please enter a number")
        
        elif choice == "3":
            list_installed_models()
        
        elif choice == "4":
            break
        
        else:
            print("Invalid choice")
    
    print("\n🎯 Ready to test! Run:")
    print("python compare_llms.py")

if __name__ == "__main__":
    main()