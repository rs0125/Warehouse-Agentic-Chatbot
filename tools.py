# tools.py

import os
import sqlalchemy
from typing import Optional, List
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field

class WarehouseSearchInput(BaseModel):
    cities: Optional[List[str]] = Field(description="A list of cities to search for warehouses in, e.g., ['Bangalore', 'Mysore']")
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


@tool("warehouse-database-search", args_schema=WarehouseSearchInput)
def find_warehouses_in_db(
    cities: Optional[List[str]] = None,
    min_sqft: Optional[int] = None,
    max_sqft: Optional[int] = None,
    warehouse_type: Optional[str] = None,
    min_rate_per_sqft: Optional[int] = None,
    max_rate_per_sqft: Optional[int] = None,
    min_docks: Optional[int] = None,
    min_clear_height: Optional[int] = None,
    compliances: Optional[str] = None,
    availability: Optional[str] = None,
    zone: Optional[str] = None,
    is_broker: Optional[bool] = None,
    page: int = 1
) -> str:
    """
    Searches the database for warehouses using a comprehensive set of filters.
    Supports pagination using the 'page' parameter.
    """
    db_uri = os.environ["DATABASE_URL"]
    engine = sqlalchemy.create_engine(db_uri)
    
    query = 'SELECT id, "warehouseType", city, "offeredSpaceSqft", "ratePerSqft", "numberOfDocks", "clearHeightFt", compliances FROM "Warehouse" WHERE 1=1'
    params = {}

    if cities:
        query += " AND city IN :cities"
        params['cities'] = tuple(cities)
        
    if min_sqft:
        query += ' AND :min_sqft <= ANY("offeredSpaceSqft")'
        params['min_sqft'] = min_sqft
    
    if max_sqft:
        query += ' AND :max_sqft >= ANY("offeredSpaceSqft")'
        params['max_sqft'] = max_sqft
    
    if warehouse_type:
        query += ' AND "warehouseType" ILIKE :warehouse_type'
        params['warehouse_type'] = f"%{warehouse_type}%"

    if min_rate_per_sqft:
        query += " AND \"ratePerSqft\" ~ '^[0-9\.]+$' AND CAST(\"ratePerSqft\" AS INTEGER) >= :min_rate_per_sqft"
        params['min_rate_per_sqft'] = min_rate_per_sqft

    if max_rate_per_sqft:
        query += " AND \"ratePerSqft\" ~ '^[0-9\.]+$' AND CAST(\"ratePerSqft\" AS INTEGER) <= :max_rate_per_sqft"
        params['max_rate_per_sqft'] = max_rate_per_sqft
        
    if min_docks:
        query += " AND \"numberOfDocks\" ~ '^[0-9\.]+$' AND CAST(\"numberOfDocks\" AS INTEGER) >= :min_docks"
        params['min_docks'] = min_docks
        
    if min_clear_height:
        query += " AND \"clearHeightFt\" ~ '^[0-9\.]+$' AND CAST(\"clearHeightFt\" AS INTEGER) >= :min_clear_height"
        params['min_clear_height'] = min_clear_height
        
    if compliances:
        query += ' AND compliances ILIKE :compliances'
        params['compliances'] = f"%{compliances}%"
        
    if availability:
        query += ' AND availability ILIKE :availability'
        params['availability'] = f"%{availability}%"
        
    if zone:
        query += ' AND zone ILIKE :zone'
        params['zone'] = f"%{zone}%"
        
    if is_broker is not None:
        query += ' AND "isBroker" ILIKE :is_broker'
        params['is_broker'] = 'Yes' if is_broker else 'No'

    limit = 5
    offset = (page - 1) * limit
    query += f' ORDER BY id DESC LIMIT {limit} OFFSET {offset};'

    with engine.connect() as connection:
        result = connection.execute(sqlalchemy.text(query), params)
        rows = result.fetchall()

    if not rows:
        if page > 1:
            return "No more warehouses found matching the criteria."
        return "No warehouses found matching those criteria."

    formatted_results = []
    for row in rows:
        row_dict = dict(row._mapping)
        space_values = row_dict['offeredSpaceSqft']
        space_str = ", ".join(map(str, space_values)) if space_values is not None else "Not specified"
        formatted_results.append(
            f"ID: {row_dict['id']}, Type: {row_dict['warehouseType']}, City: {row_dict['city']}, Spaces: {space_str} sqft, Rate: {row_dict['ratePerSqft']}, Docks: {row_dict['numberOfDocks']}"
        )
        
    return "\n".join(formatted_results)