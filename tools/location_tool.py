    # location_tools.py

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.json import JsonOutputParser
from pydantic.v1 import BaseModel, Field
from typing import List, Optional
import re

# Enhanced output model for dynamic area detection
class LocationAnalysis(BaseModel):
    cities: Optional[List[str]] = Field(None, description="A list of canonical city names and aliases, used for city or sub-region queries.")
    state: Optional[str] = Field(None, description="A single canonical state name, used only when the user's query is a state.")
    areas: Optional[List[str]] = Field(None, description="A list of specific areas or localities extracted from the query.")
    search_area: Optional[str] = Field(None, description="The primary area name for search purposes.")
    search_city: Optional[str] = Field(None, description="The primary city name for search purposes.")
    is_area_search: Optional[bool] = Field(False, description="Whether this is a specific area-based search.")

class AreaDetector:
    """Dynamic area detection without hardcoded location lists"""
    
    def __init__(self):
        # Pattern for "Area, City" format
        self.area_city_pattern = re.compile(r'^([^,]+),\s*([^,]+)$', re.IGNORECASE)
        # Pattern for common area indicators
        self.area_indicators = [
            r'\b(area|locality|sector|zone|district|region|neighborhood|neighbourhood)\b',
            r'\b(road|street|avenue|lane|circle|cross|main)\b',
            r'\b(industrial|commercial|tech|it|business)\s+(park|area|zone|hub|corridor)\b',
            r'\b(old|new|north|south|east|west|central)\s+\w+\b'
        ]
    
    def extract_area_city(self, query: str) -> tuple:
        """Extract area and city from queries like 'Whitefield, Bangalore'"""
        match = self.area_city_pattern.match(query.strip())
        if match:
            area = match.group(1).strip()
            city = match.group(2).strip()
            return area, city
        return None, None
    
    def detect_area_indicators(self, query: str) -> bool:
        """Check if query contains area-specific indicators"""
        query_lower = query.lower()
        for pattern in self.area_indicators:
            if re.search(pattern, query_lower):
                return True
        return False
    
    def analyze_location_structure(self, query: str) -> dict:
        """Analyze the structure of location query for dynamic detection"""
        area, city = self.extract_area_city(query)
        has_area_indicators = self.detect_area_indicators(query)
        
        return {
            'extracted_area': area,
            'extracted_city': city,
            'has_area_indicators': has_area_indicators,
            'is_structured_area_query': area is not None and city is not None
        }

@tool("location-intelligence-tool", return_direct=False)
def analyze_location_query(location_query: str) -> dict:
    """
    Analyzes a user's location query to identify if it's a city, a state, or a specific area.
    Uses dynamic pattern recognition instead of hardcoded location lists.
    Returns a structured object with location analysis and area detection.
    """
    parser = JsonOutputParser(pydantic_object=LocationAnalysis)
    detector = AreaDetector()
    
    # First, perform dynamic area detection
    structure_analysis = detector.analyze_location_structure(location_query)
    
    # Enhanced prompt for dynamic location analysis
    prompt = ChatPromptTemplate.from_template(
        "You are a geography expert with dynamic location analysis capabilities. Analyze the user's location query.\n"
        "Context from pattern analysis:\n"
        "- Extracted area: {extracted_area}\n"
        "- Extracted city: {extracted_city}\n"
        "- Has area indicators: {has_area_indicators}\n"
        "- Is structured area query: {is_structured_area_query}\n\n"
        "Instructions:\n"
        "1. If this is a structured area query (Area, City format), populate:\n"
        "   - 'search_area' with the area name\n"
        "   - 'search_city' with the city name\n"
        "   - 'is_area_search' as true\n"
        "   - 'areas' with relevant area variations\n"
        "2. If it's a recognized state, populate 'state' field only\n"
        "3. If it's a city or region, populate 'cities' with common aliases\n"
        "4. For any location with area indicators, set 'is_area_search' to true\n"
        "5. Always try to extract the most specific location components\n\n"
        "{format_instructions}\n"
        "User's location query: {query}"
    )

    model = ChatOpenAI(model="gpt-4o", temperature=0)
    chain = prompt | model | parser
    
    result = chain.invoke({
        "query": location_query,
        "extracted_area": structure_analysis['extracted_area'],
        "extracted_city": structure_analysis['extracted_city'],
        "has_area_indicators": structure_analysis['has_area_indicators'],
        "is_structured_area_query": structure_analysis['is_structured_area_query'],
        "format_instructions": parser.get_format_instructions(),
    })
    
    # Enhance result with pattern-based detections
    if structure_analysis['is_structured_area_query']:
        result['search_area'] = structure_analysis['extracted_area']
        result['search_city'] = structure_analysis['extracted_city']
        result['is_area_search'] = True
        if not result.get('areas'):
            result['areas'] = [structure_analysis['extracted_area']]
    
    # Ensure is_area_search is set for queries with area indicators
    if structure_analysis['has_area_indicators'] and not result.get('is_area_search'):
        result['is_area_search'] = True
    
    return result