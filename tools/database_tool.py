# tools.py

import os
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine
from typing import Optional, List
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field

class WarehouseSearchInput(BaseModel):
    cities: Optional[List[str]] = Field(description="A list of cities to search for warehouses in, e.g., ['Bangalore', 'Mysore']")
    state: Optional[str] = Field(description="A single state to search for warehouses in, e.g., 'Karnataka'.")
    min_sqft: Optional[int] = Field(description="The minimum square footage required.")
    max_sqft: Optional[int] = Field(description="The maximum square footage available.")
    warehouse_type: Optional[str] = Field(description="The type of warehouse, e.g., 'PEB', 'RCC'.")
    min_rate_per_sqft: Optional[int] = Field(description="The minimum rate per square foot.")
    max_rate_per_sqft: Optional[int] = Field(description="The maximum rate per square foot (e.g., 18).")
    min_docks: Optional[int] = Field(description="The minimum number of loading docks available.")
    min_clear_height: Optional[int] = Field(description="The minimum clear height in feet.")
    compliances: Optional[str] = Field(description="Specific compliances to search for, e.g., 'fire', 'environmental'.")
    availability: Optional[str] = Field(description="Availability status to search for, e.g., 'immediate'.")
    zone: Optional[str] = Field(description="The zone to search within, e.g., 'Industrial Zone'.")
    is_broker: Optional[bool] = Field(description="Set to True for properties listed by a broker, False for properties listed by owners.")
    page: int = Field(default=1, description="The page number of results to retrieve. Defaults to 1.")


async def _execute_query(engine, params: dict, page_num: int = 1):
    """A helper function to build and execute the full SQL query asynchronously."""
    query = 'SELECT id, "warehouseType", city, state, "totalSpaceSqft", "ratePerSqft", "numberOfDocks", "clearHeightFt", compliances FROM "Warehouse" WHERE 1=1'
    
    query_params = params.copy()

    if "cities" in query_params:
        query += " AND city = ANY(:cities)"
    elif "state" in query_params:
        query += " AND state ILIKE :state"
        query_params['state'] = f"%{query_params['state']}%"

    # --- START OF FIX ---
    # Correctly handle min and max square footage against an array column
    if "min_sqft" in query_params:
        query += ' AND EXISTS (SELECT 1 FROM unnest("totalSpaceSqft") AS s WHERE s >= :min_sqft)'
    if "max_sqft" in query_params:
        query += ' AND EXISTS (SELECT 1 FROM unnest("totalSpaceSqft") AS s WHERE s <= :max_sqft)'
    # --- END OF FIX ---

    if "warehouse_type" in query_params:
        query += ' AND "warehouseType" ILIKE :warehouse_type'
        query_params['warehouse_type'] = f"%{query_params['warehouse_type']}%"
    if "min_rate_per_sqft" in query_params:
        # Corrected regex for rate per sqft
        query += " AND \"ratePerSqft\" ~ '^[0-9.]+$' AND CAST(\"ratePerSqft\" AS INTEGER) >= :min_rate_per_sqft"
    if "max_rate_per_sqft" in query_params:
        # Corrected regex for rate per sqft
        query += " AND \"ratePerSqft\" ~ '^[0-9.]+$' AND CAST(\"ratePerSqft\" AS INTEGER) <= :max_rate_per_sqft"
    if "min_docks" in query_params:
        query += " AND \"numberOfDocks\" ~ '^[0-9.]+$' AND CAST(\"numberOfDocks\" AS INTEGER) >= :min_docks"
    if "min_clear_height" in query_params:
        query += " AND \"clearHeightFt\" ~ '^[0-9.]+$' AND CAST(\"clearHeightFt\" AS INTEGER) >= :min_clear_height"
    if "compliances" in query_params:
        query += ' AND compliances ILIKE :compliances'
        query_params['compliances'] = f"%{query_params['compliances']}%"
    if "availability" in query_params:
        query += ' AND availability ILIKE :availability'
        query_params['availability'] = f"%{query_params['availability']}%"
    if "zone" in query_params:
        query += ' AND zone ILIKE :zone'
        query_params['zone'] = f"%{query_params['zone']}%"
    if "is_broker" in query_params and query_params.get("is_broker") is not None:
        query += ' AND "isBroker" ILIKE :is_broker'
        query_params['is_broker'] = 'Yes' if query_params['is_broker'] else 'No'

    limit = 5
    offset = (page_num - 1) * limit
    query += f' ORDER BY id DESC LIMIT {limit} OFFSET {offset};'

    async with engine.connect() as connection:
        result = await connection.execute(sqlalchemy.text(query), query_params)
        return result.fetchall()


@tool("warehouse-database-search", args_schema=WarehouseSearchInput)
async def find_warehouses_in_db(**kwargs) -> str:
    """
    Searches for warehouses asynchronously. If no results are found, it automatically relaxes price constraints.
    If too few results are found, it expands the search to include more options.
    """
    db_uri = os.environ["DATABASE_URL"]
    if not db_uri.startswith("postgresql+asyncpg"):
        db_uri = db_uri.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(db_uri)
    
    params = {k: v for k, v in kwargs.items() if v is not None}
    page = params.get("page", 1)
    user_message = ""

    rows = await _execute_query(engine, params, page)

    if page == 1:
        if not rows and "max_rate_per_sqft" in params:
            original_rate = params["max_rate_per_sqft"]
            fallback_params = params.copy()
            fallback_params["max_rate_per_sqft"] = int(original_rate * 1.15)
            
            rows = await _execute_query(engine, fallback_params, page)
            if rows:
                user_message = f"I couldn't find anything at your exact price of ₹{original_rate}/sqft, but found these with a rate up to ₹{fallback_params['max_rate_per_sqft']}/sqft:\n\n"

        elif 0 < len(rows) < 5 and "max_rate_per_sqft" in params:
            original_rate = params["max_rate_per_sqft"]
            
            expansion_params = params.copy()
            expansion_params["max_rate_per_sqft"] = int(original_rate * 1.15)
            # Ensure we only find *new* warehouses in the higher price bracket
            if "min_rate_per_sqft" not in expansion_params or expansion_params["min_rate_per_sqft"] <= original_rate:
                 expansion_params["min_rate_per_sqft"] = original_rate + 1
            
            expansion_rows = await _execute_query(engine, expansion_params, 1)
            
            if expansion_rows:
                user_message = "To give you more options, I've also included some warehouses with slightly higher rates:\n\n"
                existing_ids = {row.id for row in rows}
                for row in expansion_rows:
                    if row.id not in existing_ids and len(rows) < 5:
                        rows.append(row)

    if not rows:
        return "No more warehouses found matching the criteria." if page > 1 else "No warehouses found matching those criteria."

    formatted_results = []
    for row in rows:
        row_dict = dict(row._mapping)
        space_values = row_dict.get('totalSpaceSqft')
        space_str = ", ".join(map(str, space_values)) if space_values is not None else "Not specified"
        formatted_results.append(
            f"ID: {row_dict['id']}, Type: {row_dict['warehouseType']}, City: {row_dict['city']}, State: {row_dict['state']}, Spaces: {space_str} sqft, Rate: {row_dict['ratePerSqft']}, Docks: {row_dict['numberOfDocks']}"
        )
        
    return user_message + "\n".join(formatted_results)