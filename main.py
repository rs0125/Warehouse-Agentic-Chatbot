# main.py

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.chat import router as chat_router

app = FastAPI(
    title="Warehouse Chatbot API",
    description="An intelligent agent for discovering warehouse properties.",
    version="1.0.0"
)

# Read the frontend URL from environment variables for security
# Default to a common dev port if the variable is not set
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

# List of allowed origins for CORS
origins = [
    frontend_url,
    "http://localhost:8000", # For the FastAPI docs
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Use the configured list of origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")

@app.get("/", tags=["Health Check"])
def read_root():
    """A simple health check endpoint."""
    return {"status": "ok", "message": "Welcome to the Warehouse Chatbot API!"}