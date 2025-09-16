# chatbot.py

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

# --- OPTIMIZATION: Caching ---
from langchain_core.caches import InMemoryCache
from langchain_core.globals import set_llm_cache

# Set up an in-memory cache for all LLM calls to avoid redundant work
set_llm_cache(InMemoryCache())
# -----------------------------

# Import tools from their refactored locations
from tools.database_tool import find_warehouses_in_db
from tools.location_tool import analyze_location_query

# Load environment variables from .env file
load_dotenv()

# 1. Initialize the LLM and Tools
llm = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [analyze_location_query, find_warehouses_in_db]

# 2. Create the Supervisor Agent's Prompt
# This prompt contains all the rules and logic for how the agent should think and act.
prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are a supervisor agent for a warehouse search chatbot. Your job is to orchestrate a multi-step process to answer user queries intelligently.\n"
        "**Step 1: Analyze Location.** For any user query involving a location, you MUST first use the 'location-intelligence-tool'. This tool will resolve aliases and regions into a standard format.\n"
        "**Step 2: Search Database.** After analyzing the location, you MUST use the 'warehouse-database-search' tool. Use the following logic:\n"
        "- If the location tool returns a 'state', you should pass it to the 'state' parameter of the database tool.\n"
        "- If the location tool returns a list of 'cities', you should pass it to the 'cities' parameter of the database tool.\n"
        "**PAGINATION RULE:** If the user asks for 'more options', 'next', or a similar request, you MUST re-invoke the 'warehouse-database-search' tool. "
        "Use the exact same search criteria from the previous turn, but you MUST increment the 'page' number by 1. If no page number was used before, assume the new page is 2.\n"
        "**User Interaction:** After presenting results, always ask a follow-up question to help the user narrow the search."
    )),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# 3. Create the Agent and AgentExecutor
agent = create_openai_tools_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True
)

# 4. Set up Modern, Stateful Memory
# This store will hold ChatMessageHistory objects for each conversation session.
chat_history_store = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    """Gets the history object for a session, creating it if it doesn't exist."""
    if session_id not in chat_history_store:
        chat_history_store[session_id] = ChatMessageHistory()
    return chat_history_store[session_id]

# Wrap the agent executor in the history-aware runnable
agent_with_chat_history = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

# 5. Main Execution Loop
if __name__ == "__main__":
    print("Warehouse Chatbot is ready! Type 'exit' to end.")
    # For a simple CLI, we can use a single, hardcoded session ID
    session_id = "user123"
    
    while True:
        user_input = input("You: ")
        if user_input.lower() in ['exit', 'quit']:
            break
        
        # --- OPTIMIZATION: Streaming ---
        # We use .stream() to get results token-by-token for a more responsive feel.
        print("Bot: ", end="", flush=True)
        try:
            for chunk in agent_with_chat_history.stream(
                {"input": user_input},
                config={"configurable": {"session_id": session_id}},
            ):
                if "output" in chunk:
                    print(chunk["output"], end="", flush=True)
            print() # Final newline
        except Exception as e:
            # Graceful error handling for API or other issues
            print(f"\n[Error] An error occurred: {e}")
        # -----------------------------