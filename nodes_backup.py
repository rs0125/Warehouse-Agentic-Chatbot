# nodes.py
import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
from colorama import Fore, Style

from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser

from state import GraphState
from tools.database_tool import find_warehouses_in_db
from tools.location_tool import analyze_location_query

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0.7) # Slightly increased temp for more creative chat

# ============================ GREETING NODE STARTS HERE ============================
async def greeting_node(state: GraphState) -> GraphState:
    """Initial greeting node that welcomes the user and explains what the agent can do."""
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Starting with greeting...")
    
    greeting_message = (
        "👋 Welcome to WareOnGo's warehouse discovery platform.\n\n"
        "I'll help you find suitable warehouse spaces through a quick 3-step process:\n"
        "1️⃣ Location & Size\n"
        "2️⃣ Land classification\n"
        "3️⃣ Additional requirements\n\n"
        "What location are you considering?"
    )
    
    state.add_message("assistant", greeting_message)
    print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {greeting_message}")
    
    state.workflow_stage = "area_and_size"
    state.next_action = "wait_for_user"
    return state
# ============================ GREETING NODE ENDS HERE ============================

# ============================ STAGE-SPECIFIC NODES START HERE ============================
async def area_size_gatherer_node(state: GraphState) -> GraphState:
    """Stage 1: Gather location and size requirements."""
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Stage 1: Gathering area and size...")
    
    missing_requirements = state.get_missing_requirements()
    
    if not missing_requirements:
        # Both location and size are collected, move to next stage
        state.advance_workflow_stage()
        state.next_action = "gather_business_nature"
        return state

    # Use a PydanticOutputParser to get structured output
    parser = PydanticOutputParser(pydantic_object=NextQuestion)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a friendly warehouse assistant collecting location and size requirements.
        
        In this stage, you need to collect:
        - Location (city or state)
        - Size requirements (square footage)
        
        Ask ONE question at a time. Be conversational and helpful.
        Focus on the most important missing requirement first.
        
        {format_instructions}"""),
        ("human", """Here is the conversation history so far:
        ---
        {history}
        ---
        Missing requirements in this stage: {missing}
        
        What should I ask next?""")
    ])
    
    # Format the history for the prompt
    history = "\n".join([f"{msg['role'].title()}: {msg['content']}" for msg in state.messages])
    
    chain = prompt | llm | parser
    
    try:
        next_question_model = await chain.ainvoke({
            "history": history,
            "missing": ", ".join(missing_requirements),
            "format_instructions": parser.get_format_instructions()
        })
        question = next_question_model.question
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to generate question: {e}")
        if "location" in missing_requirements:
            question = "What city or location are you looking for a warehouse in?"
        else:
            question = "How much space do you need? Please specify in square feet."

    state.add_message("assistant", question)
    print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {question}")
    
    state.next_action = "wait_for_user"
    return state

async def business_nature_gatherer_node(state: GraphState) -> GraphState:
    """Stage 2: Ask about industrial land CLU requirement."""
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Stage 2: Asking about industrial land CLU...")
    
    if state.land_type_industrial is not None:
        # Already have land type preference, move to next stage
        state.advance_workflow_stage()
        state.next_action = "gather_specifics"
        return state

    question = ("What land classification do you require?\n\n"
               "• **Industrial CLU**: For manufacturing, processing, chemical operations\n"
               "• **Commercial**: For distribution, storage, retail operations\n\n"
               "Please specify: industrial or commercial")
    
    state.add_message("assistant", question)
    print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {question}")
    
    state.next_action = "wait_for_user"
    return state

async def specifics_gatherer_node(state: GraphState) -> GraphState:
    """Stage 3: Gather specific requirements like compliances, budget, etc."""
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Stage 3: Gathering specific requirements...")
    
    question = ("Additional requirements:\n\n"
               "• Fire NOC compliance\n"
               "• Budget range (₹/sqft)\n"
               "• Structure type (PEB/RCC)\n"
               "• Loading docks\n"
               "• Other specifications\n\n"
               "Please specify your requirements, or type 'none' if not applicable.")
    
    state.add_message("assistant", question)
    print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {question}")
    
    state.next_action = "wait_for_user"
    return state
# ============================ STAGE-SPECIFIC NODES END HERE ============================

# ============================ NEW NODE STARTS HERE ============================
async def chit_chat_node(state: GraphState) -> GraphState:
    """Handles conversational filler and generates a natural response."""
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Generating a chit-chat response...")

    # Get the last user message and the last agent question
    last_user_message = ""
    last_agent_question = ""
    for msg in reversed(state.messages):
        if msg["role"] == "user" and not last_user_message:
            last_user_message = msg["content"]
        if msg["role"] == "assistant" and not last_agent_question:
            last_agent_question = msg["content"]
        if last_user_message and last_agent_question:
            break

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(
            content="You are a friendly, conversational real estate assistant. The user said something that isn't a direct answer to your question. "
                    "Provide a brief, natural-sounding acknowledgement and then gently re-ask your last question to get the conversation back on track."
        ),
        ("ai", f"This was my last question to the user: {last_agent_question}"),
        ("human", f"This was the user's reply: {last_user_message}")
    ])
    
    chain = prompt | llm
    response = await chain.ainvoke({})
    
    response_text = response.content
    state.add_message("assistant", response_text)
    print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {response_text}")

    state.next_action = "wait_for_user"
    return state
# ============================= NEW NODE ENDS HERE =============================

from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser

# (Add these imports at the top of nodes.py)

class NextQuestion(BaseModel):
    """The next question to ask the user to gather missing information."""
    question: str = Field(description="A friendly, natural-sounding question to ask the user.")
    
async def requirements_gatherer_node(state: GraphState) -> GraphState:
    """Node that dynamically generates the next question to ask the user using an LLM."""
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Dynamically generating next question...")
    
    missing_requirements = state.get_missing_requirements()
    
    if not missing_requirements:
        state.next_action = "confirm_requirements"
        return state

    # Use a PydanticOutputParser to get structured output
    parser = PydanticOutputParser(pydantic_object=NextQuestion)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a friendly and highly intelligent real estate assistant. 
        Your goal is to gather a user's requirements for a warehouse. 
        You have the conversation history and a list of requirements you still need to collect.

        Based on this information, formulate the single best question to ask the user next.

        - Be conversational and not robotic.
        - Prioritize gathering the most important information first (location, then size).
        - Do not ask for multiple things at once.
        - Keep your questions brief and to the point.
        
        {format_instructions}"""),
        ("human", """Here is the conversation history so far:
        ---
        {history}
        ---
        Here are the requirements we still need to collect: {missing}
        
        What is the best next question to ask?""")
    ])
    
    # Format the history for the prompt
    history = "\n".join([f"{msg['role'].title()}: {msg['content']}" for msg in state.messages])
    
    chain = prompt | llm | parser
    
    try:
        next_question_model = await chain.ainvoke({
            "history": history,
            "missing": ", ".join(missing_requirements),
            "format_instructions": parser.get_format_instructions()
        })
        question = next_question_model.question
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to generate dynamic question: {e}")
        # Fallback to the simple hardcoded question if the LLM fails
        question = "Sorry, I had a brief issue. What other requirements do you have?"

    state.add_message("assistant", question)
    print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {question}")
    
    state.next_action = "wait_for_user"
    return state

async def update_state_node(state: GraphState) -> GraphState:
    """Node that parses user input and updates the state based on current workflow stage."""
    if not state.messages or state.messages[-1]["role"] != "user":
        # Determine which stage we should go to
        if state.workflow_stage == "area_and_size":
            state.next_action = "gather_area_size"
        elif state.workflow_stage == "land_type_preference":
            state.next_action = "gather_business_nature"
        elif state.workflow_stage == "specifics":
            state.next_action = "gather_specifics"
        return state
    
    user_message = state.messages[-1]["content"]
    user_message_lower = user_message.lower()
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Parsing user input in {state.workflow_stage} stage: '{user_message}'")
    
    # Handle pagination for search results
    if user_message_lower in ["more", "next", "show more"]:
        MAX_PAGES = 10
        if state.current_page >= MAX_PAGES:
            response_message = f"📄 You've reached the maximum number of pages ({MAX_PAGES}). If you'd like to refine your search or try different criteria, just let me know!"
            state.add_message("assistant", response_message)
            print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {response_message}")
            state.next_action = "wait_for_user"
            return state
        
        state.current_page += 1
        state.next_action = "search_database"
        return state
    
    # Handle confirmation for search
    affirmative_keywords = ["yes", "yep", "sure", "correct", "confirm", "looks good", "do it", "start"]
    if any(keyword in user_message_lower for keyword in affirmative_keywords):
        state.requirements_confirmed = True
        state.next_action = "search_database"
        return state

    # Stage-specific parsing
    if state.workflow_stage == "area_and_size":
        await _parse_area_size_requirements(state, user_message)
    elif state.workflow_stage == "land_type_preference":
        await _parse_business_nature(state, user_message)
    elif state.workflow_stage == "specifics":
        await _parse_specific_requirements(state, user_message)
        
        # Only in specifics stage, check for location changes
        location_change_keywords = ["similar warehouses in", "similar in", "show warehouses in", "warehouses in"]
        if any(keyword in user_message_lower for keyword in location_change_keywords):
            # This is a location change request, go directly to search
            state.next_action = "search_database"
            return state
    
    # Handle criteria relaxation requests (when user wants to expand search)
    if any(keyword in user_message_lower for keyword in ["relax", "expand", "loosen", "more options", "size", "budget", "land type", "fire noc"]):
        await _handle_criteria_relaxation(state, user_message)
        # After relaxing criteria, search again
        state.next_action = "search_database"
        return state
    
    # Check if we can advance to next stage
    if state.is_ready_for_next_stage():
        if state.workflow_stage == "area_and_size":
            state.advance_workflow_stage()
            state.next_action = "gather_business_nature"
        elif state.workflow_stage == "land_type_preference":
            state.advance_workflow_stage()
            state.next_action = "gather_specifics"
        elif state.workflow_stage == "specifics":
            # Ready for confirmation
            state.next_action = "confirm_requirements"
    else:
        # Stay in current stage
        if state.workflow_stage == "area_and_size":
            state.next_action = "gather_area_size"
        elif state.workflow_stage == "land_type_preference":
            state.next_action = "gather_business_nature"
        elif state.workflow_stage == "specifics":
            state.next_action = "gather_specifics"
    
    return state

async def _parse_area_size_requirements(state: GraphState, user_message: str):
    """Parse location and size requirements from user message."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Extract location and size requirements from user message. 
        Return ONLY a raw JSON object:
        {{"location_query": null, "size_min": null, "size_max": null}}
        
        Instructions:
        1. For location: extract city/state names
        2. For size: handle ranges, "up to", "at least", single numbers
        3. If user says "all warehouses" or "any size", set size fields to null"""),
        ("user", "Extract requirements: {message}")
    ])
    
    try:
        chain = prompt | llm
        response = await chain.ainvoke({"message": user_message})
        content = response.content.strip()
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        json_str = json_match.group(1) if json_match else content
        parsed_data = json.loads(json_str)
        
        # Update location
        if parsed_data.get("location_query"):
            state.location_query = parsed_data["location_query"]
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated location: {state.location_query}")
        
        # Update size with same logic as before
        parsed_min_val = parsed_data.get("size_min")
        parsed_max_val = parsed_data.get("size_max")
        
        if parsed_min_val is not None or parsed_max_val is not None:
            if parsed_min_val and parsed_max_val:
                size_min, size_max = int(parsed_min_val), int(parsed_max_val)
                if size_min == size_max:
                    single_size = size_min
                    deviation = 0.20
                    state.size_min, state.size_max = int(single_size * (1 - deviation)), int(single_size * (1 + deviation))
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Created flexible size range: {state.size_min} - {state.size_max} sqft")
                else:
                    state.size_min, state.size_max = size_min, size_max
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated size range: {state.size_min} - {state.size_max} sqft")
            elif parsed_min_val:
                state.size_min, state.size_max = int(parsed_min_val), None
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum size: {state.size_min} sqft")
            elif parsed_max_val:
                state.size_min, state.size_max = None, int(parsed_max_val)
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated maximum size: {state.size_max} sqft")
        
        # Handle "all warehouses" phrases
        user_message_lower = user_message.lower()
        all_warehouse_phrases = ["all warehouses", "show all", "any size", "all available"]
        if any(phrase in user_message_lower for phrase in all_warehouse_phrases):
            state.size_min, state.size_max = None, None
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Cleared size restrictions")
            
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse area/size: {e}")

async def _parse_business_nature(state: GraphState, user_message: str):
    """Parse land type preference from user message."""
    user_message_lower = user_message.lower()
    
    # Parse land type preference
    if any(word in user_message_lower for word in ["industrial", "yes", "manufacturing", "processing"]):
        state.land_type_industrial = True
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Land type: Industrial")
    elif any(word in user_message_lower for word in ["commercial", "no", "distribution", "storage"]):
        state.land_type_industrial = False
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Land type: Commercial")
    else:
        # Default to commercial for flexibility
        state.land_type_industrial = False
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Land type: Commercial (default)")

async def _parse_specific_requirements(state: GraphState, user_message: str):
    """Parse specific requirements like fire NOC, budget, etc."""
    user_message_lower = user_message.lower()
    
    # Check for new search requests (location changes) - only if we already have a location
    location_keywords = ["warehouses in", "similar in", "show in", "find in", "search in"]
    if (state.location_query and  # Only if we already have a location
        any(keyword in user_message_lower for keyword in location_keywords)):
        # User wants to search in a different location - parse it
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract location from user message. Return ONLY JSON:
            {"location_query": null}
            Extract city/location name after words like 'in', 'warehouses in', etc."""),
            ("user", "Extract location: {message}")
        ])
        
        try:
            chain = prompt | llm
            response = await chain.ainvoke({"message": user_message})
            content = response.content.strip()
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            json_str = json_match.group(1) if json_match else content
            parsed_data = json.loads(json_str)
            
            if parsed_data.get("location_query"):
                # Reset search parameters for new location
                state.location_query = parsed_data["location_query"]
                state.parsed_cities = None
                state.parsed_state = None
                state.current_page = 1
                state.search_results = None
                state.requirements_confirmed = False
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} New location search: {state.location_query}")
                return
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse location: {e}")
    
    # Handle "none" or similar responses
    if user_message_lower in ["none", "no", "nothing", "no requirements", "that's all"]:
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} User indicated no specific requirements")
        return
    
    # Check for budget (only if user is explicitly mentioning budget/price/rate)
    budget_keywords = ["budget", "price", "rate", "cost", "₹", "rupees", "per sqft", "/sqft"]
    vague_budget_phrases = ["as per market", "market rate", "depends", "flexible", "negotiate"]
    
    # Only try to extract budget if user is actually talking about budget AND not using vague phrases
    if (any(keyword in user_message_lower for keyword in budget_keywords) and 
        not any(phrase in user_message_lower for phrase in vague_budget_phrases)):
        # Try to extract specific budget numbers
        budget_match = re.search(r'₹?(\d+(?:,\d{3})*(?:\.\d+)?)', user_message)
        if budget_match:
            try:
                budget_value = int(budget_match.group(1).replace(',', ''))
                state.budget_max = budget_value
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated budget: ₹{state.budget_max}")
            except ValueError:
                pass
    
    # Check for size updates (when explicitly mentioned)
    size_keywords = ["size", "sqft", "square feet", "area", "space"]
    if any(keyword in user_message_lower for keyword in size_keywords):
        # Parse size requirements using LLM for better accuracy
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Extract size requirements from user message. 
                Return ONLY a raw JSON object:
                {"size_min": null, "size_max": null}
                
                Instructions:
                1. For size: handle ranges, "up to", "at least", single numbers
                2. If user says "any size", set both fields to null
                3. Convert all sizes to square feet"""),
                ("user", "Extract size: {message}")
            ])
            
            chain = prompt | llm
            response = await chain.ainvoke({"message": user_message})
            content = response.content.strip()
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            json_str = json_match.group(1) if json_match else content
            parsed_data = json.loads(json_str)
            
            parsed_min_val = parsed_data.get("size_min")
            parsed_max_val = parsed_data.get("size_max")
            
            if parsed_min_val is not None or parsed_max_val is not None:
                if parsed_min_val and parsed_max_val:
                    state.size_min, state.size_max = int(parsed_min_val), int(parsed_max_val)
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated size range: {state.size_min} - {state.size_max} sqft")
                elif parsed_min_val:
                    state.size_min = int(parsed_min_val)
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum size: {state.size_min} sqft")
                elif parsed_max_val:
                    state.size_max = int(parsed_max_val)
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated maximum size: {state.size_max} sqft")
            elif "any size" in user_message_lower or "all sizes" in user_message_lower:
                state.size_min, state.size_max = None, None
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Cleared size restrictions")
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse size update: {e}")
    
    # Check for location updates (when explicitly mentioned)
    location_keywords = ["location", "city", "place", "area", "region", "move to", "change location"]
    if any(keyword in user_message_lower for keyword in location_keywords):
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Extract location from user message. Return ONLY JSON:
                {"location_query": null}
                Extract city/location name from the message."""),
                ("user", "Extract location: {message}")
            ])
            
            chain = prompt | llm
            response = await chain.ainvoke({"message": user_message})
            content = response.content.strip()
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            json_str = json_match.group(1) if json_match else content
            parsed_data = json.loads(json_str)
            
            if parsed_data.get("location_query"):
                state.location_query = parsed_data["location_query"]
                state.parsed_cities = None
                state.parsed_state = None
                state.current_page = 1
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated location: {state.location_query}")
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse location update: {e}")
    
    # Check for land type changes
    land_type_keywords = ["land type", "industrial", "commercial", "land classification"]
    if any(keyword in user_message_lower for keyword in land_type_keywords):
        if any(word in user_message_lower for word in ["industrial", "manufacturing", "processing"]):
            state.land_type_industrial = True
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated land type: Industrial")
        elif any(word in user_message_lower for word in ["commercial", "distribution", "storage"]):
            state.land_type_industrial = False
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated land type: Commercial")
        elif any(word in user_message_lower for word in ["any", "both", "either"]):
            state.land_type_industrial = None
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated land type: Any")
    
    # Check for fire NOC updates
    fire_keywords = ["fire noc", "fire clearance", "fire compliance", "fire certificate", "noc"]
    if any(keyword in user_message_lower for keyword in fire_keywords):
        if any(word in user_message_lower for word in ["yes", "required", "need", "must have"]):
            state.fire_noc_required = True
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Fire NOC required: True")
        elif any(word in user_message_lower for word in ["no", "not required", "don't need", "optional"]):
            state.fire_noc_required = False
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Fire NOC required: False")
    
    # Check for warehouse type updates
    warehouse_type_keywords = ["warehouse type", "structure", "construction", "peb", "rcc", "shed type"]
    if any(keyword in user_message_lower for keyword in warehouse_type_keywords):
        if "peb" in user_message_lower:
            state.warehouse_type = "PEB"
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated warehouse type: PEB")
        elif "rcc" in user_message_lower:
            state.warehouse_type = "RCC"
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated warehouse type: RCC")
        elif any(word in user_message_lower for word in ["any", "both", "either", "flexible"]):
            state.warehouse_type = None
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated warehouse type: Any")
    
    # Check for loading docks updates
    dock_keywords = ["dock", "loading dock", "loading bay", "loading platform"]
    if any(keyword in user_message_lower for keyword in dock_keywords):
        dock_match = re.search(r'(\d+)\s*(?:dock|loading)', user_message_lower)
        if dock_match:
            state.min_docks = int(dock_match.group(1))
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum docks: {state.min_docks}")
        elif any(word in user_message_lower for word in ["no dock", "without dock", "zero dock"]):
            state.min_docks = 0
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum docks: 0")
    
    # Check for clear height updates
    height_keywords = ["height", "clear height", "ceiling height", "clearance"]
    if any(keyword in user_message_lower for keyword in height_keywords):
        height_match = re.search(r'(\d+)\s*(?:ft|feet|meter|m)', user_message_lower)
        if height_match:
            height_value = int(height_match.group(1))
            # Convert meters to feet if needed
            if 'm' in user_message_lower or 'meter' in user_message_lower:
                height_value = int(height_value * 3.28084)  # Convert meters to feet
            state.min_clear_height = height_value
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum clear height: {state.min_clear_height} ft")

# (confirm_requirements_node, search_database_node, and human_input_node remain the same as before)
async def confirm_requirements_node(state: GraphState) -> GraphState:
    """Confirm all requirements with the user before searching."""
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Confirming requirements...")
    summary_parts = []
    
    if state.location_query:
        summary_parts.append(f"📍 Location: **{state.location_query}**")
    if state.size_min is not None or state.size_max is not None:
        size_range = f"**{state.size_min if state.size_min is not None else '0'} - {state.size_max if state.size_max is not None else 'any'} sqft**"
        summary_parts.append(f"📦 Size: {size_range}")
    if state.budget_max:
        summary_parts.append(f"💰 Budget: up to **₹{state.budget_max}/sqft**")
    if state.warehouse_type:
        summary_parts.append(f"🏗️ Type: **{state.warehouse_type}**")
    
    # Add fire NOC and land type requirements to the summary
    if state.fire_noc_required:
        summary_parts.append(f"🔥 Fire NOC: **Required**")
    if state.land_type_industrial is not None:
        land_type_text = "Industrial" if state.land_type_industrial else "Commercial/Flexible"
        summary_parts.append(f"🏭 Land Type: **{land_type_text}**")
    
    confirmation_message = (
        "Requirements summary:\n\n" + 
        "\n".join(summary_parts) + 
        "\n\nProceed with search? (yes/no)"
    )
    state.add_message("assistant", confirmation_message)
    print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {confirmation_message}")
    state.next_action = "wait_for_user"
    return state

async def search_database_node(state: GraphState) -> GraphState:
    # ... (no changes needed)
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
        "zone": state.zone, "is_broker": state.is_broker, "page": state.current_page,
        "fire_noc_required": state.fire_noc_required, "land_type_industrial": state.land_type_industrial
    }
    search_params = {k: v for k, v in search_params.items() if v is not None}
    try:
        print(f"{Fore.YELLOW}[TOOL]{Style.RESET_ALL} Searching with params: {search_params}")
        search_results = await find_warehouses_in_db.ainvoke(search_params)
        print(f"{Fore.YELLOW}[TOOL RESULT]{Style.RESET_ALL} Found results")
        state.search_results = search_results
        # Check if no results were found
        if "NO_RESULTS_FOUND:" in str(search_results) or "No warehouses found" in str(search_results) or "No more warehouses" in str(search_results):
            if state.current_page == 1:
                response_message = f"🔍 No warehouses match your criteria. Would you like to modify your search parameters?"
            else:
                response_message = f"📄 End of results. {state.current_page-1} pages viewed. Modify search criteria?"
        else:
            response_message = f"Search results - Page {state.current_page}:\n\n{search_results}"
            
            # Count the number of results to determine next actions
            result_count = search_results.count("ID:")
            
            if result_count >= 5:  # Full page, likely more results available
                response_message += "\n\n💡 Type **'more'** for additional results."
            elif result_count > 0 and result_count < 5 and state.current_page == 1:
                # Limited results on first page - offer to relax criteria
                response_message += f"\n\n🔍 Found {result_count} result{'s' if result_count != 1 else ''}. Would you like to relax any criteria to find more options?\n\n"
                
                # Suggest specific relaxations based on current criteria
                relaxation_options = []
                if state.size_min and state.size_max:
                    relaxation_options.append("📦 **Size range** (currently {}-{} sqft)".format(state.size_min, state.size_max))
                if state.land_type_industrial is not None:
                    land_type = "Industrial" if state.land_type_industrial else "Commercial"
                    relaxation_options.append(f"🏭 **Land type** (currently {land_type})")
                if state.budget_max:
                    relaxation_options.append(f"💰 **Budget** (currently up to ₹{state.budget_max}/sqft)")
                if state.fire_noc_required:
                    relaxation_options.append("🔥 **Fire NOC requirement**")
                if state.warehouse_type:
                    relaxation_options.append(f"🏗️ **Warehouse type** (currently {state.warehouse_type})")
                
                if relaxation_options:
                    response_message += "Options to relax:\n" + "\n".join(relaxation_options)
                    response_message += "\n\nType which criteria to relax (e.g., 'size', 'land type', 'budget') or 'none' to keep current results."
                else:
                    response_message += "Type 'search in nearby areas' to expand location, or 'none' to keep current results."
            # If fewer than 5 results on subsequent pages, don't show "more" (this is the end)
        state.add_message("assistant", response_message)
        print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {response_message}")
    except Exception as e:
        error_message = f"😬 Uh oh, I hit a snag while searching. Here's the technical error: {str(e)}"
        state.add_message("assistant", error_message)
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {error_message}")
    state.next_action = "wait_for_user"
    return state

async def _handle_criteria_relaxation(state: GraphState, user_message: str):
    """Handle user requests to relax search criteria for more results."""
    user_message_lower = user_message.lower()
    
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Handling criteria relaxation: {user_message}")
    
    # Size relaxation
    if any(keyword in user_message_lower for keyword in ["size", "sqft", "square feet", "bigger", "smaller"]):
        if state.size_min and state.size_max:
            # Expand size range by 30%
            current_range = state.size_max - state.size_min
            expansion = int(current_range * 0.3)
            state.size_min = max(0, state.size_min - expansion)
            state.size_max = state.size_max + expansion
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Relaxed size range to: {state.size_min} - {state.size_max} sqft")
        elif state.size_min:
            # Reduce minimum by 30%
            state.size_min = int(state.size_min * 0.7)
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Reduced minimum size to: {state.size_min} sqft")
        elif state.size_max:
            # Increase maximum by 50%
            state.size_max = int(state.size_max * 1.5)
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Increased maximum size to: {state.size_max} sqft")
    
    # Land type relaxation
    elif any(keyword in user_message_lower for keyword in ["land type", "land", "industrial", "commercial"]):
        if state.land_type_industrial is not None:
            state.land_type_industrial = None  # Accept both industrial and commercial
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Relaxed land type to accept both Industrial and Commercial")
    
    # Budget relaxation
    elif any(keyword in user_message_lower for keyword in ["budget", "price", "rate", "cost", "cheaper", "expensive"]):
        if state.budget_max:
            # Increase budget by 20%
            state.budget_max = int(state.budget_max * 1.2)
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Increased budget to: ₹{state.budget_max}/sqft")
        else:
            # If no budget set, don't add one (keep it flexible)
            pass
    
    # Fire NOC relaxation
    elif any(keyword in user_message_lower for keyword in ["fire noc", "fire", "noc", "compliance"]):
        if state.fire_noc_required:
            state.fire_noc_required = False
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Relaxed Fire NOC requirement")
    
    # Warehouse type relaxation
    elif any(keyword in user_message_lower for keyword in ["type", "structure", "peb", "rcc", "shed"]):
        if state.warehouse_type:
            state.warehouse_type = None  # Accept all warehouse types
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Relaxed warehouse type to accept all types")
    
    # General relaxation - relax the most restrictive criteria
    elif any(keyword in user_message_lower for keyword in ["all", "everything", "any", "general", "loosen"]):
        relaxed_something = False
        
        # Relax land type first (common restriction)
        if state.land_type_industrial is not None:
            state.land_type_industrial = None
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Relaxed land type to accept both")
            relaxed_something = True
        
        # Then relax fire NOC if set
        elif state.fire_noc_required:
            state.fire_noc_required = False
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Relaxed Fire NOC requirement")
            relaxed_something = True
        
        # Then expand size range if very specific
        elif state.size_min and state.size_max and (state.size_max - state.size_min) < 10000:
            expansion = int((state.size_max - state.size_min) * 0.5)
            state.size_min = max(0, state.size_min - expansion)
            state.size_max = state.size_max + expansion
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Expanded size range to: {state.size_min} - {state.size_max} sqft")
            relaxed_something = True
        
        if not relaxed_something:
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} No specific criteria to relax")

async def human_input_node(state: GraphState) -> GraphState:
    """Human input node - for API mode, just return state for user to provide input"""
    # In API mode, we don't wait for CLI input
    # The API will handle user input separately and invoke the graph again
    # Just mark that we're waiting for user input and end the workflow
    state.next_action = "wait_for_user"
    return state