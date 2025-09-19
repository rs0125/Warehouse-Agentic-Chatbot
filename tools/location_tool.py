    # location_tools.py

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.json import JsonOutputParser
from pydantic.v1 import BaseModel, Field
from typing import List, Optional

# CHANGED: The output model is now more structured
class LocationAnalysis(BaseModel):
    cities: Optional[List[str]] = Field(None, description="A list of canonical city names and aliases, used for city or sub-region queries.")
    state: Optional[str] = Field(None, description="A single canonical state name, used only when the user's query is a state.")

@tool("location-intelligence-tool", return_direct=False)
def analyze_location_query(location_query: str) -> dict:
    """
    Analyzes a user's location query to identify if it's a city, a state, or a sub-region.
    Returns a structured object with either a list of cities or a single state name.
    """
    parser = JsonOutputParser(pydantic_object=LocationAnalysis)
    
    # CHANGED: The prompt is now much smarter about distinguishing location types
    prompt = ChatPromptTemplate.from_template(
        "You are a geography expert. Analyze the user's location query and determine its type (city, state, or sub-region).\n"
        "1. If the query is a recognized state (e.g., 'Tamil Nadu', 'Karnataka'), populate the 'state' field with the canonical name and leave 'cities' as null.\n"
        "2. If the query is a city, alias, or abbreviation (e.g., 'blr', 'Chennai'), populate the 'cities' field with a list of all common aliases and leave 'state' as null.\n"
        "3. If the query is a sub-region (e.g., 'South Karnataka'), populate the 'cities' field with the major hub cities in that region and leave 'state' as null.\n"
        "{format_instructions}\n"
        "User's location query: {query}"
    )

    model = ChatOpenAI(model="gpt-4o", temperature=0)
    
    chain = prompt | model | parser
    
    return chain.invoke({
        "query": location_query,
        "format_instructions": parser.get_format_instructions(),
    })