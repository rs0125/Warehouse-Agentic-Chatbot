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
        "Hi! Let's find the right spot for your business. To begin, where are you looking for a warehouse?"
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
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Current state - Location: {state.location_query}, Size: {state.size_min}-{state.size_max}")
    
    missing_requirements = state.get_missing_requirements()
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Missing requirements: {missing_requirements}")
    
    if not missing_requirements:
        # Both location and size are collected, move to next stage
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} All requirements collected, advancing to business nature stage")
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
    
    # Handle confirmation for search - ONLY when we're waiting for confirmation
    affirmative_keywords = ["yes", "yep", "sure", "correct", "confirm", "looks good", "do it", "start"]
    has_affirmative = any(keyword in user_message_lower for keyword in affirmative_keywords)
    
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Confirmation check - Has affirmative: {has_affirmative}, Stage: {state.workflow_stage}, Requirements confirmed: {state.requirements_confirmed}")
    
    if (has_affirmative and 
        state.workflow_stage == "specifics" and 
        state.requirements_confirmed == False):
        # Check if any recent assistant message was a requirements summary (contains "Proceed with search?")
        # We need to look back at least 2 messages since the current flow is:
        # 1. Assistant asks "Proceed with search?"
        # 2. User responds "yes" 
        # 3. We're now processing the "yes"
        found_confirmation_message = False
        
        # Debug: Show recent messages
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Recent messages in state:")
        for i, msg in enumerate(reversed(state.messages[-5:])):
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL}   {4-i}: {msg['role']}: {msg['content'][:100]}...")
            if msg["role"] == "assistant" and ("Are these parameters fine?" in msg["content"] or "Proceed with search?" in msg["content"]):
                found_confirmation_message = True
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Found confirmation message in recent history")
        
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Checking confirmation - Found confirmation message in recent messages: {found_confirmation_message}")
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Current requirements_confirmed: {state.requirements_confirmed}")
        
        if found_confirmation_message:
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Confirming search and proceeding to database search")
            state.requirements_confirmed = True
            state.next_action = "search_database"
            return state
        else:
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Not a search confirmation context")
    
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
    
    # Handle confirmation for search - ONLY at the final confirmation step
    # This will be handled by the confirm_requirements_node instead
    
    # Check for parameter updates at ANY stage (global check) - must come before location changes
    # Only trigger for explicit update commands, not normal workflow responses
    parameter_update_keywords = ["make budget", "change budget", "set budget", "new budget", 
                                "make size", "change size", "set size", "new size",
                                "update budget", "update size"]
    explicit_change_keywords = ["make", "change", "set", "update", "new"]
    
    # Check if this is an explicit parameter update (not normal workflow response)
    has_explicit_change = any(keyword in user_message_lower for keyword in explicit_change_keywords)
    has_parameter = any(keyword in user_message_lower for keyword in ["budget", "size", "price", "rate", "cost", "sqft"])
    is_location_change = any(keyword in user_message_lower for keyword in ["make city", "change city", "switch to", "move to"])
    
    if (has_explicit_change and has_parameter and not is_location_change and 
        state.workflow_stage == "specifics"):  # Only in specifics stage for parameter updates
        # Parse parameter updates 
        await _parse_specific_requirements(state, user_message)
        # Show updated requirements summary
        await _show_updated_requirements(state)
        # Wait for user confirmation (next_action set by _show_updated_requirements)
        return state

    # Check for location changes only AFTER the initial stages (not during area_and_size stage)
    if state.workflow_stage != "area_and_size":
        location_change_keywords = ["switch to", "change to", "make city", "change city", "move to", 
                                   "find in", "search in", "show in", "warehouses in", "similar in",
                                   "update location", "new location"]
        if any(keyword in user_message_lower for keyword in location_change_keywords):
            # Parse the new location
            await _parse_location_change(state, user_message)
            # Go directly to search with new location
            state.next_action = "search_database"
            return state

    # Stage-specific parsing
    if state.workflow_stage == "area_and_size":
        await _parse_area_size_requirements(state, user_message)
    elif state.workflow_stage == "land_type_preference":
        await _parse_business_nature(state, user_message)
    elif state.workflow_stage == "specifics":
        await _parse_specific_requirements(state, user_message)
    
    # Handle criteria relaxation requests (when user wants to expand search) - more specific keywords
    relaxation_keywords = ["relax", "expand", "loosen", "more options"]
    if any(keyword in user_message_lower for keyword in relaxation_keywords):
        await _handle_criteria_relaxation(state, user_message)
        # After relaxing criteria, search again
        state.next_action = "search_database"
        return state
    
    # Check if we can advance to next stage
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Checking if ready for next stage. Current stage: {state.workflow_stage}")
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Location: {state.location_query}, Size: {state.size_min}-{state.size_max}")
    
    is_ready = state.is_ready_for_next_stage()
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Is ready for next stage: {is_ready}")
    
    if is_ready:
        if state.workflow_stage == "area_and_size":
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Advancing from area_and_size to land_type_preference")
            state.advance_workflow_stage()
            state.next_action = "gather_business_nature"
        elif state.workflow_stage == "land_type_preference":
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Advancing from land_type_preference to specifics")
            state.advance_workflow_stage()
            state.next_action = "gather_specifics"
        elif state.workflow_stage == "specifics":
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Moving to confirmation")
            # Ready for confirmation - but only if not already confirmed and not already set to search
            if not state.requirements_confirmed and state.next_action != "search_database":
                state.next_action = "confirm_requirements"
            elif state.requirements_confirmed or state.next_action == "search_database":
                # Already confirmed or already set to search, should search
                state.next_action = "search_database"
    else:
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Not ready, staying in current stage")
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
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Parsing area/size from: '{user_message}'")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Extract location and size requirements from user message. 
        Return ONLY a raw JSON object:
        {{"location_query": null, "size_min": null, "size_max": null}}
        
        Instructions:
        1. For location: extract city/state names
        2. For size: handle ranges, "up to", "at least", single numbers, "k" abbreviations (50k = 50000)
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
        
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Parsed data: {parsed_data}")
        
        # Update location
        if parsed_data.get("location_query"):
            state.location_query = parsed_data["location_query"]
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated location: {state.location_query}")
            # Clear parsed cities so it gets re-processed through location tool
            state.parsed_cities = None
            state.parsed_state = None
        
        # Update size with same logic as before
        parsed_min_val = parsed_data.get("size_min")
        parsed_max_val = parsed_data.get("size_max")
        
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Size values - min: {parsed_min_val}, max: {parsed_max_val}")
        
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
    
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Parsing specific requirements from: '{user_message}'")
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Budget before parsing - min: {state.budget_min}, max: {state.budget_max}")
    
    # Handle "none" or similar responses first
    if user_message_lower in ["none", "no", "nothing", "no requirements", "that's all"]:
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} User indicated no specific requirements")
        return
    
    # Handle simple confirmations that should NOT trigger requirement parsing
    simple_confirmations = ["yes", "yep", "sure", "correct", "ok", "okay"]
    if user_message_lower in simple_confirmations:
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Simple confirmation detected, skipping requirement parsing")
        return
    location_keywords = ["warehouses in", "similar in", "show in", "find in", "search in"]
    if (state.location_query and  # Only if we already have a location
        any(keyword in user_message_lower for keyword in location_keywords)):
        # User wants to search in a different location - parse it
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract location from user message. Return ONLY JSON:
            {{"location_query": null}}
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
    
    # Enhanced budget parsing (only if user is explicitly mentioning budget/price/rate)
    budget_keywords = ["budget", "price", "rate", "cost", "₹", "rupees", "per sqft", "/sqft", 
                       "rent", "rental", "lease rate", "monthly rent", "pricing", "charges",
                       "expense", "fees", "payment", "amount", "money", "financial", "affordable"]
    vague_budget_phrases = ["as per market", "market rate", "depends", "flexible", "negotiate",
                           "reasonable", "fair price", "market price", "standard rate", 
                           "competitive", "discuss", "talk about price", "let's see", "open to negotiate"]
    
    # Only try to extract budget if user is actually talking about budget AND not using vague phrases
    if (any(keyword in user_message_lower for keyword in budget_keywords) and 
        not any(phrase in user_message_lower for phrase in vague_budget_phrases)):
        
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Extract budget requirements from user message. 
                Return ONLY a raw JSON object:
                {{"budget_min": null, "budget_max": null}}
                
                Instructions:
                1. Handle ranges: "₹20-50 per sqft", "between ₹30 and ₹60", "20 to 30", "budget 15-25"
                2. Handle max only: "up to ₹40", "maximum ₹35", "not more than 50", "under ₹30"
                3. Handle min only: "at least ₹25", "minimum ₹20", "above ₹15", "starting from 30"
                4. Handle single numbers: "₹35 per sqft", "budget 50", "rate 40" → treat as budget_max
                5. Extract only numbers, remove currency symbols and units
                6. Handle "k" notation: "25k" = 25000, but for rent usually means 25 per sqft
                7. Clear budget: "any budget", "flexible budget", "no budget limit", "open budget"
                8. Complex patterns: "make budget 20 to 30", "set rate between 15-25", "price range 30-45"
                
                Examples:
                - "budget ₹20-50 per sqft" → {{"budget_min": 20, "budget_max": 50}}
                - "up to ₹40 rent" → {{"budget_min": null, "budget_max": 40}}
                - "at least ₹25 per sqft" → {{"budget_min": 25, "budget_max": null}}
                - "₹35 per sqft" → {{"budget_min": null, "budget_max": 35}}
                - "flexible budget" → {{"budget_min": null, "budget_max": null}}"""),
                ("user", "Extract budget: {message}")
            ])
            
            chain = prompt | llm
            response = await chain.ainvoke({"message": user_message})
            content = response.content.strip()
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            json_str = json_match.group(1) if json_match else content
            parsed_data = json.loads(json_str)
            
            parsed_min_budget = parsed_data.get("budget_min")
            parsed_max_budget = parsed_data.get("budget_max")
            
            if parsed_min_budget is not None or parsed_max_budget is not None:
                if parsed_min_budget and parsed_max_budget:
                    state.budget_min, state.budget_max = int(parsed_min_budget), int(parsed_max_budget)
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated budget range: ₹{state.budget_min} - ₹{state.budget_max}/sqft")
                elif parsed_min_budget:
                    state.budget_min = int(parsed_min_budget)
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum budget: ₹{state.budget_min}/sqft")
                elif parsed_max_budget:
                    state.budget_max = int(parsed_max_budget)
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated maximum budget: ₹{state.budget_max}/sqft")
            elif "any budget" in user_message_lower or "flexible" in user_message_lower:
                state.budget_min, state.budget_max = None, None
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Cleared budget restrictions")
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse budget: {e}")
            # Fallback to regex extraction for simple patterns
            # Look for patterns like "50 to 60", "20-30", "budget 25 to 40"
            range_match = re.search(r'(\d+)\s*(?:to|-)\s*(\d+)', user_message)
            if range_match:
                try:
                    min_val, max_val = int(range_match.group(1)), int(range_match.group(2))
                    state.budget_min, state.budget_max = min_val, max_val
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated budget range (fallback): ₹{state.budget_min} - ₹{state.budget_max}/sqft")
                except ValueError:
                    pass
            else:
                # Single number fallback
                budget_match = re.search(r'₹?(\d+(?:,\d{3})*(?:\.\d+)?)', user_message)
                if budget_match:
                    try:
                        budget_value = int(budget_match.group(1).replace(',', ''))
                        state.budget_max = budget_value
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated budget (fallback): ₹{state.budget_max}/sqft")
                    except ValueError:
                        pass
    
    # Parse other warehouse requirements using LLM
    await _parse_warehouse_specifications(state, user_message)
    
    # Legacy keyword-based parsing (keeping as fallback)
    await _parse_legacy_requirements(state, user_message)

async def _parse_warehouse_specifications(state: GraphState, user_message: str):
    """Parse warehouse specifications like docks, height, type using LLM."""
    user_message_lower = user_message.lower()
    
    # Check if message contains specification keywords
    spec_keywords = ["dock", "height", "warehouse type", "structure", "peb", "rcc", "compliance", 
                     "availability", "zone", "broker", "loading", "clear height", "ceiling"]
    
    if not any(keyword in user_message_lower for keyword in spec_keywords):
        return
    
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract warehouse specifications from user message. 
            Return ONLY a raw JSON object:
            {{
                "warehouse_type": null,
                "min_docks": null,
                "min_clear_height": null,
                "compliances_query": null,
                "fire_noc_required": null,
                "availability": null,
                "zone": null,
                "is_broker": null
            }}
            
            Instructions:
            1. warehouse_type: Extract "PEB", "RCC", or null for any/flexible
               - PEB: pre-engineered, steel structure, metal building
               - RCC: concrete, cement, reinforced concrete, brick
               - null: any, both, either, flexible, doesn't matter
            
            2. min_docks: Extract minimum number of loading docks (integer)
               - Handle: "5 docks", "at least 3 loading bays", "minimum 2 platforms"
               - 0 for: "no dock", "without dock", "zero dock"
            
            3. min_clear_height: Extract minimum clear height in feet (convert meters to feet if needed)
               - Handle: "20 feet", "6 meters", "minimum 15 ft height"
               - Convert: 1 meter = 3.28 feet
            
            4. compliances_query: Extract compliance requirements (NOT fire-related)
               - Examples: "environmental", "safety", "OSHA", "pollution control"
            
            5. fire_noc_required: true if fire NOC/compliance mentioned, false if explicitly not wanted
               - true: "fire NOC", "fire compliance", "make it have fire NOC", "fire safety required"
               - false: "no fire NOC", "without fire compliance", "skip fire requirements"
            
            6. availability: Extract availability needs
               - Examples: "immediate", "within 30 days", "ASAP", "urgent", "next month"
            
            7. zone: Extract zone preferences  
               - Examples: "industrial zone", "SEZ", "special economic zone", "IT park"
            
            8. is_broker: true if user wants broker properties, false if owner properties
               - true: "broker properties", "through agent", "via broker"
               - false: "owner properties", "direct owner", "no broker", "without agent"
            
            Examples:
            - "PEB structure with 5 docks and 20 feet height" → {{"warehouse_type": "PEB", "min_docks": 5, "min_clear_height": 20}}
            - "fire NOC required, immediate availability" → {{"fire_noc_required": true, "availability": "immediate"}}
            - "concrete building, no fire compliance needed" → {{"warehouse_type": "RCC", "fire_noc_required": false}}
            - "make it have fire NOC, 3 loading bays" → {{"fire_noc_required": true, "min_docks": 3}}
            - "owner properties only, industrial zone" → {{"is_broker": false, "zone": "industrial zone"}}"""),
            ("user", "Extract specifications: {message}")
        ])
        
        chain = prompt | llm
        response = await chain.ainvoke({"message": user_message})
        content = response.content.strip()
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        json_str = json_match.group(1) if json_match else content
        parsed_data = json.loads(json_str)
        
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Parsed specifications: {parsed_data}")
        
        # Update state with parsed values
        if parsed_data.get("warehouse_type"):
            state.warehouse_type = parsed_data["warehouse_type"]
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated warehouse type: {state.warehouse_type}")
        
        if parsed_data.get("min_docks") is not None:
            state.min_docks = int(parsed_data["min_docks"])
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum docks: {state.min_docks}")
        
        if parsed_data.get("min_clear_height") is not None:
            state.min_clear_height = int(parsed_data["min_clear_height"])
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum clear height: {state.min_clear_height} ft")
        
        if parsed_data.get("compliances_query"):
            state.compliances_query = parsed_data["compliances_query"]
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated compliances: {state.compliances_query}")
            # If fire compliance is mentioned, set the fire NOC flag
            if "fire" in state.compliances_query.lower():
                state.fire_noc_required = True
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Fire NOC required: True (from compliance)")
        
        if parsed_data.get("fire_noc_required") is not None:
            state.fire_noc_required = parsed_data["fire_noc_required"]
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Fire NOC required: {state.fire_noc_required} (from direct parsing)")
        
        if parsed_data.get("availability"):
            state.availability = parsed_data["availability"]
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated availability: {state.availability}")
        
        if parsed_data.get("zone"):
            state.zone = parsed_data["zone"]
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated zone: {state.zone}")
        
        if parsed_data.get("is_broker") is not None:
            state.is_broker = parsed_data["is_broker"]
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated broker preference: {state.is_broker}")
            
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse specifications: {e}")

async def _parse_legacy_requirements(state: GraphState, user_message: str):
    """Legacy keyword-based parsing for backward compatibility."""
    user_message_lower = user_message.lower()
    
    # Check for size updates (when explicitly mentioned)
    size_keywords = ["size", "sqft", "square feet", "area", "space"]
    if any(keyword in user_message_lower for keyword in size_keywords):
        # Parse size requirements using LLM for better accuracy
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Extract size requirements from user message. 
                Return ONLY a raw JSON object:
                {{"size_min": null, "size_max": null}}
                
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
                    # Check if it's actually a single value (min == max)
                    if parsed_min_val == parsed_max_val:
                        # Single value - create ±10% range
                        single_value = int(parsed_min_val)
                        range_deviation = 0.10  # 10%
                        state.size_min = int(single_value * (1 - range_deviation))
                        state.size_max = int(single_value * (1 + range_deviation))
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Single value {single_value} sqft converted to range: {state.size_min} - {state.size_max} sqft (±10%)")
                    else:
                        # Actual range provided
                        state.size_min, state.size_max = int(parsed_min_val), int(parsed_max_val)
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated size range: {state.size_min} - {state.size_max} sqft")
                elif parsed_min_val:
                    # Only minimum provided - could be single value or minimum
                    single_value = int(parsed_min_val)
                    # Check if user said "at least" or similar, otherwise treat as single value
                    if any(phrase in user_message_lower for phrase in ["at least", "minimum", "min", "above", "more than"]):
                        state.size_min = single_value
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum size: {state.size_min} sqft")
                    else:
                        # Treat as single value - create ±10% range
                        range_deviation = 0.10  # 10%
                        state.size_min = int(single_value * (1 - range_deviation))
                        state.size_max = int(single_value * (1 + range_deviation))
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Single value {single_value} sqft converted to range: {state.size_min} - {state.size_max} sqft (±10%)")
                elif parsed_max_val:
                    # Only maximum provided - could be single value or maximum
                    single_value = int(parsed_max_val)
                    # Check if user said "up to" or similar, otherwise treat as single value
                    if any(phrase in user_message_lower for phrase in ["up to", "maximum", "max", "below", "less than", "under"]):
                        state.size_max = single_value
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated maximum size: {state.size_max} sqft")
                    else:
                        # Treat as single value - create ±10% range
                        range_deviation = 0.10  # 10%
                        state.size_min = int(single_value * (1 - range_deviation))
                        state.size_max = int(single_value * (1 + range_deviation))
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Single value {single_value} sqft converted to range: {state.size_min} - {state.size_max} sqft (±10%)")
            elif "any size" in user_message_lower or "all sizes" in user_message_lower:
                state.size_min, state.size_max = None, None
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Cleared size restrictions")
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse size update: {e}")
    
    # Check for location updates (when explicitly mentioned)
    location_keywords = ["location", "city", "place", "area", "region", "move to", "change location", 
                        "make city", "change city", "switch to", "find in", "search in", "show in",
                        "warehouses in", "change to", "update location", "new location"]
    if any(keyword in user_message_lower for keyword in location_keywords):
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Extract location from user message. Return ONLY JSON:
                {{"location_query": null}}
                Extract city/location name from the message. Look for city names after words like 'city', 'in', 'to', etc."""),
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
                state.search_results = None
                state.requirements_confirmed = False
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
    
async def _parse_legacy_requirements(state: GraphState, user_message: str):
    """Legacy keyword-based parsing for backward compatibility - only when LLM parsing misses things."""
    user_message_lower = user_message.lower()
    
    # Check for size updates (when explicitly mentioned)
    size_keywords = ["size", "sqft", "square feet", "area", "space"]
    if any(keyword in user_message_lower for keyword in size_keywords):
        # Parse size requirements using LLM for better accuracy
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Extract size requirements from user message. 
                Return ONLY a raw JSON object:
                {{"size_min": null, "size_max": null}}
                
                Instructions:
                1. For size: handle ranges, "up to", "at least", single numbers
                2. If user says "any size", set both fields to null
                3. Convert all sizes to square feet
                4. Handle "k" notation: "10k" = 10000"""),
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
                    # Check if it's actually a single value (min == max)
                    if parsed_min_val == parsed_max_val:
                        # Single value - create ±20% range
                        single_value = int(parsed_min_val)
                        range_deviation = 0.20  # 20%
                        state.size_min = int(single_value * (1 - range_deviation))
                        state.size_max = int(single_value * (1 + range_deviation))
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Single value {single_value} sqft converted to range: {state.size_min} - {state.size_max} sqft (±20%)")
                    else:
                        # Actual range provided
                        state.size_min, state.size_max = int(parsed_min_val), int(parsed_max_val)
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated size range: {state.size_min} - {state.size_max} sqft")
                elif parsed_min_val:
                    # Only minimum provided - could be single value or minimum
                    single_value = int(parsed_min_val)
                    # Check if user said "at least" or similar, otherwise treat as single value
                    if any(phrase in user_message_lower for phrase in ["at least", "minimum", "min", "above", "more than"]):
                        state.size_min = single_value
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum size: {state.size_min} sqft")
                    else:
                        # Treat as single value - create ±20% range
                        range_deviation = 0.20  # 20%
                        state.size_min = int(single_value * (1 - range_deviation))
                        state.size_max = int(single_value * (1 + range_deviation))
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Single value {single_value} sqft converted to range: {state.size_min} - {state.size_max} sqft (±20%)")
                elif parsed_max_val:
                    # Only maximum provided - could be single value or maximum
                    single_value = int(parsed_max_val)
                    # Check if user said "up to" or similar, otherwise treat as single value
                    if any(phrase in user_message_lower for phrase in ["up to", "maximum", "max", "below", "less than", "under"]):
                        state.size_max = single_value
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated maximum size: {state.size_max} sqft")
                    else:
                        # Treat as single value - create ±20% range
                        range_deviation = 0.20  # 20%
                        state.size_min = int(single_value * (1 - range_deviation))
                        state.size_max = int(single_value * (1 + range_deviation))
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Single value {single_value} sqft converted to range: {state.size_min} - {state.size_max} sqft (±20%)")
            elif "any size" in user_message_lower or "flexible" in user_message_lower:
                state.size_min, state.size_max = None, None
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Cleared size restrictions")
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse size: {e}")
    
    # Enhanced Fire NOC parsing (only if not already set by LLM)
    if state.fire_noc_required is None:  # Only if LLM didn't set it
        fire_keywords = ["fire noc", "fire clearance", "fire compliance", "fire certificate", "noc", 
                         "fire safety", "fire approval", "fire permit", "fire license"]
        if any(keyword in user_message_lower for keyword in fire_keywords):
            positive_indicators = ["yes", "required", "need", "must have", "want", "should have", 
                                  "make it have", "add", "include", "with", "ensure", "necessary",
                                  "mandatory", "compulsory", "essential", "needed", "requires", 
                                  "please add", "make sure", "prefer", "looking for", "seeking"]
            negative_indicators = ["no", "not required", "don't need", "optional", "without", 
                                  "remove", "exclude", "don't want", "skip", "ignore", "avoid",
                                  "not necessary", "no need", "not interested", "doesn't matter"]
            
            if any(word in user_message_lower for word in positive_indicators):
                state.fire_noc_required = True
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Fire NOC required: True (legacy fallback)")
            elif any(word in user_message_lower for word in negative_indicators):
                state.fire_noc_required = False
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Fire NOC required: False (legacy fallback)")
    
    # Enhanced Warehouse type parsing (only if not already set by LLM)
    if state.warehouse_type is None:  # Only if LLM didn't set it
        warehouse_type_keywords = ["warehouse type", "structure", "construction", "peb", "rcc", "shed type",
                                   "building type", "structure type", "construction type", "material"]
        if any(keyword in user_message_lower for keyword in warehouse_type_keywords):
            peb_indicators = ["peb", "pre-engineered", "pre engineered", "steel structure", "metal building"]
            rcc_indicators = ["rcc", "concrete", "cement", "reinforced concrete", "brick", "solid construction"]
            flexible_indicators = ["any", "both", "either", "flexible", "doesn't matter", "open to both", 
                                  "not particular", "whatever", "any type", "no preference"]
            
            if any(word in user_message_lower for word in peb_indicators):
                state.warehouse_type = "PEB"
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated warehouse type: PEB (legacy fallback)")
            elif any(word in user_message_lower for word in rcc_indicators):
                state.warehouse_type = "RCC"
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated warehouse type: RCC (legacy fallback)")
            elif any(word in user_message_lower for word in flexible_indicators):
                state.warehouse_type = None
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated warehouse type: Any (legacy fallback)")
    
    # Enhanced Loading docks parsing (only if not already set by LLM)
    if state.min_docks is None:  # Only if LLM didn't set it
        dock_keywords = ["dock", "loading dock", "loading bay", "loading platform", "docks", "loading bays",
                         "truck dock", "vehicle loading", "loading area", "loading zone", "bay", "platform"]
        if any(keyword in user_message_lower for keyword in dock_keywords):
            dock_match = re.search(r'(\d+)\s*(?:dock|loading|bay|platform)', user_message_lower)
            if dock_match:
                state.min_docks = int(dock_match.group(1))
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum docks: {state.min_docks} (legacy fallback)")
            else:
                # Enhanced negative indicators for docks
                no_dock_indicators = ["no dock", "without dock", "zero dock", "0 dock", "no loading dock",
                                     "no bays", "without loading", "no platform", "don't need dock",
                                     "no loading bay", "skip dock", "avoid dock"]
                if any(phrase in user_message_lower for phrase in no_dock_indicators):
                    state.min_docks = 0
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum docks: 0 (legacy fallback)")
    
    # Enhanced Clear height parsing (only if not already set by LLM)
    if state.min_clear_height is None:  # Only if LLM didn't set it
        height_keywords = ["height", "clear height", "ceiling height", "clearance", "headroom", 
                           "vertical clearance", "roof height", "minimum height", "overhead clearance"]
        if any(keyword in user_message_lower for keyword in height_keywords):
            # Enhanced regex to catch more patterns
            height_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|meter|metres|meters|m)\b', user_message_lower)
            if height_match:
                height_value = float(height_match.group(1))
                # Convert meters to feet if needed
                if 'm' in user_message_lower or 'meter' in user_message_lower:
                    height_value = height_value * 3.28084  # Convert meters to feet
                state.min_clear_height = int(height_value)
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated minimum clear height: {state.min_clear_height} ft (legacy fallback)")
    
    # Enhanced Land type parsing (only if not already set by LLM or previous logic)
    if state.land_type_industrial is None:  # Only if not already set
        land_type_keywords = ["land type", "land classification", "zoning", "industrial land", "commercial land",
                              "industrial zone", "commercial zone", "land use", "property type"]
        if any(keyword in user_message_lower for keyword in land_type_keywords):
            industrial_indicators = ["industrial", "manufacturing", "production", "factory", "industry",
                                    "industrial zone", "industrial area", "manufacturing zone"]
            commercial_indicators = ["commercial", "distribution", "storage", "warehouse", "logistics",
                                    "commercial zone", "distribution center", "storage facility"]
            flexible_indicators = ["any", "both", "either", "flexible", "doesn't matter", "open to both",
                                  "not particular", "whatever", "any type", "no preference"]
            
            if any(word in user_message_lower for word in industrial_indicators):
                state.land_type_industrial = True
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated land type: Industrial (legacy fallback)")
            elif any(word in user_message_lower for word in commercial_indicators):
                state.land_type_industrial = False
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated land type: Commercial (legacy fallback)")
            elif any(word in user_message_lower for word in flexible_indicators):
                state.land_type_industrial = None
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated land type: Any (legacy fallback)")

# (confirm_requirements_node, search_database_node, and human_input_node remain the same as before)
async def confirm_requirements_node(state: GraphState) -> GraphState:
    """Confirm all requirements with the user before searching."""
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Confirming requirements...")
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Budget state - min: {state.budget_min}, max: {state.budget_max}")
    summary_parts = []
    
    if state.location_query:
        summary_parts.append(f"📍 Location: **{state.location_query}**")
    if state.size_min is not None or state.size_max is not None:
        size_range = f"**{state.size_min if state.size_min is not None else '0'} - {state.size_max if state.size_max is not None else 'any'} sqft**"
        summary_parts.append(f"📦 Size: {size_range}")
    
    # Handle budget range display
    if state.budget_min is not None or state.budget_max is not None:
        if state.budget_min and state.budget_max:
            budget_range = f"**₹{state.budget_min} - ₹{state.budget_max}/sqft**"
            summary_parts.append(f"💰 Budget: {budget_range}")
        elif state.budget_min:
            summary_parts.append(f"💰 Budget: at least **₹{state.budget_min}/sqft**")
        elif state.budget_max:
            summary_parts.append(f"💰 Budget: up to **₹{state.budget_max}/sqft**")
    if state.warehouse_type:
        summary_parts.append(f"🏗️ Type: **{state.warehouse_type}**")
    
    # Add dock count
    if state.min_docks is not None:
        summary_parts.append(f"🚚 Min Docks: **{state.min_docks}**")
    
    # Add clear height
    if state.min_clear_height is not None:
        summary_parts.append(f"📏 Min Height: **{state.min_clear_height} ft**")
    
    # Add compliances
    if state.compliances_query:
        summary_parts.append(f"📋 Compliance: **{state.compliances_query}**")
    
    # Add availability
    if state.availability:
        summary_parts.append(f"⏰ Availability: **{state.availability}**")
    
    # Add zone preference
    if state.zone:
        summary_parts.append(f"🗺️ Zone: **{state.zone}**")
    
    # Add broker preference
    if state.is_broker is not None:
        broker_text = "Broker properties preferred" if state.is_broker else "Owner properties preferred"
        summary_parts.append(f"🏢 Listing: **{broker_text}**")
    
    # Add fire NOC and land type requirements to the summary
    if state.fire_noc_required:
        summary_parts.append(f"🔥 Fire NOC: **Required**")
    if state.land_type_industrial is not None:
        land_type_text = "Industrial" if state.land_type_industrial else "Commercial/Flexible"
        summary_parts.append(f"🏭 Land Type: **{land_type_text}**")
    
    confirmation_message = (
        "Hope I captured your requirements well!\n\n" + 
        "\n".join(summary_parts) + 
        "\n\nAre these parameters fine? (yes/no)"
    )
    state.add_message("assistant", confirmation_message)
    print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {confirmation_message}")
    state.next_action = "wait_for_user"
    return state

async def search_database_node(state: GraphState) -> GraphState:
    # ... (no changes needed)
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Searching database...")
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Current budget state - min: {state.budget_min}, max: {state.budget_max}")
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Location query: {state.location_query}")
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Existing parsed_cities: {state.parsed_cities}")
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Existing parsed_state: {state.parsed_state}")
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Existing search_area: {state.search_area}")
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Existing is_area_search: {state.is_area_search}")
    
    if state.location_query and not state.parsed_cities and not state.parsed_state and not state.search_area:
        try:
            print(f"{Fore.YELLOW}[TOOL]{Style.RESET_ALL} Analyzing location: {state.location_query}")
            location_result = await analyze_location_query.ainvoke({"location_query": state.location_query})
            print(f"{Fore.YELLOW}[TOOL RESULT]{Style.RESET_ALL} {location_result}")
            if isinstance(location_result, dict):
                # Handle area-specific searches first
                if location_result.get("search_area") and location_result.get("search_city"):
                    state.search_area = location_result["search_area"]
                    state.search_city = location_result["search_city"]
                    state.is_area_search = True
                    state.parsed_cities = [location_result["search_city"]]
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Area search detected - Area: {state.search_area}, City: {state.search_city}")
                elif location_result.get("is_area_search"):
                    state.is_area_search = True
                    if location_result.get("areas"):
                        state.search_area = location_result["areas"][0]  # Use first area
                        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Area indicators detected - Area: {state.search_area}")
                
                # Handle standard location results
                if location_result.get("cities"):
                    if not state.parsed_cities:  # Don't override if already set by area search
                        state.parsed_cities = location_result["cities"]
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Parsed cities from tool: {state.parsed_cities}")
                elif location_result.get("state"):
                    state.parsed_state = location_result["state"]
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Parsed state from tool: {state.parsed_state}")
                elif not state.search_area:  # Only fallback if no area was detected
                    # If tool returns empty result, use original query as city
                    state.parsed_cities = [state.location_query]
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Tool returned empty, using original: {state.parsed_cities}")
            else:
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Location analysis tool returned an unexpected format.")
                state.parsed_cities = [state.location_query]
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Using original location as fallback: {state.parsed_cities}")
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Location analysis failed: {e}")
            # Simple fallback: use original query as city name
            state.parsed_cities = [state.location_query]
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Using original location as fallback: {state.parsed_cities}")
    else:
        print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Skipping location tool - using existing parsed data")
    search_params = {
        "cities": state.parsed_cities, "state": state.parsed_state, "search_area": state.search_area,
        "search_address": state.search_address, "is_area_search": state.is_area_search,
        "min_sqft": state.size_min, "max_sqft": state.size_max, "min_rate_per_sqft": state.budget_min, 
        "max_rate_per_sqft": state.budget_max, "warehouse_type": state.warehouse_type, 
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
                response_message = f"🔍 I couldn't find any warehouses matching your exact criteria. To get more options, we could try:\n\n• Expanding the location search area\n• Adjusting the budget range\n• Considering different property types\n• Relaxing size requirements\n\nWould you like me to adjust any of these parameters?"
            else:
                response_message = f"📄 That's all the results I found - {state.current_page-1} pages total. Want to try different search criteria to see more options?"
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
        if state.budget_min and state.budget_max:
            # Expand budget range by 20%
            current_range = state.budget_max - state.budget_min
            expansion = int(current_range * 0.2)
            state.budget_min = max(0, state.budget_min - expansion)
            state.budget_max = state.budget_max + expansion
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Relaxed budget range to: ₹{state.budget_min} - ₹{state.budget_max}/sqft")
        elif state.budget_min:
            # Reduce minimum budget by 20%
            state.budget_min = int(state.budget_min * 0.8)
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Reduced minimum budget to: ₹{state.budget_min}/sqft")
        elif state.budget_max:
            # Increase maximum budget by 20%
            state.budget_max = int(state.budget_max * 1.2)
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Increased maximum budget to: ₹{state.budget_max}/sqft")
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

async def _parse_location_change(state: GraphState, user_message: str):
    """Parse location change requests and update state accordingly."""
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract location from user message. Return ONLY JSON:
            {{"location_query": null}}
            Extract city/location name from the message. Look for city names after words like 'switch to', 'change to', 'make city', etc."""),
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
            state.search_results = None
            state.requirements_confirmed = False
            print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated location to: {state.location_query}")
        else:
            print(f"{Fore.YELLOW}[DEBUG]{Style.RESET_ALL} No location found in message: {user_message}")
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse location change: {e}")

async def _show_updated_requirements(state: GraphState):
    """Show updated requirements summary after parameter changes."""
    summary_parts = []
    
    if state.location_query:
        summary_parts.append(f"📍 Location: **{state.location_query}**")
    if state.size_min is not None or state.size_max is not None:
        size_range = f"**{state.size_min if state.size_min is not None else '0'} - {state.size_max if state.size_max is not None else 'any'} sqft**"
        summary_parts.append(f"📦 Size: {size_range}")
    
    # Handle budget range display
    if state.budget_min is not None or state.budget_max is not None:
        if state.budget_min and state.budget_max:
            budget_range = f"**₹{state.budget_min} - ₹{state.budget_max}/sqft**"
            summary_parts.append(f"💰 Budget: {budget_range}")
        elif state.budget_min:
            summary_parts.append(f"💰 Budget: at least **₹{state.budget_min}/sqft**")
        elif state.budget_max:
            summary_parts.append(f"💰 Budget: up to **₹{state.budget_max}/sqft**")
            
    if state.warehouse_type:
        summary_parts.append(f"🏗️ Type: **{state.warehouse_type}**")
    
    # Add dock count
    if state.min_docks is not None:
        summary_parts.append(f"🚚 Min Docks: **{state.min_docks}**")
    
    # Add clear height
    if state.min_clear_height is not None:
        summary_parts.append(f"📏 Min Height: **{state.min_clear_height} ft**")
    
    # Add compliances
    if state.compliances_query:
        summary_parts.append(f"📋 Compliance: **{state.compliances_query}**")
    
    # Add availability
    if state.availability:
        summary_parts.append(f"⏰ Availability: **{state.availability}**")
    
    # Add zone preference
    if state.zone:
        summary_parts.append(f"🗺️ Zone: **{state.zone}**")
    
    # Add broker preference
    if state.is_broker is not None:
        broker_text = "Broker properties preferred" if state.is_broker else "Owner properties preferred"
        summary_parts.append(f"🏢 Listing: **{broker_text}**")
    
    # Add fire NOC and land type requirements to the summary
    if state.fire_noc_required:
        summary_parts.append(f"🔥 Fire NOC: **Required**")
    if state.land_type_industrial is not None:
        land_type_text = "Industrial" if state.land_type_industrial else "Commercial/Flexible"
        summary_parts.append(f"🏭 Land Type: **{land_type_text}**")
    
    if summary_parts:
        updated_message = "Updated requirements:\n\n" + "\n".join(summary_parts) + "\n\nProceed with search? (yes/no)"
        state.add_message("assistant", updated_message)
        print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {updated_message}")
        state.next_action = "wait_for_user"
    else:
        # If no summary to show, at least acknowledge the update
        acknowledge_message = "Parameters updated. Proceed with search? (yes/no)"
        state.add_message("assistant", acknowledge_message)
        print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {acknowledge_message}")
        state.next_action = "wait_for_user"

async def human_input_node(state: GraphState) -> GraphState:
    """Human input node - for API mode, just return state for user to provide input"""
    # In API mode, we don't wait for CLI input
    # The API will handle user input separately and invoke the graph again
    # Just mark that we're waiting for user input and end the workflow
    state.next_action = "wait_for_user"
    return state