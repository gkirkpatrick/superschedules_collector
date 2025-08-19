#!/usr/bin/env python3
"""
Parse clean_prompts.txt into structured JSON format for testing
"""

import json
import re
import sys

def parse_clean_prompts(file_path: str) -> list:
    """Parse the clean_prompts.txt file into structured prompts."""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Split by prompt separators
    prompt_blocks = re.split(r'=== PROMPT \d+ ===', content)[1:]  # Skip first empty part
    
    prompts = []
    
    for i, block in enumerate(prompt_blocks, 1):
        # Clean up the block
        block = block.strip()
        
        # Remove the separator line and trailing info
        block = re.sub(r'2025-\d{2}-\d{2}.*?INFO -\s*$', '', block, flags=re.MULTILINE | re.DOTALL)
        block = re.sub(r'={40,}.*$', '', block, flags=re.MULTILINE | re.DOTALL)
        block = block.strip()
        
        if not block or len(block) < 100:  # Skip very short/empty prompts
            continue
            
        # Extract event name from Content line
        content_match = re.search(r'Content: [\d:]+-?[\d:]*\s*\n?([^\n]+)', block)
        if content_match:
            event_name = content_match.group(1).strip()
            # Clean up common patterns
            event_name = re.sub(r'\s*,\s*$', '', event_name)  # Remove trailing commas
        else:
            event_name = f"Event {i}"
        
        prompts.append({
            "id": i,
            "name": event_name,
            "prompt": block
        })
    
    return prompts

def main():
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "clean_prompts.txt"
    
    try:
        prompts = parse_clean_prompts(input_file)
        
        output_file = "parsed_prompts.json"
        with open(output_file, 'w') as f:
            json.dump(prompts, f, indent=2)
        
        print(f"✅ Parsed {len(prompts)} prompts from {input_file}")
        print(f"📄 Saved to {output_file}")
        
        # Show first few prompt names
        print("\n📋 Sample prompts:")
        for prompt in prompts[:5]:
            print(f"  {prompt['id']:2d}. {prompt['name']}")
        if len(prompts) > 5:
            print(f"     ... and {len(prompts) - 5} more")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())