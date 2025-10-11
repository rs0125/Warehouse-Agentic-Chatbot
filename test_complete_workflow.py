#!/usr/bin/env python3
"""
Complete integration test for dynamic area search workflow.
Tests the full pipeline from user input to database search with area detection.
"""

import asyncio
import os
from state import GraphState
from nodes import update_state_node, search_database_node

async def test_complete_area_workflow():
    """Test the complete area search workflow from input to search"""
    
    print("🔄 Testing Complete Dynamic Area Search Pipeline")
    print("=" * 60)
    
    # Test case with area-specific query
    test_query = "I need a 10000 sqft warehouse in Whitefield, Bangalore with industrial land type"
    
    print(f"🧪 Testing: '{test_query}'")
    print("-" * 60)
    
    # Step 1: Initialize state and process area/size input
    state = GraphState()
    state.add_message("user", test_query)
    
    print("📝 Step 1: Processing area and size requirements...")
    result_state = await update_state_node(state)
    
    print(f"   ✓ Location Query: {result_state.location_query}")
    print(f"   ✓ Size Range: {result_state.size_min} - {result_state.size_max} sqft")
    print(f"   ✓ Workflow Stage: {result_state.workflow_stage}")
    
    # Step 2: Process business nature (if needed)
    if result_state.workflow_stage == "land_type_preference":
        print("\n📝 Step 2: Processing industrial land type preference...")
        state.add_message("user", "industrial") 
        result_state = await update_state_node(state)
        print(f"   ✓ Land Type Industrial: {result_state.land_type_industrial}")
        print(f"   ✓ Workflow Stage: {result_state.workflow_stage}")
    
    # Step 3: Move to specifics stage if needed
    if result_state.workflow_stage == "specifics":
        print("\n📝 Step 3: In specifics stage, proceeding to search...")
        # Set ready for search
        result_state.requirements_confirmed = True
        result_state.next_action = "search_database"
    
    # Step 4: Test the search phase with location analysis
    if result_state.next_action == "search_database":
        print("\n🔍 Step 4: Testing search with dynamic area detection...")
        try:
            # This should trigger the location analysis tool
            search_result_state = await search_database_node(result_state)
            
            print(f"📍 Location Analysis Results:")
            print(f"   ✓ Original Query: {search_result_state.location_query}")
            print(f"   ✓ Parsed Cities: {search_result_state.parsed_cities}")
            print(f"   ✓ Search Area: {search_result_state.search_area}")
            print(f"   ✓ Search City: {search_result_state.search_city}")
            print(f"   ✓ Is Area Search: {search_result_state.is_area_search}")
            
            print(f"\n🎯 Final Search Parameters:")
            print(f"   - Location: {search_result_state.search_area or search_result_state.parsed_cities}")
            print(f"   - Size: {search_result_state.size_min}-{search_result_state.size_max}")
            print(f"   - Land Type: {'Industrial' if search_result_state.land_type_industrial else 'Commercial'}")
            
            # Validate area detection for "Whitefield, Bangalore"
            if "Whitefield" in str(search_result_state.search_area):
                print(f"   ✅ Successfully detected area: Whitefield")
            else:
                print(f"   ❌ Failed to detect area from 'Whitefield, Bangalore'")
                
            if "Bangalore" in str(search_result_state.search_city or search_result_state.parsed_cities):
                print(f"   ✅ Successfully detected city: Bangalore")
            else:
                print(f"   ❌ Failed to detect city from 'Whitefield, Bangalore'")
                
            if search_result_state.is_area_search:
                print(f"   ✅ Correctly identified as area search")
            else:
                print(f"   ❌ Failed to identify as area search")
            
            # Check search results
            if search_result_state.search_results:
                print(f"\n📊 Search Results: Found warehouses")
            else:
                print(f"\n📊 Search Results: No results or search failed")
                
        except Exception as e:
            print(f"❌ Error in search phase: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("🏁 Complete Pipeline Test Finished")

if __name__ == "__main__":
    asyncio.run(test_complete_area_workflow())