#!/usr/bin/env python3

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from graph import create_warehouse_graph
from state import GraphState
from api import state_to_context

async def debug_api_workflow():
    """Debug the exact same workflow as the API"""
    
    # Create the graph (same as API)
    graph = create_warehouse_graph()
    
    # Create fresh state (same as start endpoint)
    state = GraphState()
    state.workflow_stage = "area_and_size"
    state.next_action = "greeting"
    
    print("🔍 Testing the exact API workflow...")
    
    try:
        # Process through workflow to get greeting (same as API)
        config = {"configurable": {"thread_id": "stateless"}}
        result = await graph.ainvoke(state, config=config)
        
        print(f"✅ LangGraph execution successful")
        print(f"📋 Result type: {type(result)}")
        print(f"📋 Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        
        # Get the greeting message (same as API)
        assistant_messages = [msg for msg in result["messages"] if msg["role"] == "assistant"]
        response_text = assistant_messages[-1]["content"] if assistant_messages else "Welcome to WareOnGo!"
        
        print(f"💬 Response text: {response_text[:100]}...")
        
        # Convert dict result back to GraphState (same as API fix)
        result_state = GraphState()
        for key, value in result.items():
            if hasattr(result_state, key):
                setattr(result_state, key, value)
                print(f"   Set {key} = {value}")
            else:
                print(f"   ⚠️  Skipped {key} (not in GraphState)")
        
        print(f"📊 Result state workflow_stage: {result_state.workflow_stage}")
        print(f"📊 Result state next_action: {result_state.next_action}")
        
        # Convert to context (same as API)
        response_context = state_to_context(result_state)
        
        print(f"🎯 Context conversion successful!")
        print(f"📄 Context current_stage: {response_context.current_stage}")
        print(f"📄 Context area: {response_context.area}")
        
        return {
            "message": response_text,
            "context": response_context,
            "conversation_complete": False
        }
        
    except Exception as e:
        print(f"❌ Error in workflow: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(debug_api_workflow())
    if result:
        print("🎉 Full workflow successful!")
    else:
        print("💥 Workflow failed!")