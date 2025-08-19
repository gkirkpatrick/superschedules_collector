#!/usr/bin/env python3
"""
Unified LLM Testing Framework

This script runs comprehensive tests across multiple LLM providers and models
based on configuration in config.yaml.

Features:
- Multi-provider support (OpenAI, Anthropic, Ollama)
- Context size testing
- Configurable authentication
- Detailed logging and analysis
- JSON schema validation
- Performance comparison
"""

import json
import yaml
import requests
import time
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass


@dataclass
class TestConfig:
    """Configuration for a single test run."""
    model_id: str
    model_config: Dict[str, Any]
    context_size: int
    prompt_data: Dict[str, Any]


@dataclass  
class TestResult:
    """Result from a single LLM test."""
    model_id: str
    context_size: int
    prompt_id: int
    prompt_name: str
    success: bool
    response_time: float
    response_text: str
    parsed_json: Optional[Dict[str, Any]]
    error: Optional[str]
    timestamp: str


class LLMTestRunner:
    """Main test runner that orchestrates LLM testing."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.results: List[TestResult] = []
        self.setup_logging()
        
    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"❌ Config file {self.config_path} not found")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"❌ Error parsing config file: {e}")
            sys.exit(1)
            
    def setup_logging(self):
        level = getattr(logging, self.config['advanced']['log_level'].upper())
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def load_prompts(self) -> List[Dict[str, Any]]: 
        prompts_file = self.config['test_data']['prompts_file']
        try:
            with open(prompts_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error(f"Prompts file {prompts_file} not found")
            sys.exit(1)
            
    def get_auth_key(self, auth_config: Dict[str, Any]) -> Optional[str]:
        if auth_config['type'] == 'none':
            return None
            
        # Try environment variable first
        if 'key_env' in auth_config:
            key = os.getenv(auth_config['key_env'])
            if key:
                return key
                
        # Try key file
        if 'key_file' in auth_config:
            key_file = os.path.expanduser(auth_config['key_file'])
            try:
                with open(key_file, 'r') as f:
                    return f.read().strip()
            except FileNotFoundError:
                pass
                
        return None
        
    def check_model_availability(self, model_config: Dict[str, Any]) -> bool:
        provider = model_config['provider']
        
        if provider == 'ollama':
            return self._check_ollama_model(model_config['name'])
        elif provider in ['openai', 'anthropic']:
            auth_key = self.get_auth_key(self.config['auth'][provider])
            return auth_key is not None
        
        return False
        
    def _check_ollama_model(self, model_name: str) -> bool:
        """Check if Ollama model is available locally."""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            response.raise_for_status()
            models = response.json().get("models", [])
            available_models = [m["name"] for m in models]
            return model_name in available_models
        except requests.RequestException:
            return False
            
    def query_openai(self, model_config: Dict[str, Any], prompt: str, context_size: int) -> TestResult:
        start_time = time.time()
        auth_key = self.get_auth_key(self.config['auth']['openai'])
        
        if not auth_key:
            return TestResult(
                model_id=f"{model_config['name']}_{context_size}",
                context_size=context_size,
                prompt_id=0, prompt_name="", success=False,
                response_time=0, response_text="", parsed_json=None,
                error="No OpenAI API key available", timestamp=datetime.now().isoformat()
            )
        
        # Truncate prompt to context size if needed
        truncated_prompt = prompt[:context_size * 4]  # Rough char-to-token ratio
        
        payload = {
            "model": model_config['name'],
            "messages": [{"role": "user", "content": truncated_prompt}],
            "temperature": model_config.get('temperature', 0),
            "max_tokens": min(4000, context_size // 2)  # Leave room for input
        }
        
        headers = {
            "Authorization": f"Bearer {auth_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                model_config['api_url'], 
                headers=headers, 
                json=payload, 
                timeout=self.config['global']['timeout']
            )
            response.raise_for_status()
            
            data = response.json()
            response_text = data["choices"][0]["message"]["content"].strip()
            
            # Try to parse JSON
            parsed_json = self._parse_json_response(response_text)
            
            return TestResult(
                model_id=f"{model_config['name']}_{context_size}",
                context_size=context_size,
                prompt_id=0, prompt_name="", success=True,
                response_time=time.time() - start_time,
                response_text=response_text,
                parsed_json=parsed_json,
                error=None,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            return TestResult(
                model_id=f"{model_config['name']}_{context_size}",
                context_size=context_size,
                prompt_id=0, prompt_name="", success=False,
                response_time=time.time() - start_time,
                response_text="", parsed_json=None,
                error=str(e), timestamp=datetime.now().isoformat()
            )
            
    def query_anthropic(self, model_config: Dict[str, Any], prompt: str, context_size: int) -> TestResult:
        start_time = time.time()
        auth_key = self.get_auth_key(self.config['auth']['anthropic'])
        
        if not auth_key:
            return TestResult(
                model_id=f"{model_config['name']}_{context_size}",
                context_size=context_size,
                prompt_id=0, prompt_name="", success=False,
                response_time=0, response_text="", parsed_json=None,
                error="No Anthropic API key available", timestamp=datetime.now().isoformat()
            )
        
        # Truncate prompt to context size if needed
        truncated_prompt = prompt[:context_size * 4]  # Rough char-to-token ratio
        
        payload = {
            "model": model_config['name'],
            "max_tokens": min(4000, context_size // 2),
            "temperature": model_config.get('temperature', 0),
            "messages": [{"role": "user", "content": truncated_prompt}]
        }
        
        headers = {
            "x-api-key": auth_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        try:
            response = requests.post(
                model_config['api_url'],
                headers=headers,
                json=payload,
                timeout=self.config['global']['timeout']
            )
            response.raise_for_status()
            
            data = response.json()
            response_text = data["content"][0]["text"].strip()
            
            # Try to parse JSON
            parsed_json = self._parse_json_response(response_text)
            
            return TestResult(
                model_id=f"{model_config['name']}_{context_size}",
                context_size=context_size,
                prompt_id=0, prompt_name="", success=True,
                response_time=time.time() - start_time,
                response_text=response_text,
                parsed_json=parsed_json,
                error=None,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            return TestResult(
                model_id=f"{model_config['name']}_{context_size}",
                context_size=context_size,
                prompt_id=0, prompt_name="", success=False,
                response_time=time.time() - start_time,
                response_text="", parsed_json=None,
                error=str(e), timestamp=datetime.now().isoformat()
            )
            
    def query_ollama(self, model_config: Dict[str, Any], prompt: str, context_size: int) -> TestResult:
        start_time = time.time()
        
        # Truncate prompt to context size if needed  
        truncated_prompt = prompt[:context_size * 4]  # Rough char-to-token ratio
        
        payload = {
            "model": model_config['name'],
            "prompt": truncated_prompt,
            "stream": False,
            "options": {
                "temperature": model_config.get('temperature', 0),
                "num_ctx": context_size,
                "top_p": 1,
            }
        }
        
        try:
            response = requests.post(
                model_config['api_url'],
                json=payload,
                timeout=self.config['global']['timeout']
            )
            response.raise_for_status()
            
            data = response.json()
            response_text = data.get("response", "").strip()
            
            # Try to parse JSON
            parsed_json = self._parse_json_response(response_text)
            
            return TestResult(
                model_id=f"{model_config['name']}_{context_size}",
                context_size=context_size,
                prompt_id=0, prompt_name="", success=True,
                response_time=time.time() - start_time,
                response_text=response_text,
                parsed_json=parsed_json,
                error=None,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            return TestResult(
                model_id=f"{model_config['name']}_{context_size}",
                context_size=context_size,
                prompt_id=0, prompt_name="", success=False,
                response_time=time.time() - start_time,
                response_text="", parsed_json=None,
                error=str(e), timestamp=datetime.now().isoformat()
            )
            
    def _parse_json_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from model response, handling markdown formatting."""
        if not response_text:
            return None
            
        try:
            # Handle "null" responses
            if response_text.lower().strip() == "null":
                return None
                
            # Clean up markdown formatting
            clean_text = response_text
            if clean_text.startswith('```json'):
                clean_text = clean_text.replace('```json\\n', '').replace('\\n```', '').strip()
            elif clean_text.startswith('```'):
                clean_text = clean_text.replace('```\\n', '').replace('\\n```', '').strip()
                
            return json.loads(clean_text)
            
        except json.JSONDecodeError:
            return {"error": "Invalid JSON", "raw_response": response_text[:200]}
            
    def run_single_test(self, model_config: Dict[str, Any], prompt_data: Dict[str, Any], context_size: int) -> TestResult:
        """Run a single test for one model/prompt/context combination."""
        provider = model_config['provider']
        prompt = prompt_data['prompt']
        
        if provider == 'openai':
            result = self.query_openai(model_config, prompt, context_size)
        elif provider == 'anthropic':
            result = self.query_anthropic(model_config, prompt, context_size)
        elif provider == 'ollama':
            result = self.query_ollama(model_config, prompt, context_size)
        else:
            result = TestResult(
                model_id=f"{model_config['name']}_{context_size}",
                context_size=context_size,
                prompt_id=prompt_data['id'], prompt_name=prompt_data['name'],
                success=False, response_time=0, response_text="",
                parsed_json=None, error=f"Unsupported provider: {provider}",
                timestamp=datetime.now().isoformat()
            )
            
        # Fill in prompt details
        result.prompt_id = prompt_data['id']
        result.prompt_name = prompt_data['name']
        
        return result
        
    def run_all_tests(self):
        print("🔬 Starting Unified LLM Testing Framework")
        print("=" * 60)
        
        # Load test data
        prompts = self.load_prompts()
        enabled_models = {k: v for k, v in self.config['models'].items() if v.get('enabled', False)}
        
        if not enabled_models:
            print("❌ No models enabled in config")
            return
            
        print(f"📋 Loaded {len(prompts)} test prompts")
        print(f"🤖 Testing {len(enabled_models)} enabled models")
        print()
        
        # Check model availability
        available_models = {}
        for model_id, model_config in enabled_models.items():
            if self.check_model_availability(model_config):
                available_models[model_id] = model_config
                print(f"✅ {model_id}: Available")
            else:
                print(f"❌ {model_id}: Not available")
                
        if not available_models:
            print("❌ No models available for testing")
            return
            
        print()
        
        # Generate test configurations
        test_configs = []
        for model_id, model_config in available_models.items():
            for context_size in model_config.get('test_contexts', [4000]):
                for prompt_data in prompts:
                    test_configs.append(TestConfig(
                        model_id=model_id,
                        model_config=model_config,
                        context_size=context_size,
                        prompt_data=prompt_data
                    ))
                    
        total_tests = len(test_configs)
        print(f"🧪 Running {total_tests} total tests...")
        print()
        
        # Run tests
        for i, test_config in enumerate(test_configs, 1):
            print(f"🔄 Test {i}/{total_tests}: {test_config.model_id} (ctx={test_config.context_size}) - {test_config.prompt_data['name']}")
            
            result = self.run_single_test(
                test_config.model_config,
                test_config.prompt_data, 
                test_config.context_size
            )
            
            self.results.append(result)
            
            # Print immediate result
            status = "✅" if result.success else "❌"
            print(f"   {status} {result.response_time:.2f}s - {result.error or 'Success'}")
            
        print()
        print("🎯 Testing Complete!")
        
        # Save results
        self.save_results()
        self.print_summary()
        
    def save_results(self):
        output_dir = Path(self.config['global']['output_dir'])
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save detailed results
        if self.config['reporting']['save_individual_responses']:
            results_file = output_dir / f"unified_test_results_{timestamp}.jsonl"
            with open(results_file, 'w') as f:
                for result in self.results:
                    f.write(json.dumps({
                        'model_id': result.model_id,
                        'context_size': result.context_size,
                        'prompt_id': result.prompt_id,
                        'prompt_name': result.prompt_name,
                        'success': result.success,
                        'response_time': result.response_time,
                        'response_text': result.response_text,
                        'parsed_json': result.parsed_json,
                        'error': result.error,
                        'timestamp': result.timestamp
                    }) + '\\n')
            print(f"📄 Detailed results: {results_file}")
            
        # Save summary stats
        if self.config['reporting']['save_summary_stats']:
            summary = self.generate_summary()
            summary_file = output_dir / f"unified_test_summary_{timestamp}.json"
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            print(f"📊 Summary stats: {summary_file}")
            
    def generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics from test results."""
        summary = {
            'test_config': {
                'total_tests': len(self.results),
                'models_tested': len(set(r.model_id for r in self.results)),
                'prompts_tested': len(set(r.prompt_id for r in self.results)),
                'context_sizes': sorted(set(r.context_size for r in self.results))
            },
            'model_stats': {}
        }
        
        # Per-model statistics
        for model_id in set(r.model_id for r in self.results):
            model_results = [r for r in self.results if r.model_id == model_id]
            
            successful = [r for r in model_results if r.success]
            valid_json = [r for r in successful if r.parsed_json and not r.parsed_json.get('error')]
            
            summary['model_stats'][model_id] = {
                'total_tests': len(model_results),
                'success_rate': len(successful) / len(model_results),
                'avg_response_time': sum(r.response_time for r in successful) / len(successful) if successful else 0,
                'valid_json_rate': len(valid_json) / len(model_results),
                'context_sizes_tested': sorted(set(r.context_size for r in model_results))
            }
            
        return summary
        
    def print_summary(self):
        summary = self.generate_summary()
        
        print("=" * 60)
        print("📊 SUMMARY STATISTICS")
        print("=" * 60)
        print(f"Total Tests: {summary['test_config']['total_tests']}")
        print(f"Models Tested: {summary['test_config']['models_tested']}")  
        print(f"Prompts Tested: {summary['test_config']['prompts_tested']}")
        print(f"Context Sizes: {summary['test_config']['context_sizes']}")
        print()
        
        for model_id, stats in summary['model_stats'].items():
            print(f"🤖 {model_id}:")
            print(f"   Success Rate: {stats['success_rate']:.1%}")
            print(f"   Avg Response Time: {stats['avg_response_time']:.2f}s") 
            print(f"   Valid JSON Rate: {stats['valid_json_rate']:.1%}")
            print(f"   Context Sizes: {stats['context_sizes_tested']}")
            print()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Unified LLM Testing Framework")
    parser.add_argument("--config", default="config.yaml", help="Configuration file path")
    parser.add_argument("--models", nargs='+', help="Specific models to test (overrides config)")
    parser.add_argument("--context-sizes", nargs='+', type=int, help="Specific context sizes to test")
    
    args = parser.parse_args()
    
    # Create and run test runner
    runner = LLMTestRunner(args.config)
    
    # Override config if command line args provided
    if args.models:
        for model_id in runner.config['models']:
            runner.config['models'][model_id]['enabled'] = model_id in args.models
            
    if args.context_sizes:
        for model_config in runner.config['models'].values():
            model_config['test_contexts'] = args.context_sizes
    
    runner.run_all_tests()


if __name__ == "__main__":
    main()