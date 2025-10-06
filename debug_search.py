#!/usr/bin/env python3

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from tools.database_tool import find_warehouses_in_db

async def test_search_params():
    """Test the exact search parameters that should find warehouse 408"""
    
    print("🔍 Testing search parameters that should find warehouse ID 408...")
    
    # Test the exact parameters from the working search
    search_params = {
        'cities': ['Bangalore'], 
        'min_sqft': 40000, 
        'max_sqft': 60000, 
        'page': 1, 
        'land_type_industrial': True
    }
    
    print(f"📋 Search params: {search_params}")
    
    try:
        result = await find_warehouses_in_db.ainvoke(search_params)
        print(f"✅ Search result:")
        print(result)
        
        # Check if warehouse 408 is in the results
        if "408" in str(result):
            print("✅ Warehouse 408 found in results!")
        else:
            print("❌ Warehouse 408 NOT found in results!")
            
        # Count total results
        result_count = str(result).count("ID:")
        print(f"📊 Total results found: {result_count}")
        
    except Exception as e:
        print(f"❌ Search failed: {e}")
        import traceback
        traceback.print_exc()

    # Also test without land type restriction
    print("\n🔍 Testing without land type restriction...")
    search_params_no_land = {
        'cities': ['Bangalore'], 
        'min_sqft': 40000, 
        'max_sqft': 60000, 
        'page': 1
    }
    
    try:
        result2 = await find_warehouses_in_db.ainvoke(search_params_no_land)
        print(f"✅ Search result (no land type):")
        print(result2)
        
        if "408" in str(result2):
            print("✅ Warehouse 408 found when land type not specified!")
        else:
            print("❌ Warehouse 408 still not found!")
            
    except Exception as e:
        print(f"❌ Search failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_search_params())