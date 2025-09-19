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
    """Node that parses user input and updates the state."""
    if not state.messages or state.messages[-1]["role"] != "user":
        state.next_action = "gather_requirements"
        return state
    
    user_message = state.messages[-1]["content"]
    user_message_lower = user_message.lower()
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Parsing user input: '{user_message}'")
    
    if user_message_lower in ["more", "next", "show more"]:
        state.current_page += 1
        state.next_action = "search_database"
        return state
    
    # ============================ FIX STARTS HERE ============================
    # This check is now more flexible to catch variations of "yes".
    affirmative_keywords = ["yes", "yep", "sure", "correct", "confirm", "looks good", "do it", "start"]
    if any(keyword in user_message_lower for keyword in affirmative_keywords):
        state.requirements_confirmed = True
        state.next_action = "search_database"
        return state
    # ============================= FIX ENDS HERE =============================

    # The prompt and the rest of the function remain the same
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are extracting warehouse requirements from user messages. 
        IMPORTANT: Return ONLY a raw JSON object. Do NOT wrap it in markdown code blocks or add any other text.
        Return this exact JSON structure:
        {{"location_query": null, "size_min": null, "size_max": null, "budget_max": null, "warehouse_type": null, "compliances_query": null, "min_docks": null, "min_clear_height": null, "availability": null, "zone": null, "is_broker": null}}
        
        Instructions:
        1.  If the user specifies a range (e.g., "between 30k and 50k"), populate both `size_min` and `size_max`.
        2.  For phrases like "up to", "less than", or "maximum of", only populate `size_max` and leave `size_min` as null.
        3.  For phrases like "at least", "more than", or "minimum of", only populate `size_min` and leave `size_max` as null.
        4.  If the user wants to remove a filter (e.g., "any size", "remove size filter"), set both `size_min` and `size_max` to null.
        5.  If the user provides a single target number (e.g., "50000 sqft"), set both `size_min` and `size_max` to that same number.
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

            if parsed_min_val is not None or parsed_max_val is not None:
                parameter_changed = True
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
                elif parsed_min_val and not parsed_max_val:
                    state.size_min, state.size_max = int(parsed_min_val), None
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated with minimum size: {state.size_min} sqft")
                elif not parsed_min_val and parsed_max_val:
                    state.size_min, state.size_max = None, int(parsed_max_val)
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated with maximum size: {state.size_max} sqft")
                else:
                    state.size_min, state.size_max = None, None
                    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Cleared size requirements.")

            if parsed_data.get("budget_max"):
                state.budget_max = int(parsed_data["budget_max"])
                parameter_changed = True
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated budget: {state.budget_max}")
            if parsed_data.get("warehouse_type"):
                state.warehouse_type = parsed_data["warehouse_type"]
                parameter_changed = True
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Updated type: {state.warehouse_type}")
            
            if parameter_changed:
                state.requirements_confirmed = False
                print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} Search parameters changed, resetting confirmation status.")
                state.next_action = "gather_requirements"
            else:
                state.next_action = "chit_chat"

        except json.JSONDecodeError as je:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse JSON from LLM: {je}")
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} LLM response was: {response.content}")
            state.next_action = "chit_chat"
            
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to parse user input: {e}")
        state.next_action = "gather_requirements"
    
    return state

# (confirm_requirements_node, search_database_node, and human_input_node remain the same as before)
async def confirm_requirements_node(state: GraphState) -> GraphState:
    # ... (no changes needed)
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
    confirmation_message = (
        "Alright, let's double-check. Here's what I've got for your search:\n\n" + 
        "\n".join(summary_parts) + 
        "\n\nDoes this look right to you? If so, I'll start searching right away! (yes/no)"
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
        "zone": state.zone, "is_broker": state.is_broker, "page": state.current_page
    }
    search_params = {k: v for k, v in search_params.items() if v is not None}
    try:
        print(f"{Fore.YELLOW}[TOOL]{Style.RESET_ALL} Searching with params: {search_params}")
        search_results = await find_warehouses_in_db.ainvoke(search_params)
        print(f"{Fore.YELLOW}[TOOL RESULT]{Style.RESET_ALL} Found results")
        state.search_results = search_results
        if "No warehouses found" in str(search_results) or "No more warehouses" in str(search_results):
             response_message = f"🔍 On it... Okay, I've checked our listings (Page {state.current_page}), but it looks like we don't have anything that matches those exact criteria right now. Maybe we could try broadening the search a bit?"
        else:
            response_message = f"🚀 Okay, I've found some options for you! Here are the results from page {state.current_page}:\n\n{search_results}"
            response_message += "\n\n💡 If you want to see more, just say **'more'** or **'next'**!"
        state.add_message("assistant", response_message)
        print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {response_message}")
    except Exception as e:
        error_message = f"😬 Uh oh, I hit a snag while searching. Here's the technical error: {str(e)}"
        state.add_message("assistant", error_message)
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {error_message}")
    state.next_action = "wait_for_user"
    return state

async def human_input_node(state: GraphState) -> GraphState:
    # ... (no changes needed)
    user_input = input(f"{Fore.CYAN}[YOU]{Style.RESET_ALL} ").strip()
    if user_input.lower() in ['quit', 'exit', 'bye']:
        state.conversation_complete = True
        goodbye_message = "You got it. Thanks for chatting! Feel free to reach out anytime you need to find a warehouse. Have a great day!"
        state.add_message("assistant", goodbye_message)
        print(f"{Fore.GREEN}[AGENT]{Style.RESET_ALL} {goodbye_message}")
        return state
    state.add_message("user", user_input)
    state.next_action = "update_state"
    return state