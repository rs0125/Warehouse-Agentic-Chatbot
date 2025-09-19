import json
import asyncio
import re
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import colorama
from colorama import Fore, Style, Back

# Assume these tools exist and are correctly defined in their respective files
from tools.database_tool import find_warehouses_in_db
from tools.location_tool import analyze_location_query


load_dotenv()
colorama.init()

# =============================================================================
# STATE DEFINITION
# =============================================================================

@dataclass
class GraphState:
    """Central state object that tracks the conversation and user requirements."""
    
    # Conversation tracking
    messages: List[Dict[str, str]] = field(default_factory=list)
    
    # User requirements (slot-filling)
    location_query: Optional[str] = None
    parsed_cities: Optional[List[str]] = None
    parsed_state: Optional[str] = None
    size_min: Optional[int] = None
    size_max: Optional[int] = None
    budget_max: Optional[int] = None
    warehouse_type: Optional[str] = None
    compliances_query: Optional[str] = None
    min_docks: Optional[int] = None
    min_clear_height: Optional[int] = None
    availability: Optional[str] = None
    zone: Optional[str] = None
    is_broker: Optional[bool] = None
    
    # Search state
    search_results: Optional[str] = None
    current_page: int = 1
    requirements_confirmed: bool = False
    
    # Flow control
    next_action: str = "gather_requirements"
    conversation_complete: bool = False
    
    def add_message(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.messages.append({"role": role, "content": content})
    
    def get_missing_requirements(self) -> List[str]:
        """Identify which requirements are still missing."""
        missing = []
        if not self.location_query:
            missing.append("location")
        if not self.size_min and not self.size_max:
            missing.append("size requirements")
        return missing
    
    def is_ready_for_search(self) -> bool:
        """Check if we have minimum requirements for search."""
        return bool(self.location_query and (self.size_min or self.size_max or self.budget_max))

# =============================================================================
# LANGGRAPH NODES
# =============================================================================

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)

async def requirements_gatherer_node(state: GraphState) -> GraphState:
    """Node that determines what to ask the user next."""
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Requirements gatherer analyzing state...")
    
    missing_requirements = state.get_missing_requirements()
    
    if not missing_requirements:
        state.next_action = "confirm_requirements"
        return state
    
    # Use a simpler, more direct approach to generate questions
    if not state.location_query:
        question = "Where would you like the warehouse to be located? (e.g., Bangalore, Karnataka, or South India)"
    elif not state.size_min and not state.size_max:
        question = "What size warehouse do you need? Please specify in square feet (e.g., 50000 sqft or between 30000-80000 sqft)"
    elif not state.budget_max:
        question = "What's your budget range? Please specify the maximum rate per square foot (e.g., ₹20 per sqft)"
    else:
        # Ask about additional requirements
        if not state.warehouse_type:
            question = "Do you have any preference for warehouse type? (e.g., PEB, RCC, built-up)"
        elif not state.min_docks:
            question = "How many loading docks do you need minimum? (e.g., 2 docks)"
        elif not state.compliances_query:
            question = "Do you need any specific compliances? (e.g., fire safety, environmental clearance)"
        else:
            question = "Do you have any other specific requirements? (clear height, availability timeline, zone preference, etc.)"
    
    state.add_message("assistant", question)
    print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {question}")
    
    state.next_action = "wait_for_user"
    return state

async def update_state_node(state: GraphState) -> GraphState:
    """Node that parses user input and updates the state."""
    if not state.messages or state.messages[-1]["role"] != "user":
        state.next_action = "gather_requirements"
        return state
    
    user_message = state.messages[-1]["content"]
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Parsing user input: '{user_message}'")
    
    if user_message.lower() in ["more", "next", "show more"]:
        state.current_page += 1
        state.next_action = "search_database"
        return state
    
    if user_message.lower() in ["yes", "confirm", "looks good", "correct"]:
        state.requirements_confirmed = True
        state.next_action = "search_database"
        return state
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are extracting warehouse requirements from user messages. 
        IMPORTANT: Return ONLY a raw JSON object. Do NOT wrap it in markdown code blocks or add any other text.
        Return this exact JSON structure:
        {{"location_query": null, "size_min": null, "size_max": null, "budget_max": null, "warehouse_type": null, "compliances_query": null, "min_docks": null, "min_clear_height": null, "availability": null, "zone": null, "is_broker": null}}
        Only change null values to actual values when explicitly mentioned in the user message.
        """),
        ("user", "Extract requirements from this message: {message}")
    ])
    
    try:
        chain = prompt | llm
        response = await chain.ainvoke({"message": user_message})
        
        try:
            content = response.content.strip()
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            json_str = json_match.group(1) if json_match else content
            parsed_data = json.loads(json_str)
            
            parameter_changed = False
            
            if parsed_data.get("location_query"):
                state.location_query = parsed_data["location_query"]
                state.parsed_cities = None
                state.parsed_state = None
                parameter_changed = True
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated location: {state.location_query}")

            parsed_min_val = parsed_data.get("size_min")
            parsed_max_val = parsed_data.get("size_max")

            if parsed_min_val and parsed_max_val:
                size_min, size_max = int(parsed_min_val), int(parsed_max_val)
                if size_min == size_max:
                    single_size = size_min
                    deviation = 0.20
                    state.size_min, state.size_max = int(single_size * (1 - deviation)), int(single_size * (1 + deviation))
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Created flexible size range: {state.size_min} - {state.size_max} sqft")
                else:
                    state.size_min, state.size_max = size_min, size_max
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated with explicit size range: {state.size_min} - {state.size_max} sqft")
                parameter_changed = True
            elif parsed_min_val or parsed_max_val:
                single_size = int(parsed_min_val or parsed_max_val)
                deviation = 0.20
                state.size_min, state.size_max = int(single_size * (1 - deviation)), int(single_size * (1 + deviation))
                parameter_changed = True
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Created flexible size range: {state.size_min} - {state.size_max} sqft")

            if parsed_data.get("budget_max"):
                state.budget_max = int(parsed_data["budget_max"])
                parameter_changed = True
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated budget: {state.budget_max}")
                
            if parsed_data.get("warehouse_type"):
                state.warehouse_type = parsed_data["warehouse_type"]
                parameter_changed = True
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated type: {state.warehouse_type}")
            
            if parsed_data.get("compliances_query"):
                state.compliances_query = parsed_data["compliances_query"]
                parameter_changed = True
            if parsed_data.get("min_docks"):
                state.min_docks = int(parsed_data["min_docks"])
                parameter_changed = True
            if parsed_data.get("min_clear_height"):
                state.min_clear_height = int(parsed_data["min_clear_height"])
                parameter_changed = True
            if parsed_data.get("availability"):
                state.availability = parsed_data["availability"]
                parameter_changed = True
            if parsed_data.get("zone"):
                state.zone = parsed_data["zone"]
                parameter_changed = True
            if parsed_data.get("is_broker") is not None:
                state.is_broker = bool(parsed_data["is_broker"])
                parameter_changed = True

            if parameter_changed:
                state.requirements_confirmed = False
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Search parameters changed, resetting confirmation status.")
                
        except json.JSONDecodeError as je:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse JSON from LLM: {je}")
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} LLM response was: {response.content}")
            
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse user input: {e}")
    
    state.next_action = "gather_requirements"
    return state

async def confirm_requirements_node(state: GraphState) -> GraphState:
    """Node that confirms requirements with the user before searching."""
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Confirming requirements...")
    summary_parts = []
    
    if state.location_query:
        summary_parts.append(f"📍 Location: {state.location_query}")
    if state.size_min or state.size_max:
        size_range = f"{state.size_min or '0'} - {state.size_max or '∞'} sqft"
        summary_parts.append(f"📦 Size: {size_range}")
    if state.budget_max:
        summary_parts.append(f"💰 Budget: up to ₹{state.budget_max}/sqft")
    if state.warehouse_type:
        summary_parts.append(f"🏗️ Type: {state.warehouse_type}")
    if state.compliances_query:
        summary_parts.append(f"✅ Compliances: {state.compliances_query}")
    if state.min_docks:
        summary_parts.append(f"🚛 Min Docks: {state.min_docks}")
    if state.min_clear_height:
        summary_parts.append(f"📏 Min Height: {state.min_clear_height} ft")
    if state.availability:
        summary_parts.append(f"⏰ Availability: {state.availability}")
    
    confirmation_message = (
        "Let me confirm your requirements:\n\n" + 
        "\n".join(summary_parts) + 
        "\n\nShall I search for warehouses matching these criteria? (yes/no)"
    )
    
    state.add_message("assistant", confirmation_message)
    print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {confirmation_message}")
    
    state.next_action = "wait_for_user"
    return state

async def search_database_node(state: GraphState) -> GraphState:
    """Node that performs the actual warehouse search."""
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Searching database...")
    
    if state.location_query and not state.parsed_cities and not state.parsed_state:
        try:
            print(f"{Fore.YELLOW}[TOOL]{Style.RESET_ALL} Analyzing location: {state.location_query}")
            location_result = await analyze_location_query.ainvoke({"location_query": state.location_query})
            print(f"{Fore.YELLOW}[TOOL RESULT]{Style.RESET_ALL} {location_result}")
            
            if isinstance(location_result, dict):
                if location_result.get("cities"):
                    state.parsed_cities = location_result["cities"]
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Parsed cities: {state.parsed_cities}")
                elif location_result.get("state"):
                    state.parsed_state = location_result["state"]
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Parsed state: {state.parsed_state}")
            else:
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Location analysis tool returned an unexpected format.")
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Location analysis failed: {e}")

    search_params = {
        "cities": state.parsed_cities, "state": state.parsed_state, "min_sqft": state.size_min,
        "max_sqft": state.size_max, "max_rate_per_sqft": state.budget_max, "warehouse_type": state.warehouse_type,
        "compliances": state.compliances_query, "min_docks": state.min_docks,
        "min_clear_height": state.min_clear_height, "availability": state.availability,
        "zone": state.zone, "is_broker": state.is_broker, "page": state.current_page
    }
    search_params = {k: v for k, v in search_params.items() if v is not None}
    
    try:
        print(f"{Fore.YELLOW}[TOOL]{Style.RESET_ALL} Searching with params: {search_params}")
        search_results = await find_warehouses_in_db.ainvoke(search_params)
        print(f"{Fore.YELLOW}[TOOL RESULT]{Style.RESET_ALL} Found results")
        
        state.search_results = search_results
        
        response_message = f"🏢 **Warehouse Search Results (Page {state.current_page})**\n\n{search_results}"
        if "No warehouses found" not in search_results and "No more warehouses" not in search_results:
            response_message += "\n\n💡 *Say 'more' or 'next' to see additional options*"
        
        state.add_message("assistant", response_message)
        print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {response_message}")
    except Exception as e:
        error_message = f"I encountered an error while searching: {str(e)}"
        state.add_message("assistant", error_message)
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {error_message}")
    
    state.next_action = "wait_for_user"
    return state

async def human_input_node(state: GraphState) -> GraphState:
    """Node that handles human input."""
    user_input = input(f"{Fore.CYAN}[YOU]{Style.RESET_ALL} ").strip()
    
    if user_input.lower() in ['quit', 'exit', 'bye']:
        state.conversation_complete = True
        state.add_message("assistant", "Goodbye! Feel free to return anytime for warehouse searches.")
        print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} Goodbye! Feel free to return anytime.")
        return state
    
    state.add_message("user", user_input)
    state.next_action = "update_state"
    return state

# =============================================================================
# ROUTING LOGIC
# =============================================================================
def router(state: GraphState) -> Literal["gather_requirements", "confirm_requirements", "search_database", "human_input", "update_state", "__end__"]:
    """Router function that determines the next node based on state."""
    
    if state.conversation_complete:
        return "__end__"
    
    print(f"{Fore.MAGENTA}[ROUTER]{Style.RESET_ALL} Next action: {state.next_action}")
    
    if state.next_action == "wait_for_user":
        return "human_input"
        
    # ============================ FIX STARTS HERE ============================
    # This line is necessary to handle the transition from human_input to update_state.
    elif state.next_action == "update_state":
        return "update_state"
    # ============================= FIX ENDS HERE =============================

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
        # A sensible default
        return "gather_requirements"
# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def create_warehouse_graph():
    """Create and return the LangGraph workflow."""
    workflow = StateGraph(GraphState)
    
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
    })
    
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

# =============================================================================
# CLI INTERFACE
# =============================================================================

async def run_cli_chatbot():
    """Main CLI chatbot interface."""
    print(f"\n{Back.BLUE}{Fore.WHITE} 🏢 WAREHOUSE DISCOVERY AGENT (LangGraph) 🏢 {Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Welcome! I'll help you find warehouse properties.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Type 'quit', 'exit', or 'bye' to end the conversation.{Style.RESET_ALL}\n")
    
    app = create_warehouse_graph()
    
    import uuid
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        async for event in app.astream({}, config=config):
            for key, value in event.items():
                if key == "__end__":
                    return
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Conversation interrupted. Goodbye!{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    asyncio.run(run_cli_chatbot())