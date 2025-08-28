"""LLM-based event validation and tagging module."""

import json
from typing import Dict, List, Optional
from openai import OpenAI
import os


def get_openai_client() -> OpenAI:
    """Get OpenAI client with API key from environment or secret file."""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        try:
            with open(os.path.expanduser("~/.secret_keys"), "r") as f:
                for line in f:
                    if line.startswith("OPENAI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
        except FileNotFoundError:
            pass
    
    if not api_key:
        raise ValueError("OpenAI API key not found in environment or ~/.secret_keys")
    
    return OpenAI(api_key=api_key)


def validate_and_enhance_events(events: List[Dict]) -> List[Dict]:
    """
    Validate events and add LLM-generated tags based on descriptions.
    
    Args:
        events: List of event dictionaries
        
    Returns:
        List of enhanced events with validation scores and tags
    """
    if not events:
        return events
    
    client = get_openai_client()
    enhanced_events = []
    
    for event in events:
        try:
            enhanced_event = _validate_single_event(client, event)
            enhanced_events.append(enhanced_event)
        except Exception as e:
            print(f"Failed to validate event {event.get('title', 'Unknown')}: {e}")
            # Return original event with minimal validation info
            event['validation_score'] = 0.5  # Neutral score for failed validation
            event['tags'] = []
            enhanced_events.append(event)
    
    return enhanced_events


def _validate_single_event(client: OpenAI, event: Dict) -> Dict:
    """Validate a single event and generate tags."""
    
    validation_prompt = f"""
Analyze this event and provide:
1. A validation score (0.0-1.0) indicating how complete/accurate the event data appears
2. Relevant tags based on the title and description that would help users find this event

Event data:
Title: {event.get('title', 'N/A')}
Description: {event.get('description', 'N/A')}
Location: {event.get('location', 'N/A')}
Date/Time: {event.get('start_time', 'N/A')}

Consider these aspects for validation score:
- Are required fields (title, date) present and meaningful?
- Does the description provide useful information?
- Is the location specific enough?
- Does the date/time make sense?

For tags, consider:
- Age groups (kids, teens, adults, families, seniors)
- Activity types (workshop, performance, meeting, festival, educational, sports, art)
- Topics/interests (science, history, music, fitness, food, technology)
- Accessibility (free, paid, indoor, outdoor, beginner-friendly)

Return JSON only:
{{
    "validation_score": 0.85,
    "tags": ["families", "educational", "science", "kids", "indoor", "free"]
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": validation_prompt}],
            temperature=0.1,
            max_tokens=200
        )
        
        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)
        
        # Add validation results to event
        event['validation_score'] = result.get('validation_score', 0.5)
        event['tags'] = result.get('tags', [])
        
        return event
        
    except Exception as e:
        print(f"LLM validation failed for event: {e}")
        event['validation_score'] = 0.5
        event['tags'] = []
        return event