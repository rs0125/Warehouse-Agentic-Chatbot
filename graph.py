# graph.py
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from colorama import Fore, Style

from state import GraphState
from nodes import (
    requirements_gatherer_node,
    update_state_node,
    confirm_requirements_node,
    search_database_node,
    human_input_node,
    chit_chat_node, # <-- Import the new node
)

def router(state: GraphState) -> Literal["gather_requirements", "confirm_requirements", "search_database", "human_input", "update_state", "chit_chat", "__end__"]:
    """Router function that determines the next node based on state."""
    if state.conversation_complete:
        return "__end__"
    
    print(f"{Fore.MAGENTA}[ROUTER]{Style.RESET_ALL} Next action: {state.next_action}")
    
    # ============================ ROUTER CHANGE HERE ============================
    # Add a simple rule for our new chit_chat action
    if state.next_action == "chit_chat":
        return "chit_chat"
    # =========================================================================

    if state.next_action == "wait_for_user":
        return "human_input"
    elif state.next_action == "update_state":
        return "update_state"
    elif state.next_action == "gather_requirements":
        if state.is_ready_for_search() and not state.requirements_confirmed:
            return "confirm_requirements"
        else:
            return "gather_requirements"
    elif state.next_action == "confirm_requirements":
        return "confirm_requirements"
    elif state.next_action == "search_database":
        return "search_database"
    else:
        return "gather_requirements"

def create_warehouse_graph():
    """Create and return the LangGraph workflow."""
    workflow = StateGraph(GraphState)
    
    # ============================ GRAPH CHANGE HERE ============================
    # Add the new node to the graph
    workflow.add_node("chit_chat", chit_chat_node)
    # =========================================================================

    workflow.add_node("gather_requirements", requirements_gatherer_node)
    workflow.add_node("update_state", update_state_node)
    workflow.add_node("confirm_requirements", confirm_requirements_node)
    workflow.add_node("search_database", search_database_node)
    workflow.add_node("human_input", human_input_node)
    
    workflow.set_entry_point("gather_requirements")
    
    workflow.add_conditional_edges("gather_requirements", router, {
        "confirm_requirements": "confirm_requirements", 
        "human_input": "human_input",
        "gather_requirements": "gather_requirements",
    })
    
    workflow.add_conditional_edges("update_state", router, {
        "gather_requirements": "gather_requirements",
        "confirm_requirements": "confirm_requirements",
        "search_database": "search_database",
        "chit_chat": "chit_chat", # <-- Add new path from update_state
    })
    
    # ============================ GRAPH CHANGE HERE ============================
    # Add an edge for our new node. After chatting, it waits for human input.
    workflow.add_conditional_edges("chit_chat", router, {
        "human_input": "human_input"
    })
    # =========================================================================
    
    workflow.add_conditional_edges("confirm_requirements", router, {
        "human_input": "human_input"
    })
    
    workflow.add_conditional_edges("search_database", router, {
        "human_input": "human_input"
    })
    
    workflow.add_conditional_edges("human_input", router, {
        "update_state": "update_state",
        "__end__": END
    })
    
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app