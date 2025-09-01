"""
Test the enhanced collector with Schema.org support.
"""
import json
from scrapers.jsonld_scraper import _parse_location, _extract_organizer, _extract_event_objects

def test_schema_org_place_preservation():
    """Test that Schema.org Place objects are preserved."""
    
    # Mock Schema.org Place data (like from Needham Library)
    place_data = {
        "@type": "Place",
        "name": "Inside, Children's Room",
        "address": "Needham Free Public Library, 1139 Highland Avenue, Needham, MA, 02494",
        "telephone": "781-455-7559",
        "url": "www.needhamma.gov>library"
    }
    
    # Test _parse_location preserves the full object
    result = _parse_location(place_data)
    
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result.get("@type") == "Place", f"Expected Place type, got {result.get('@type')}"
    assert result.get("name") == "Inside, Children's Room"
    assert "Needham" in result.get("address", ""), "Full address with Needham should be preserved"
    assert result.get("telephone") == "781-455-7559"
    
    print("✅ Schema.org Place preservation test passed")

def test_organizer_extraction():
    """Test organizer extraction from various formats."""
    
    # String organizer
    assert _extract_organizer("Needham Public Library") == "Needham Public Library"
    
    # Dict organizer (Schema.org Organization)
    org_data = {"@type": "Organization", "name": "Needham Public Library"}
    assert _extract_organizer(org_data) == "Needham Public Library"
    
    # Empty/None
    assert _extract_organizer(None) == ""
    assert _extract_organizer("") == ""
    
    print("✅ Organizer extraction test passed")

def test_backward_compatibility():
    """Test that simple string locations still work."""
    
    # Simple string
    result = _parse_location("Town Hall")
    assert result == "Town Hall", f"Expected 'Town Hall', got {result}"
    
    # Simple dict without @type
    simple_dict = {"name": "Community Center", "address": "123 Main St"}
    result = _parse_location(simple_dict)
    assert result == "Community Center", f"Expected 'Community Center', got {result}"
    
    print("✅ Backward compatibility test passed")

def test_location_array_handling():
    """Test that location arrays work correctly."""
    
    # Array with Schema.org Place
    place_array = [{
        "@type": "Place",
        "name": "Library Community Room", 
        "address": "Needham Free Public Library, 1139 Highland Avenue, Needham, MA, 02494"
    }]
    
    result = _parse_location(place_array)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result.get("@type") == "Place"
    assert "Needham" in result.get("address", "")
    
    print("✅ Location array handling test passed")

if __name__ == "__main__":
    test_schema_org_place_preservation()
    test_organizer_extraction()
    test_backward_compatibility()
    test_location_array_handling()
    print("\n🎉 All collector Schema.org tests passed!")