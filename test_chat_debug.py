#!/usr/bin/env python3

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from graph import create_warehouse_graph
from state import GraphState
from api import context_to_state, state_to_context, ConversationContext

async def debug_chat_workflow():
    """Debug the exact same workflow as the chat endpoint"""
    
    # Create the graph
    graph = create_warehouse_graph()
    
    # Simulate the context from frontend
    frontend_context = ConversationContext(
        current_stage="area_size",
        area=None,
        size_constraint=None,
        land_type_preference=None,
        specific_requirements=[],
        conversation_history=[]
    )
    
    print("🔍 Testing the exact chat workflow...")
    print(f"📥 Frontend context: {frontend_context}")
    
    try:
        # Convert context to state (same as chat endpoint)
        state = context_to_state(frontend_context)
        print(f"🔄 Converted state workflow_stage: {state.workflow_stage}")
        print(f"🔄 Converted state next_action: {state.next_action}")
        print(f"🔄 Converted state messages: {len(state.messages)}")
        
        # Add user message (same as chat endpoint)
        user_message = "Can you share warehouses in blr"
        state.add_message("user", user_message)
        state.next_action = "update_state"
        
        print(f"✉️  Added user message: {user_message}")
        print(f"🔄 Set next_action to: {state.next_action}")
        print(f"📋 Total messages now: {len(state.messages)}")
        
        # Process through workflow (same as chat endpoint)
        config = {"configurable": {"thread_id": "stateless"}}
        result = await graph.ainvoke(state, config=config)
        
        print(f"✅ LangGraph execution successful")
        print(f"📋 Result messages count: {len(result['messages'])}")
        
        # Print all messages to see what happened
        for i, msg in enumerate(result['messages']):
            print(f"  Message {i}: {msg['role']} - {msg['content'][:80]}...")
        
        # Get the last assistant message (same as chat endpoint)
        assistant_messages = [msg for msg in result["messages"] if msg["role"] == "assistant"]
        response_text = assistant_messages[-1]["content"] if assistant_messages else "Hello! How can I help you find a warehouse?"
        
        print(f"🤖 Assistant response: {response_text[:100]}...")
        
        # Check workflow state
        print(f"📊 Final workflow_stage: {result.get('workflow_stage')}")
        print(f"📊 Final next_action: {result.get('next_action')}")
        
        return {
            "success": True,
            "response": response_text,
            "final_stage": result.get('workflow_stage'),
            "final_action": result.get('next_action')
        }
        
    except Exception as e:
        print(f"❌ Error in chat workflow: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    result = asyncio.run(debug_chat_workflow())
    if result["success"]:
        print("🎉 Chat workflow completed!")
        print(f"🔍 Analysis: Response {'seems correct' if 'blr' in result['response'].lower() or 'bangalore' in result['response'].lower() else 'seems wrong - still showing greeting'}")
    else:
        print("💥 Chat workflow failed!")