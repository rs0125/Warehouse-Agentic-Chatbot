#!/usr/bin/env python3
"""
Test script for complete dynamic area search workflow.
Tests the integration of enhanced location tool with the database search.
"""

import asyncio
import os
from state import GraphState
from nodes import update_state_node

async def test_area_search_workflow():
    """Test the complete area search workflow"""
    
    print("🧪 Testing Complete Area Search Workflow")
    print("=" * 50)
    
    # Test case: Area, City format
    test_cases = [
        {
            "query": "I need a 10000 sqft warehouse in Whitefield, Bangalore",
            "expected_area": "Whitefield",
            "expected_city": "Bangalore"
        },
        {
            "query": "Looking for warehouses in Electronic City industrial area, need around 5000 sqft",
            "expected_area": "Electronic City",
            "expected_indicators": "industrial"
        },
        {
            "query": "Need warehouse space in Bangalore around 8000 sqft",
            "expected_city": "Bangalore",
            "expected_area_search": False
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. Testing: '{test_case['query']}'")
        print("-" * 40)
        
        # Create state and simulate user input
        state = GraphState()
        state.add_message("user", test_case["query"])
        
        try:
            # Run the state update node which parses user input
            result_state = await update_state_node(state)
            
            print(f"📍 Results:")
            print(f"   Location Query: {result_state.location_query}")
            print(f"   Parsed Cities: {result_state.parsed_cities}")
            print(f"   Search Area: {result_state.search_area}")
            print(f"   Search City: {result_state.search_city}")
            print(f"   Is Area Search: {result_state.is_area_search}")
            print(f"   Size Min: {result_state.size_min}")
            print(f"   Size Max: {result_state.size_max}")
            print(f"   Workflow Stage: {result_state.workflow_stage}")
            
            # Validate expectations
            if "expected_area" in test_case:
                expected = test_case["expected_area"]
                actual = result_state.search_area
                status = "✅" if expected in str(actual) else "❌"
                print(f"   {status} Expected area '{expected}' in result: {actual}")
            
            if "expected_city" in test_case:
                expected = test_case["expected_city"]
                actual = result_state.search_city or result_state.parsed_cities
                status = "✅" if expected in str(actual) else "❌"
                print(f"   {status} Expected city '{expected}' in result: {actual}")
                
            if "expected_area_search" in test_case:
                expected = test_case["expected_area_search"]
                actual = result_state.is_area_search
                status = "✅" if expected == actual else "❌"
                print(f"   {status} Expected area search: {expected}, Got: {actual}")
            
        except Exception as e:
            print(f"❌ Error testing workflow: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("🎯 Complete Workflow Test Complete")

if __name__ == "__main__":
    asyncio.run(test_area_search_workflow())