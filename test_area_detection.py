#!/usr/bin/env python3
"""
Test script for dynamic area detection functionality.
Tests the enhanced location tool without hardcoded location lists.
"""

import asyncio
import os
from tools.location_tool import analyze_location_query

async def test_area_detection():
    """Test various location query formats"""
    
    # Set up environment (assuming you have OpenAI API key)
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY not found in environment variables")
        return
    
    test_cases = [
        # Area, City format
        "Whitefield, Bangalore",
        "Electronic City, Bangalore", 
        "Gurgaon, Delhi",
        "Andheri, Mumbai",
        
        # Area indicators
        "Whitefield area",
        "Electronic City industrial zone",
        "Sector 18 Noida",
        "Cyber City Gurgaon",
        
        # Standard city searches
        "Bangalore",
        "Chennai", 
        "Delhi",
        
        # State searches
        "Karnataka",
        "Tamil Nadu",
        
        # Complex area queries
        "Industrial area near Whitefield",
        "Tech parks in Bangalore",
        "Warehouses in Electronic City Phase 1"
    ]
    
    print("🧪 Testing Dynamic Area Detection System")
    print("=" * 50)
    
    for i, query in enumerate(test_cases, 1):
        print(f"\n{i}. Testing: '{query}'")
        print("-" * 30)
        
        try:
            result = await analyze_location_query.ainvoke({"location_query": query})
            
            print(f"📍 Location Analysis Results:")
            print(f"   Cities: {result.get('cities')}")
            print(f"   State: {result.get('state')}")
            print(f"   Areas: {result.get('areas')}")
            print(f"   Search Area: {result.get('search_area')}")
            print(f"   Search City: {result.get('search_city')}")
            print(f"   Is Area Search: {result.get('is_area_search')}")
            
            # Validate the detection logic
            if "," in query:
                expected_area_search = True
                print(f"✅ Expected area search: {expected_area_search}, Got: {result.get('is_area_search')}")
            
        except Exception as e:
            print(f"❌ Error testing '{query}': {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Dynamic Area Detection Test Complete")

if __name__ == "__main__":
    asyncio.run(test_area_detection())