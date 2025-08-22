# LLM Testing & Comparison Tools

This directory contains tools for testing and comparing different LLM models for event extraction from web pages.

## Overview

These tools were developed to evaluate local Ollama models as alternatives to OpenAI for the event scraping pipeline. The testing showed that **Gemma2:7b achieves 100% accuracy while being 29% faster than OpenAI**.

## ⭐ New Unified Testing Framework

### Main Tool: `test_runner.py`

**One script to rule them all!** The new unified framework supports:

- **Multi-provider testing**: OpenAI, Anthropic, Ollama
- **Configurable authentication**: API keys, files, or no auth for local models  
- **Context size testing**: Test different context windows
- **Flexible configuration**: All settings in `config.yaml`
- **Comprehensive reporting**: Detailed logs and summary statistics

### Quick Start

```bash
# Test with default config (Gemma2:7b vs OpenAI)
python test_runner.py

# Test specific models only
python test_runner.py --models openai_gpt4o_mini ollama_gemma2_7b

# Test specific context sizes
python test_runner.py --context-sizes 4000 16000 32000

# Use custom config
python test_runner.py --config my_config.yaml
```

### Configuration

Edit `config.yaml` to:
- Enable/disable models to test
- Set API keys and authentication  
- Configure context sizes to test
- Adjust timeout and retry settings
- Control output and reporting

## Legacy Testing Scripts

### Data Processing Tools

- **`parse_prompts.py`** - Converts clean_prompts.txt to structured JSON
  - Creates parsed_prompts.json with 30 test cases
  - Input for testing frameworks

- **`test_prompts.py`** - Captures prompts from live scraper runs
  - Logs LLM interactions for testing with local models
  - Creates prompt_logs.txt

### Setup & Configuration

- **`ollama_setup.py`** - Ollama model management
  - Pull and manage local models
  - Check model availability

## Test Data

### Input Data
- **`clean_prompts.txt`** - 30 real prompts from Boston.gov scraping
- **`parsed_prompts.json`** - Structured version of prompts for testing
- **`prompt_logs.txt`** - Raw logs from live scraper runs

### Results Data
- **`llm_test_results_20250819_103151.jsonl`** - **FINAL RESULTS** (Gemma2:7b vs OpenAI)
- **`llm_test_results_20250819_103151_summary.json`** - **FINAL SUMMARY** (100% accuracy, 29% faster)
- **`llm_test_results_20250819_100858.jsonl`** - Previous results (Gemma3:12b vs OpenAI)
- Other result files from earlier testing iterations

## Key Findings

### Model Performance Summary
1. **DeepSeek-LLM:7b**: Too slow, frequent timeouts
2. **Gemma3:12b**: 96.7% accuracy, 34% slower than OpenAI  
3. **Gemma2:7b**: **100% accuracy, 29% faster than OpenAI** ✅

### Final Recommendation
**Use Gemma2:7b (gemma2:latest)** for production event scraping:
- Perfect JSON compliance and functional equivalence with OpenAI
- Significantly faster response times (2.88s vs 4.03s average)
- No API costs, runs locally on RTX 5070
- 100% success rate across all test scenarios

## Usage Examples

### New Unified Framework
```bash
# Run all enabled tests from config
python test_runner.py

# Test only specific models 
python test_runner.py --models openai_gpt4o_mini anthropic_sonnet

# Test different context sizes
python test_runner.py --context-sizes 2000 8000 16000
```

### Legacy Scripts
```bash
# Convert prompts for testing
python parse_prompts.py
```

## Configuration Notes

### For `test_runner.py` (Unified Framework):
- Configure authentication in `config.yaml` 
- OpenAI: API key in `~/.secret_keys` or `OPENAI_API_KEY` env var
- Anthropic: API key in `~/.anthropic_key` or `ANTHROPIC_API_KEY` env var  
- Ollama: Local server on `localhost:11434` (no auth needed)

### For Legacy Scripts:
- OpenAI API key in `~/.secret_keys` or `OPENAI_API_KEY` environment variable
- Ollama server running on `localhost:11434`
- Target model pulled locally (e.g., `ollama pull gemma2:latest`)

## Schema Validation

The testing validates against the correct API schema:
```json
{
  "source_id": int|null,
  "external_id": "string",
  "title": "string", 
  "description": "string",
  "location": "string",
  "start_time": "ISO datetime",
  "end_time": "ISO datetime|null",
  "url": "string|null"
}
```

The `metadata_tags` field in test prompts is ignored by the API (harmless extra field).