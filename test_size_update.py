#!/usr/bin/env python3
"""
Quick test for size parsing functionality
"""

import asyncio
import os
from state import GraphState
from nodes import update_state_node

async def test_size_update():
    """Test size update functionality"""
    
    print("🧪 Testing Size Update: 'change size to 10k'")
    print("=" * 50)
    
    # Initialize state in specifics stage (where size updates should work)
    state = GraphState()
    state.workflow_stage = "specifics"
    state.location_query = "Whitefield, Bangalore"
    state.size_min = 24000
    state.size_max = 36000
    state.land_type_industrial = False
    
    print(f"Initial state:")
    print(f"  Size: {state.size_min} - {state.size_max} sqft")
    print(f"  Stage: {state.workflow_stage}")
    
    # Add the user message for size change
    state.add_message("user", "change size to 10k")
    
    # Process the update
    result_state = await update_state_node(state)
    
    print(f"\nAfter processing 'change size to 10k':")
    print(f"  Size: {result_state.size_min} - {result_state.size_max} sqft")
    print(f"  Next action: {result_state.next_action}")
    
    # Check if it worked
    if result_state.size_min and result_state.size_max:
        expected_center = 10000
        actual_center = (result_state.size_min + result_state.size_max) / 2
        if abs(actual_center - expected_center) < 1000:  # Within 1000 sqft of 10k
            print("✅ Size update worked correctly!")
        else:
            print(f"❌ Size update didn't work as expected. Center: {actual_center}")
    else:
        print("❌ Size values not set after update")

if __name__ == "__main__":
    asyncio.run(test_size_update())