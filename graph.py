# graph.py
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from colorama import Fore, Style

from state import GraphState
from nodes import (
    greeting_node,
    area_size_gatherer_node,
    business_nature_gatherer_node,
    specifics_gatherer_node,
    update_state_node,
    confirm_requirements_node,
    search_database_node,
    human_input_node,
    chit_chat_node,
)

def router(state: GraphState) -> Literal["greeting", "gather_area_size", "gather_business_nature", "gather_specifics", "confirm_requirements", "search_database", "human_input", "update_state", "chit_chat", "__end__"]:
    """Router function that determines the next node based on state."""
    if state.conversation_complete:
        return "__end__"
    
    print(f"{Fore.MAGENTA}[ROUTER]{Style.RESET_ALL} Next action: {state.next_action}")
    
    if state.next_action == "chit_chat":
        return "chit_chat"
    elif state.next_action == "wait_for_user":
        # In API mode, we end here so the frontend can send the next message
        # In CLI mode, this would go to human_input, but API handles it differently
        return "__end__"
    elif state.next_action == "update_state":
        return "update_state"
    elif state.next_action == "gather_area_size":
        return "gather_area_size"
    elif state.next_action == "gather_business_nature":
        return "gather_business_nature"
    elif state.next_action == "gather_specifics":
        return "gather_specifics"
    elif state.next_action == "confirm_requirements":
        return "confirm_requirements"
    elif state.next_action == "search_database":
        return "search_database"
    elif state.next_action == "greeting":
        return "greeting"
    else:
        # Default based on workflow stage
        if state.workflow_stage == "area_and_size":
            return "gather_area_size"
        elif state.workflow_stage == "nature_of_business":
            return "gather_business_nature"
        elif state.workflow_stage == "specifics":
            return "gather_specifics"
        else:
            return "gather_area_size"

def create_warehouse_graph():
    """Create and return the LangGraph workflow."""
    workflow = StateGraph(GraphState)
    
    # Add all nodes
    workflow.add_node("entry_router", lambda state: state)  # Pass-through node
    workflow.add_node("greeting", greeting_node)
    workflow.add_node("gather_area_size", area_size_gatherer_node)
    workflow.add_node("gather_business_nature", business_nature_gatherer_node)
    workflow.add_node("gather_specifics", specifics_gatherer_node)
    workflow.add_node("chit_chat", chit_chat_node)
    workflow.add_node("update_state", update_state_node)
    workflow.add_node("confirm_requirements", confirm_requirements_node)
    workflow.add_node("search_database", search_database_node)
    workflow.add_node("human_input", human_input_node)
    
    # Set entry_router as the entry point
    workflow.set_entry_point("entry_router")
    
    # Add conditional edges
    # Entry router decides where to start based on state
    workflow.add_conditional_edges("entry_router", router, {
        "greeting": "greeting",
        "gather_area_size": "gather_area_size",
        "gather_business_nature": "gather_business_nature", 
        "gather_specifics": "gather_specifics",
        "update_state": "update_state",
        "confirm_requirements": "confirm_requirements",
        "search_database": "search_database",
        "chit_chat": "chit_chat",
        "human_input": "human_input",
        "__end__": END
    })
    
    workflow.add_conditional_edges("greeting", router, {
        "human_input": "human_input",
        "__end__": END
    })
    
    workflow.add_conditional_edges("gather_area_size", router, {
        "human_input": "human_input",
        "gather_business_nature": "gather_business_nature",
        "__end__": END
    })
    
    workflow.add_conditional_edges("gather_business_nature", router, {
        "human_input": "human_input",
        "gather_specifics": "gather_specifics",
        "__end__": END
    })
    
    workflow.add_conditional_edges("gather_specifics", router, {
        "human_input": "human_input", 
        "confirm_requirements": "confirm_requirements",
        "__end__": END
    })
    
    workflow.add_conditional_edges("update_state", router, {
        "gather_area_size": "gather_area_size",
        "gather_business_nature": "gather_business_nature",
        "gather_specifics": "gather_specifics",
        "confirm_requirements": "confirm_requirements",
        "search_database": "search_database",
        "chit_chat": "chit_chat",
        "__end__": END
    })
    
    workflow.add_conditional_edges("chit_chat", router, {
        "human_input": "human_input",
        "__end__": END
    })
    
    workflow.add_conditional_edges("confirm_requirements", router, {
        "human_input": "human_input",
        "__end__": END
    })
    
    workflow.add_conditional_edges("search_database", router, {
        "human_input": "human_input",
        "__end__": END
    })
    
    workflow.add_conditional_edges("human_input", router, {
        "update_state": "update_state",
        "__end__": END
    })
    
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app