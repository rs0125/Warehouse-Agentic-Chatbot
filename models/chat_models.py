# models/chat_models.py

from pydantic import BaseModel

class ChatRequest(BaseModel):
    user_input: str
    # A unique ID for each user's conversation
    session_id: str

class ChatResponse(BaseModel):
    # This is useful for non-streaming responses, but we'll stream text directly
    bot_response: str