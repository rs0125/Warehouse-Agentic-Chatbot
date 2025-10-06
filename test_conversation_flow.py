#!/usr/bin/env python3

import asyncio
import requests
import json

async def test_conversation_flow():
    """Test the exact conversation flow that's causing issues"""
    
    base_url = "http://localhost:8000"
    
    print("🧪 Testing full conversation flow...")
    
    # Step 1: Start conversation
    print("\n1️⃣ Starting conversation...")
    start_response = requests.post(f"{base_url}/start")
    if start_response.status_code != 200:
        print(f"❌ Start failed: {start_response.status_code}")
        return
    
    start_data = start_response.json()
    print(f"✅ Start response: {start_data['message'][:50]}...")
    context = start_data['context']
    print(f"📄 Initial context: {context}")
    
    # Step 2: Send "bangalore"
    print("\n2️⃣ Sending: bangalore")
    chat_response = requests.post(f"{base_url}/chat", json={
        "message": "bangalore",
        "context": context
    })
    
    if chat_response.status_code != 200:
        print(f"❌ Chat failed: {chat_response.status_code}")
        return
    
    chat_data = chat_response.json()
    print(f"✅ Response: {chat_data['message'][:50]}...")
    context = chat_data['context']
    print(f"📄 Context after bangalore: {context}")
    
    # Step 3: Send "5000 sqft"
    print("\n3️⃣ Sending: 5000 sqft")
    chat_response = requests.post(f"{base_url}/chat", json={
        "message": "5000 sqft",
        "context": context
    })
    
    if chat_response.status_code != 200:
        print(f"❌ Chat failed: {chat_response.status_code}")
        return
    
    chat_data = chat_response.json()
    print(f"✅ Response: {chat_data['message'][:50]}...")
    context = chat_data['context']
    print(f"📄 Context after size: {context}")
    
    # Step 4: Send "commercial" (this should work but doesn't)
    print("\n4️⃣ Sending: commercial")
    chat_response = requests.post(f"{base_url}/chat", json={
        "message": "commercial",
        "context": context
    })
    
    if chat_response.status_code != 200:
        print(f"❌ Chat failed: {chat_response.status_code}")
        return
    
    chat_data = chat_response.json()
    print(f"✅ Response: {chat_data['message'][:50]}...")
    context = chat_data['context']
    print(f"📄 Context after commercial: {context}")
    
    # Check if we're stuck in land type loop
    if "land classification" in chat_data['message'].lower():
        print("❌ ISSUE CONFIRMED: Still asking for land classification!")
        print(f"🔍 Context details:")
        print(f"   current_stage: {context.get('current_stage')}")
        print(f"   land_type_preference: {context.get('land_type_preference')}")
        print(f"   area: {context.get('area')}")
        print(f"   size_constraint: {context.get('size_constraint')}")
    else:
        print("✅ SUCCESS: Progressed to next stage!")
        print(f"📄 Final context: {context}")

if __name__ == "__main__":
    asyncio.run(test_conversation_flow())