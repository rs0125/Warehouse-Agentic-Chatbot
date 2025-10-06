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
    fire_noc_required: Optional[bool] = Field(description="Set to True to search for warehouses with fire NOC available.")
    land_type_industrial: Optional[bool] = Field(description="Set to True to search for warehouses on industrial land type.")
    page: int = Field(default=1, description="The page number of results to retrieve. Defaults to 1.")


async def _execute_query(engine, params: dict, page_num: int = 1):
    """A helper function to build and execute the full SQL query asynchronously."""
    # Updated query to join with WarehouseData table for fire NOC and land type info
    query = '''SELECT w.id, w."warehouseType", w.city, w.state, w."totalSpaceSqft", w."ratePerSqft", 
                      w."numberOfDocks", w."clearHeightFt", w.compliances,
                      wd."fireNocAvailable", wd."fireSafetyMeasures", wd."landType"
               FROM "Warehouse" w
               LEFT JOIN "WarehouseData" wd ON w.id = wd."warehouseId"
               WHERE 1=1'''
    
    query_params = params.copy()

    if "cities" in query_params:
        query += " AND w.city = ANY(:cities)"
    elif "state" in query_params:
        query += " AND w.state ILIKE :state"
        query_params['state'] = f"%{query_params['state']}%"

    # Handle min and max square footage against an array column
    if "min_sqft" in query_params:
        query += ' AND EXISTS (SELECT 1 FROM unnest(w."totalSpaceSqft") AS s WHERE s >= :min_sqft)'
    if "max_sqft" in query_params:
        query += ' AND EXISTS (SELECT 1 FROM unnest(w."totalSpaceSqft") AS s WHERE s <= :max_sqft)'

    if "warehouse_type" in query_params:
        query += ' AND w."warehouseType" ILIKE :warehouse_type'
        query_params['warehouse_type'] = f"%{query_params['warehouse_type']}%"
    if "min_rate_per_sqft" in query_params:
        # Corrected regex for rate per sqft
        query += " AND w.\"ratePerSqft\" ~ '^[0-9.]+$' AND CAST(w.\"ratePerSqft\" AS INTEGER) >= :min_rate_per_sqft"
    if "max_rate_per_sqft" in query_params:
        # Corrected regex for rate per sqft
        query += " AND w.\"ratePerSqft\" ~ '^[0-9.]+$' AND CAST(w.\"ratePerSqft\" AS INTEGER) <= :max_rate_per_sqft"
    if "min_docks" in query_params:
        query += " AND w.\"numberOfDocks\" ~ '^[0-9.]+$' AND CAST(w.\"numberOfDocks\" AS INTEGER) >= :min_docks"
    if "min_clear_height" in query_params:
        query += " AND w.\"clearHeightFt\" ~ '^[0-9.]+$' AND CAST(w.\"clearHeightFt\" AS INTEGER) >= :min_clear_height"
    if "compliances" in query_params:
        query += ' AND w.compliances ILIKE :compliances'
        query_params['compliances'] = f"%{query_params['compliances']}%"
    if "availability" in query_params:
        query += ' AND w.availability ILIKE :availability'
        query_params['availability'] = f"%{query_params['availability']}%"
    if "zone" in query_params:
        query += ' AND w.zone ILIKE :zone'
        query_params['zone'] = f"%{query_params['zone']}%"
    if "is_broker" in query_params and query_params.get("is_broker") is not None:
        query += ' AND w."isBroker" ILIKE :is_broker'
        query_params['is_broker'] = 'Yes' if query_params['is_broker'] else 'No'
    
    # NEW: Handle fire NOC requirement
    if "fire_noc_required" in query_params and query_params.get("fire_noc_required") is True:
        query += ' AND wd."fireNocAvailable" = :fire_noc_required'
    
    # NEW: Handle industrial land type requirement
    if "land_type_industrial" in query_params and query_params.get("land_type_industrial") is True:
        query += ' AND wd."landType" ILIKE :land_type'
        query_params['land_type'] = '%industrial%'

    limit = 5
    offset = (page_num - 1) * limit
    query += f' ORDER BY w.id DESC LIMIT {limit} OFFSET {offset};'

    async with engine.connect() as connection:
        result = await connection.execute(sqlalchemy.text(query), query_params)
        return result.fetchall()


@tool("warehouse-database-search", args_schema=WarehouseSearchInput)
async def find_warehouses_in_db(**kwargs) -> str:
    """
    Searches for warehouses asynchronously. If no results are found, it automatically relaxes price constraints.
    If too few results are found, it expands the search to include more options.
    
    Uses a fallback approach: try SQLAlchemy async first, then fall back to direct asyncpg if needed.
    """
    import asyncpg
    from urllib.parse import urlparse
    
    db_uri = os.environ["DATABASE_URL"]
    
    # First try the original SQLAlchemy approach
    try:
        if not db_uri.startswith("postgresql+asyncpg"):
            sqlalchemy_uri = db_uri.replace("postgresql://", "postgresql+asyncpg://")
        else:
            sqlalchemy_uri = db_uri

        engine = create_async_engine(sqlalchemy_uri, pool_pre_ping=True)
        
        params = {k: v for k, v in kwargs.items() if v is not None}
        page = params.get("page", 1)
        user_message = ""

        rows = await _execute_query(engine, params, page)
        
        # Handle the rest of the logic...
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
            return "NO_RESULTS_FOUND: No more warehouses found matching the criteria." if page > 1 else "NO_RESULTS_FOUND: No warehouses found matching those criteria."

        formatted_results = []
        for row in rows:
            row_dict = dict(row._mapping)
            space_values = row_dict.get('totalSpaceSqft')
            space_str = ", ".join(map(str, space_values)) if space_values is not None else "Not specified"
            
            # Build basic warehouse info
            result_line = f"ID: {row_dict['id']}, Type: {row_dict['warehouseType']}, City: {row_dict['city']}, State: {row_dict['state']}, Spaces: {space_str} sqft, Rate: {row_dict['ratePerSqft']}, Docks: {row_dict['numberOfDocks']}"
            
            # Add fire NOC information if available
            fire_noc = row_dict.get('fireNocAvailable')
            if fire_noc is not None:
                fire_status = "✅ Fire NOC Available" if fire_noc else "❌ Fire NOC Not Available"
                result_line += f", {fire_status}"
                
                # Add fire safety measures if available
                fire_measures = row_dict.get('fireSafetyMeasures')
                if fire_measures:
                    result_line += f", Fire Safety: {fire_measures}"
            
            # Add land type information if available
            land_type = row_dict.get('landType')
            if land_type:
                result_line += f", Land Type: {land_type}"
            
            formatted_results.append(result_line)
            
        return user_message + "\n".join(formatted_results)
        
    except Exception as e:
        # Fallback to direct asyncpg connection (debug message only, not shown to user)
        debug_mode = os.getenv("DEBUG", "false").lower() == "true"
        if debug_mode:
            print(f"SQLAlchemy failed ({e}), falling back to direct asyncpg...")
        
        try:
            # Parse the connection URL manually
            parsed = urlparse(db_uri)
            
            # Direct asyncpg connection
            conn = await asyncpg.connect(
                user=parsed.username,
                password=parsed.password,
                database=parsed.path[1:],  # Remove leading slash
                host=parsed.hostname,
                port=parsed.port
            )
            
            params = {k: v for k, v in kwargs.items() if v is not None}
            page = params.get("page", 1)
            
            # Build query manually with WarehouseData join
            query = '''SELECT w.id, w."warehouseType", w.city, w.state, w."totalSpaceSqft", w."ratePerSqft", 
                              w."numberOfDocks", w."clearHeightFt", w.compliances,
                              wd."fireNocAvailable", wd."fireSafetyMeasures", wd."landType"
                       FROM "Warehouse" w
                       LEFT JOIN "WarehouseData" wd ON w.id = wd."warehouseId"
                       WHERE 1=1'''
            query_params = []
            param_values = []
            
            if "cities" in params:
                query += " AND w.city = ANY($" + str(len(param_values) + 1) + ")"
                param_values.append(params["cities"])
            
            if "min_sqft" in params:
                query += ' AND EXISTS (SELECT 1 FROM unnest(w."totalSpaceSqft") AS s WHERE s >= $' + str(len(param_values) + 1) + ')'
                param_values.append(params["min_sqft"])
                
            if "max_sqft" in params:
                query += ' AND EXISTS (SELECT 1 FROM unnest(w."totalSpaceSqft") AS s WHERE s <= $' + str(len(param_values) + 1) + ')'
                param_values.append(params["max_sqft"])
            
            # Handle fire NOC requirement
            if "fire_noc_required" in params and params.get("fire_noc_required") is True:
                query += ' AND wd."fireNocAvailable" = $' + str(len(param_values) + 1)
                param_values.append(True)
            
            # Handle industrial land type requirement
            if "land_type_industrial" in params and params.get("land_type_industrial") is True:
                query += ' AND wd."landType" ILIKE $' + str(len(param_values) + 1)
                param_values.append('%industrial%')

            limit = 5
            offset = (page - 1) * limit
            query += f' ORDER BY w.id DESC LIMIT {limit} OFFSET {offset};'
            
            rows = await conn.fetch(query, *param_values)
            await conn.close()
            
            if not rows:
                return "NO_RESULTS_FOUND: No warehouses found matching those criteria."
            
            formatted_results = []
            for row in rows:
                space_values = row['totalSpaceSqft']
                space_str = ", ".join(map(str, space_values)) if space_values is not None else "Not specified"
                
                # Build basic warehouse info
                result_line = f"ID: {row['id']}, Type: {row['warehouseType']}, City: {row['city']}, State: {row['state']}, Spaces: {space_str} sqft, Rate: {row['ratePerSqft']}, Docks: {row['numberOfDocks']}"
                
                # Add fire NOC information if available
                fire_noc = row.get('fireNocAvailable')
                if fire_noc is not None:
                    fire_status = "✅ Fire NOC Available" if fire_noc else "❌ Fire NOC Not Available"
                    result_line += f", {fire_status}"
                    
                    # Add fire safety measures if available
                    fire_measures = row.get('fireSafetyMeasures')
                    if fire_measures:
                        result_line += f", Fire Safety: {fire_measures}"
                
                # Add land type information if available
                land_type = row.get('landType')
                if land_type:
                    result_line += f", Land Type: {land_type}"
                
                formatted_results.append(result_line)
                
            return "\n".join(formatted_results)
            
        except Exception as fallback_error:
            return f"Database connection failed: {fallback_error}"