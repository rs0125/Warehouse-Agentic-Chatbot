# location_tools.py

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.json import JsonOutputParser
from pydantic.v1 import BaseModel, Field
from typing import List

class LocationAnalysis(BaseModel):
    cities: List[str] = Field(description="A comprehensive list of canonical city names and all their common aliases based on the user's query.")

@tool("location-intelligence-tool", return_direct=False)
def analyze_location_query(location_query: str) -> dict:
    """
    Analyzes a user's location query to resolve aliases (e.g., 'Blr' -> ['Bangalore', 'Bengaluru'])
    and decompose regions (e.g., 'South Karnataka' -> ['Mysore', 'Mandya', ...]).
    Returns a list of all relevant city names and their aliases for database searching.
    """
    parser = JsonOutputParser(pydantic_object=LocationAnalysis)
    
    prompt = ChatPromptTemplate.from_template(
        "You are a geography expert. Analyze the user's location query. "
        "Your goal is to produce a list of all possible variations of city names that should be searched in a database. "
        "Resolve any aliases, abbreviations, or misspellings. Return a list containing the canonical name AND its common aliases. "
        "For example, 'blr' or 'Bengaluru' should result in ['Bangalore', 'Bengaluru']. "
        "If the query is a region (like 'South Karnataka'), list the major industrial/warehouse hub cities within that region.\n"
        "{format_instructions}\n"
        "User's location query: {query}"
    )

    model = ChatOpenAI(model="gpt-4o", temperature=0)
    
    chain = prompt | model | parser
    
    return chain.invoke({
        "query": location_query,
        "format_instructions": parser.get_format_instructions(),
    })