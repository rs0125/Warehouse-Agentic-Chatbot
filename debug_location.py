#!/usr/bin/env python3

import asyncio
from tools.location_tool import analyze_location_query

async def test_location_parsing():
    """Test location parsing for 'blr'"""
    try:
        result = await analyze_location_query.ainvoke({"location_query": "blr"})
        print(f"Location analysis result for 'blr': {result}")
        print(f"Type: {type(result)}")
        
        if isinstance(result, dict):
            print(f"Cities: {result.get('cities')}")
            print(f"State: {result.get('state')}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_location_parsing())