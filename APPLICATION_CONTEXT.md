# Warehouse Agentic Chatbot - Application Context

## Overview
A conversational AI warehouse discovery agent built with LangGraph, OpenAI, and FastAPI. The agent guides users through a structured 3-stage workflow to collect warehouse requirements and search for suitable properties.

## Architecture

### Core Components

#### 1. **LangGraph Workflow** (`graph.py`)
- **StateGraph**: Manages conversation flow through defined stages
- **Conditional Routing**: Routes between nodes based on user input and state
- **State Persistence**: Maintains conversation context across interactions

#### 2. **Conversation Nodes** (`nodes.py`)
- **area_and_size_node**: Collects location and size requirements
- **land_type_preference_node**: Determines industrial vs commercial preference
- **specific_requirements_node**: Gathers budget, structure type, and other specs
- **confirm_requirements_node**: Summarizes and confirms all requirements
- **search_database_node**: Executes warehouse search with collected criteria

#### 3. **State Management** (`state.py`)
- **GraphState**: Pydantic model defining all conversation state fields
- **Message History**: Tracks full conversation flow
- **Workflow Stages**: `area_and_size`, `land_type_preference`, `specifics`, `confirmation`

#### 4. **Tools** (`tools/`)
- **database_tool.py**: Simulates warehouse property database search
- **location_tool.py**: Expands location queries (e.g., "blr" → "Bangalore, Bengaluru")

#### 5. **API Interface** (`api.py`)
- **FastAPI**: RESTful endpoints for chat interactions
- **CORS**: Enabled for frontend integration
- **Session Management**: Thread-based conversation persistence

## Workflow Stages

### Stage 1: Area and Size Collection
- **Purpose**: Gather location and size requirements
- **Inputs**: City/location, size range (sqft)
- **Validation**: Location expansion via location_tool
- **Advancement**: Automatic when both location and size collected

### Stage 2: Land Type Preference
- **Purpose**: Determine industrial vs commercial/flexible preference
- **Template**: Structured question about warehouse type needs
- **Options**: Industrial (fire NOC required) vs Commercial/Flexible
- **Advancement**: User selection triggers move to specifics

### Stage 3: Specific Requirements
- **Purpose**: Collect additional specifications
- **Inputs**: 
  - Budget range (₹/sqft)
  - Structure type (PEB/RCC)
  - Loading docks
  - Other specifications
- **Flexibility**: Users can specify "none" to skip
- **Advancement**: Automatic when user input processed

### Stage 4: Confirmation and Search
- **Purpose**: Final confirmation before database search
- **Display**: Formatted requirements summary
- **Action**: "Proceed with search? (yes/no)"
- **Search**: Triggers database_tool execution

## Key Features

### Intelligent Conversation Flow
- **Stage Progression**: Automatic advancement based on requirement completion
- **Natural Language**: Conversational prompts and responses
- **Error Handling**: Graceful handling of unclear inputs
- **Context Awareness**: Maintains full conversation history

### Budget Range Support
- **Flexible Input**: Single values or ranges accepted
- **Parsing**: Regex-based extraction from natural language
- **State Fields**: `budget_min` and `budget_max` 
- **Display**: Proper formatting in confirmation summary

### Location Intelligence
- **Abbreviation Expansion**: "blr" → ["Bangalore", "Bengaluru"]
- **Tool Integration**: Leverages location_tool for city recognition
- **State Preservation**: Maintains original query and expanded results

### Template System
- **ChatPromptTemplate**: Structured prompts with JSON output
- **Variable Escaping**: Proper handling of template variables with `{{}}`
- **Output Parsing**: Pydantic models for structured responses

## Technical Implementation

### State Fields
```python
class GraphState(BaseModel):
    # Core conversation
    messages: List[Dict[str, str]]
    workflow_stage: str
    next_action: str
    
    # Requirements
    location_query: Optional[str]
    size_min: Optional[int]
    size_max: Optional[int]
    budget_min: Optional[float]
    budget_max: Optional[float]
    warehouse_type: Optional[str]
    land_type_industrial: Optional[bool]
    fire_noc_required: Optional[bool]
    
    # Processing state
    parsed_cities: List[str]
    parsed_state: Optional[str]
    requirements_confirmed: bool
```

### Routing Logic
```python
def router(state: GraphState) -> str:
    if state.next_action == "wait_for_user":
        return END
    elif state.next_action == "update_state":
        return state.workflow_stage
    elif state.next_action == "confirm_requirements":
        return "confirmation"
    elif state.next_action == "search_database":
        return "search"
```

### Confirmation Detection
- **Context Awareness**: Looks back through recent messages for "Proceed with search?"
- **Affirmative Detection**: Recognizes "yes", "proceed", "confirm" etc.
- **State Transition**: Sets `requirements_confirmed = True` and advances to search

## API Endpoints

### POST /chat
- **Purpose**: Main conversation endpoint
- **Input**: `{"message": "user input"}`
- **Output**: `{"response": "agent response", "status": "waiting/searching/complete"}`
- **Session**: Thread-based with UUID tracking

### GET /health
- **Purpose**: Service health check
- **Output**: `{"status": "healthy"}`

## Environment Requirements

### Dependencies
- **LangGraph**: 0.6.8+ for workflow management
- **OpenAI**: GPT models for conversation generation
- **FastAPI**: API framework
- **Pydantic**: Data validation and serialization
- **Colorama**: Terminal color output
- **Python-dotenv**: Environment variable management

### Environment Variables
```bash
OPENAI_API_KEY=sk-your-key-here
```

## Development Setup

### Installation
```bash
pip install -r requirements.txt
```

### Running API Server
```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

### Running CLI Version
```bash
python main.py
```

## Debug Features

### Comprehensive Logging
- **Stage Transitions**: Logs workflow stage changes
- **State Debugging**: Shows current field values
- **Confirmation Detection**: Detailed confirmation flow logging
- **Budget Tracking**: Monitors budget value preservation

### Debug Output Example
```
[DEBUG] Parsing user input in specifics stage: 'yes'
[DEBUG] Confirmation check - Has affirmative: True, Stage: specifics, Requirements confirmed: False
[DEBUG] Found confirmation message in recent history
[DEBUG] Confirming search and proceeding to database search
```

## Recent Enhancements

### Confirmation Loop Fix
- **Issue**: "yes" responses cycling back to confirmation instead of search
- **Solution**: Enhanced message history scanning to find confirmation context
- **Implementation**: Look back through last 5 messages for "Proceed with search?"

### Budget Range Implementation
- **Feature**: Support for budget ranges (min-max) vs single values
- **Parsing**: Regex patterns for natural language budget extraction
- **State**: Separate `budget_min` and `budget_max` fields

### Template Variable Fixes
- **Issue**: ChatPromptTemplate parsing errors with JSON variables
- **Solution**: Proper escaping with double braces `{{}}`
- **Templates**: All JSON templates updated with escaped variables

## Error Handling

### Common Issues
1. **Template Variables**: Ensure proper `{{}}` escaping in ChatPromptTemplate
2. **Confirmation Loops**: Message history context required for proper detection
3. **Budget Loss**: Simple confirmations need protection from requirement re-parsing
4. **Location Expansion**: Handle cases where location_tool returns no results

### Recovery Mechanisms
- **Graceful Degradation**: Continue workflow even with missing optional fields
- **User Guidance**: Clear prompts when input unclear or missing
- **State Preservation**: Protect collected requirements from accidental clearing

## Testing

### Manual Testing Flow
1. Start conversation with location request
2. Provide size requirements
3. Select land type preference
4. Specify or skip additional requirements
5. Confirm final summary
6. Verify search execution

### Key Test Cases
- Budget range input: "40-50 per sqft"
- Location abbreviations: "blr", "del", "mum"
- Confirmation responses: "yes", "proceed", "confirm"
- Requirement skipping: "none", "not applicable"

## Future Enhancements

### Planned Features
- **Real Database Integration**: Replace simulated search with actual property database
- **Enhanced Location Intelligence**: Support for area/neighborhood specifications
- **Filter Persistence**: Save and reuse search criteria across sessions
- **Multi-language Support**: Regional language conversation capabilities

### Scalability Considerations
- **Database Optimization**: Efficient querying for large property datasets
- **Caching**: Response caching for common location/requirement combinations
- **Rate Limiting**: API protection for production deployment
- **Analytics**: Conversation flow and requirement pattern analysis