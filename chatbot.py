# chatbot.py

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

# NEW: Import the required ChatMessageHistory class
from langchain_community.chat_message_histories import ChatMessageHistory

# --- Caching and Tool Imports ---
from langchain_core.caches import InMemoryCache
from langchain_core.globals import set_llm_cache
set_llm_cache(InMemoryCache())
from tools import find_warehouses_in_db
from location_tools import analyze_location_query

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [analyze_location_query, find_warehouses_in_db]

prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are a supervisor agent for a warehouse search chatbot. Your job is to orchestrate a two-step process to answer user queries.\n"
        "**Step 1: Analyze Location.** For any user query involving a location, you MUST first use the 'location-intelligence-tool'.\n"
        "**Step 2: Search Database.** Once you have a list of cities, you MUST use the 'warehouse-database-search' tool to find the warehouses.\n"
        "**PAGINATION RULE:** If the user asks for 'more options', 'next', or a similar request, you MUST re-invoke the 'warehouse-database-search' tool. "
        "Use the exact same search criteria from the previous turn, but you MUST increment the 'page' number by 1. If no page number was used before, assume the new page is 2.\n"
        "**User Interaction:** After presenting results, always ask a follow-up question to help the user narrow the search."
    )),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_openai_tools_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True
)

# This store will now hold ChatMessageHistory objects instead of plain lists
chat_history_store = {}

# NEW: This function gets the history object for a session, creating it if needed
def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in chat_history_store:
        chat_history_store[session_id] = ChatMessageHistory()
    return chat_history_store[session_id]

# CHANGED: We pass our new function to the history-aware runnable
agent_with_chat_history = RunnableWithMessageHistory(
    agent_executor,
    get_session_history, # Pass the function here
    input_messages_key="input",
    history_messages_key="chat_history",
)

if __name__ == "__main__":
    print("Warehouse Chatbot is ready! Type 'exit' to end.")
    session_id = "user1"
    
    while True:
        user_input = input("You: ")
        if user_input.lower() in ['exit', 'quit']:
            break
        
        print("Bot: ", end="", flush=True)
        for chunk in agent_with_chat_history.stream(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}},
        ):
            if "output" in chunk:
                print(chunk["output"], end="", flush=True)
        print()