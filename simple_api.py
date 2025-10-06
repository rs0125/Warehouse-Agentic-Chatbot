"""
Simplified API for testing
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Warehouse API Test")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple context model matching documentation
class SimpleContext(BaseModel):
    current_stage: str = "area_size"
    area: Optional[str] = None
    size_constraint: Optional[str] = None
    land_type_preference: Optional[str] = None
    specific_requirements: List[str] = []
    conversation_history: List[str] = []

class ChatRequest(BaseModel):
    message: str
    context: Optional[SimpleContext] = None

class ChatResponse(BaseModel):
    message: str
    context: SimpleContext

# Global graph variable
warehouse_graph = None

@app.on_event("startup")
async def startup_event():
    """Initialize the LangGraph workflow on startup"""
    global warehouse_graph
    
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not found")
        return
    
    try:
        from graph import create_warehouse_graph
        warehouse_graph = create_warehouse_graph()
        print("✅ Warehouse Discovery Agent initialized")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        warehouse_graph = None

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "agent_ready": warehouse_graph is not None}

@app.post("/start")
async def start_conversation():
    """Start conversation - just return greeting without complex workflow"""
    
    greeting = (
        "👋 Welcome to WareOnGo's warehouse discovery platform.\n\n"
        "I'll help you find suitable warehouse spaces through a quick 3-step process:\n"
        "1️⃣ Location & Size\n"
        "2️⃣ Land classification\n"
        "3️⃣ Additional requirements\n\n"
        "What location are you considering?"
    )
    
    context = SimpleContext(current_stage="area_size")
    
    return ChatResponse(message=greeting, context=context)

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """Process chat message"""
    
    if warehouse_graph is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    # For now, just echo the message and update context
    context = request.context or SimpleContext()
    
    # Simple stage progression logic
    if context.current_stage == "area_size" and request.message:
        context.area = request.message
        context.conversation_history.append(request.message)
        context.current_stage = "business_nature"
        
        return ChatResponse(
            message="Do you specifically need warehouses on industrial land with proper CLU (Change of Land Use)?",
            context=context
        )
    
    elif context.current_stage == "business_nature":
        context.land_type_preference = "yes" if "yes" in request.message.lower() else "no"
        context.conversation_history.append(request.message)
        context.current_stage = "specifics"
        
        return ChatResponse(
            message="Any specific requirements like Fire NOC, connectivity, etc.?",
            context=context
        )
    
    elif context.current_stage == "specifics":
        if request.message.lower() not in ["show me", "search", "find"]:
            context.specific_requirements.append(request.message)
        context.conversation_history.append(request.message)
        
        # Mock search results
        results = f"""
        <h3>🏢 Found 3 warehouses matching your criteria:</h3>
        
        <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px;">
            <h4>📍 Prime Warehouse Bangalore</h4>
            <p><strong>📍 Location:</strong> {context.area or 'Bangalore'}</p>
            <p><strong>📏 Size:</strong> 8000 sq ft</p>
            <p><strong>🌍 Land Type:</strong> {'Industrial' if context.land_type_preference == 'yes' else 'Commercial'}</p>
            <p><strong>🔥 Fire NOC:</strong> {'Available' if 'fire' in str(context.specific_requirements).lower() else 'Not Required'}</p>
            <p><strong>📞 Contact:</strong> +91-9876543210</p>
        </div>
        """
        
        return ChatResponse(message=results, context=context)
    
    else:
        return ChatResponse(
            message="I can help you find warehouses. Let's start with your location preference.",
            context=SimpleContext()
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)