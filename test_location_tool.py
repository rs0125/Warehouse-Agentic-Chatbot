#!/usr/bin/env python3

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from tools.location_tool import analyze_location_query

async def test_location_tool():
    """Test the location tool with different inputs"""
    test_inputs = ["bangalore", "blr", "Bangalore", "BLR"]
    
    for location in test_inputs:
        try:
            print(f"\n--- Testing: '{location}' ---")
            result = await analyze_location_query.ainvoke({"location_query": location})
            print(f"Result: {result}")
            print(f"Type: {type(result)}")
            
            if isinstance(result, dict):
                print(f"Cities: {result.get('cities')}")
                print(f"State: {result.get('state')}")
            
        except Exception as e:
            print(f"Error with '{location}': {e}")

if __name__ == "__main__":
    asyncio.run(test_location_tool())