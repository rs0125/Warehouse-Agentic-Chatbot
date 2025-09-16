# api/chat.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from models.chat_models import ChatRequest
from services.agent_service import run_agent_stream

router = APIRouter()

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Receives a user's message and session ID, and streams the agent's response
    using Server-Sent Events (SSE).
    """
    return StreamingResponse(
        run_agent_stream(request.user_input, request.session_id), 
        media_type="text/event-stream"
    )