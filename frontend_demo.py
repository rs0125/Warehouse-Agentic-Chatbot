"""
Example Frontend Integration - demonstrates how to interact with the API
This shows exactly how your React/Vue/etc frontend should communicate with the backend
"""

import requests
import json
from typing import Optional, Dict, Any

API_BASE = "http://localhost:8000"

class WarehouseDiscoveryClient:
    """
    Example client demonstrating frontend-backend communication
    
    In your actual frontend:
    - Replace requests with fetch() or axios
    - Store context in component state or localStorage
    - Handle UI updates based on responses
    """
    
    def __init__(self):
        self.context: Optional[Dict[Any, Any]] = None
    
    def start_conversation(self) -> str:
        """Start a new conversation - equivalent to page load"""
        try:
            response = requests.post(f"{API_BASE}/start")
            response.raise_for_status()
            
            data = response.json()
            self.context = data["context"]
            
            return data["response"]
        except Exception as e:
            return f"Error starting conversation: {e}"
    
    def send_message(self, message: str) -> str:
        """Send user message and get agent response"""
        try:
            payload = {
                "message": message,
                "context": self.context
            }
            
            response = requests.post(f"{API_BASE}/chat", json=payload)
            response.raise_for_status()
            
            data = response.json()
            # Update context for next request
            self.context = data["context"]
            
            return data["response"]
        except Exception as e:
            return f"Error sending message: {e}"
    
    def get_conversation_status(self) -> Dict[str, Any]:
        """Get current conversation state - useful for UI"""
        if not self.context:
            return {"stage": "not_started", "complete": False}
        
        return {
            "stage": self.context.get("workflow_stage", "unknown"),
            "complete": self.context.get("conversation_complete", False),
            "location": self.context.get("location_query"),
            "size_min": self.context.get("size_min"),
            "size_max": self.context.get("size_max"),
            "land_type": "Industrial" if self.context.get("land_type_industrial") else "Commercial" if self.context.get("land_type_industrial") is False else None
        }

def demo_conversation():
    """
    Demo showing complete conversation flow
    This is exactly how your frontend should work
    """
    print("🏢 WareOnGo API Demo - Frontend Integration Example")
    print("=" * 60)
    
    client = WarehouseDiscoveryClient()
    
    # 1. Start conversation (page load)
    print("\n1. Starting conversation...")
    response = client.start_conversation()
    print(f"Agent: {response}")
    
    # 2. User provides location and size
    print(f"\nStatus: {client.get_conversation_status()}")
    user_input = "I need a warehouse in Mumbai, 30000 sqft"
    print(f"User: {user_input}")
    response = client.send_message(user_input)
    print(f"Agent: {response}")
    
    # 3. User specifies land type
    print(f"\nStatus: {client.get_conversation_status()}")
    user_input = "commercial"
    print(f"User: {user_input}")
    response = client.send_message(user_input)
    print(f"Agent: {response}")
    
    # 4. User specifies additional requirements
    print(f"\nStatus: {client.get_conversation_status()}")
    user_input = "fire NOC required, PEB structure"
    print(f"User: {user_input}")
    response = client.send_message(user_input)
    print(f"Agent: {response}")
    
    # 5. User confirms and searches
    print(f"\nStatus: {client.get_conversation_status()}")
    user_input = "yes"
    print(f"User: {user_input}")
    response = client.send_message(user_input)
    print(f"Agent: {response}")
    
    print(f"\nFinal Status: {client.get_conversation_status()}")
    print("\n" + "=" * 60)
    print("Demo complete! This shows exactly how your frontend should integrate.")

if __name__ == "__main__":
    demo_conversation()