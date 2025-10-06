"""
FastAPI server for Warehouse Discovery Agent
Stateless design - frontend sends conversation context with each request
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import os
from dataclasses import asdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from graph import create_warehouse_graph
from state import GraphState

app = FastAPI(
    title="WareOnGo Warehouse Discovery API",
    description="AI-powered warehouse discovery platform",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests/responses
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ConversationContext(BaseModel):
    # Simple context structure for frontend
    current_stage: str = "area_size"
    area: Optional[str] = None
    size_constraint: Optional[str] = None
    size_min: Optional[int] = None  # Add actual size values
    size_max: Optional[int] = None  # Add actual size values
    land_type_preference: Optional[str] = None
    specific_requirements: List[str] = []
    conversation_history: List[str] = []

class ChatRequest(BaseModel):
    message: str
    context: Optional[ConversationContext] = None

class ChatResponse(BaseModel):
    message: str
    context: ConversationContext
    conversation_complete: bool = False

# Initialize the graph once
warehouse_graph = None

@app.on_event("startup")
async def startup_event():
    """Initialize the LangGraph workflow on startup"""
    global warehouse_graph
    
    # Check for OpenAI API key
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not found. Please set it before making requests.")
        print("   You can set it with: export OPENAI_API_KEY='your-key-here'")
        return
    
    try:
        warehouse_graph = create_warehouse_graph()
        print("✅ Warehouse Discovery Agent initialized")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        warehouse_graph = None

def context_to_state(context: Optional[ConversationContext]) -> GraphState:
    """Convert API context to GraphState object"""
    if context is None:
        # Start fresh conversation
        state = GraphState()
        state.workflow_stage = "area_and_size"
        state.next_action = "greeting"  # Start with greeting
        return state
    
    # Convert simple context to state
    state = GraphState()
    
    # Add conversation history as messages
    for msg in context.conversation_history:
        state.add_message("user", msg)
    
    # Map simple fields to state
    if context.area:
        state.location_query = context.area
        state.parsed_cities = [context.area]
    
    # Use actual size values if available, otherwise fall back to size constraint
    if context.size_min is not None or context.size_max is not None:
        # Use the actual size values from the context
        state.size_min = context.size_min
        state.size_max = context.size_max
    elif context.size_constraint:
        # Fallback to size constraint mapping only if no actual values
        if "small" in context.size_constraint.lower():
            state.size_max = 5000
        elif "medium" in context.size_constraint.lower():
            state.size_min = 5001
            state.size_max = 15000
        elif "large" in context.size_constraint.lower():
            state.size_min = 15001
    
    if context.land_type_preference == "yes":
        state.land_type_industrial = True
    elif context.land_type_preference == "no":
        state.land_type_industrial = False
    
    if "fire noc" in str(context.specific_requirements).lower():
        state.fire_noc_required = True
    
    # Map stages
    stage_map = {
        "area_size": "area_and_size",
        "business_nature": "land_type_preference", 
        "specifics": "specifics"
    }
    state.workflow_stage = stage_map.get(context.current_stage, "area_and_size")
    
    return state

def state_to_context(state) -> ConversationContext:
    """Convert GraphState or dict to simple API context"""
    
    # Helper function to safely get attributes from state (dict or object)
    def get_attr(obj, attr, default=None):
        if hasattr(obj, attr):
            return getattr(obj, attr)
        elif isinstance(obj, dict):
            return obj.get(attr, default)
        return default
    
    # Extract area from location query or parsed cities
    area = None
    location_query = get_attr(state, 'location_query')
    parsed_cities = get_attr(state, 'parsed_cities')
    if location_query:
        area = location_query
    elif parsed_cities:
        area = parsed_cities[0]
    
    # Extract size constraint
    size_constraint = None
    size_max = get_attr(state, 'size_max')
    size_min = get_attr(state, 'size_min')
    if size_max and size_max <= 5000:
        size_constraint = "small"
    elif size_min and size_min >= 15001:
        size_constraint = "large"
    elif size_min or size_max:
        size_constraint = "medium"
    
    # Extract land type preference
    land_type_preference = None
    land_type_industrial = get_attr(state, 'land_type_industrial')
    if land_type_industrial is True:
        land_type_preference = "yes"
    elif land_type_industrial is False:
        land_type_preference = "no"
    
    # Extract specific requirements
    specific_requirements = []
    fire_noc_required = get_attr(state, 'fire_noc_required')
    if fire_noc_required:
        specific_requirements.append("fire noc required")
    
    # Extract conversation history (user messages only)
    messages = get_attr(state, 'messages', [])
    conversation_history = [
        msg["content"] for msg in messages 
        if msg["role"] == "user"
    ]
    
    # Map stages back
    stage_map = {
        "area_and_size": "area_size",
        "land_type_preference": "business_nature",
        "specifics": "specifics"
    }
    workflow_stage = get_attr(state, 'workflow_stage', 'area_and_size')
    current_stage = stage_map.get(workflow_stage, "area_size")
    
    return ConversationContext(
        current_stage=current_stage,
        area=area,
        size_constraint=size_constraint,
        size_min=get_attr(state, 'size_min'),
        size_max=get_attr(state, 'size_max'),
        land_type_preference=land_type_preference,
        specific_requirements=specific_requirements,
        conversation_history=conversation_history
    )

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint - processes user message through the workflow
    
    Frontend sends:
    - User message
    - Previous conversation context (optional for first message)
    
    Backend returns:
    - Agent response
    - Updated conversation context
    - Conversation completion status
    """
    if warehouse_graph is None:
        raise HTTPException(status_code=503, detail="Agent not initialized. Please check OpenAI API key.")
    
    try:
        # Convert context to state
        state = context_to_state(request.context)
        
        # Add user message if provided
        if request.message.strip():
            state.add_message("user", request.message)
            state.next_action = "update_state"
        
        # Process through workflow
        config = {"configurable": {"thread_id": "stateless"}}
        
        # Run the workflow
        result = await warehouse_graph.ainvoke(state, config=config)
        
        # Get the last assistant message
        assistant_messages = [msg for msg in result["messages"] if msg["role"] == "assistant"]
        response_text = assistant_messages[-1]["content"] if assistant_messages else "Hello! How can I help you find a warehouse?"
        
        # Convert dict result directly to context (state_to_context can handle dicts now)
        response_context = state_to_context(result)
        
        # Get conversation_complete from result
        conversation_complete = result.get('conversation_complete', False)
        
        return ChatResponse(
            message=response_text,
            context=response_context,
            conversation_complete=conversation_complete
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/start", response_model=ChatResponse)
async def start_conversation() -> ChatResponse:
    """
    Start a new conversation - returns greeting message
    """
    if warehouse_graph is None:
        raise HTTPException(status_code=503, detail="Agent not initialized. Please check OpenAI API key.")
    
    try:
        # Create fresh state
        state = GraphState()
        state.workflow_stage = "area_and_size"
        state.next_action = "greeting"
        
        # Process through workflow to get greeting
        config = {"configurable": {"thread_id": "stateless"}}
        result = await warehouse_graph.ainvoke(state, config=config)
        
        # Get the greeting message
        assistant_messages = [msg for msg in result["messages"] if msg["role"] == "assistant"]
        response_text = assistant_messages[-1]["content"] if assistant_messages else "Welcome to WareOnGo!"
        
        # Convert dict result directly to context (state_to_context can handle dicts now)
        response_context = state_to_context(result)
        
        return ChatResponse(
            message=response_text,
            context=response_context,
            conversation_complete=False
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting conversation: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "WareOnGo Warehouse Discovery API"}

@app.get("/")
async def root():
    """API root - basic info"""
    return {
        "service": "WareOnGo Warehouse Discovery API",
        "version": "1.0.0",
        "endpoints": {
            "start": "POST /start - Start new conversation",
            "chat": "POST /chat - Send message and get response",
            "health": "GET /health - Health check"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)