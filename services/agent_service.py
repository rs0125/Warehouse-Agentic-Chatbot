# services/agent_service.py

import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.caches import InMemoryCache
from langchain_core.globals import set_llm_cache

from tools.database_tool import find_warehouses_in_db
from tools.location_tool import analyze_location_query

load_dotenv()

set_llm_cache(InMemoryCache())

llm = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [analyze_location_query, find_warehouses_in_db]

# CHANGED: The prompt now includes a rule to bypass the final summarization step.
prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are a supervisor agent for a warehouse search chatbot. Your job is to orchestrate a multi-step process to answer user queries efficiently.\n"
        "**Step 1: Analyze Location.** For any user query involving a location, you MUST first use the 'location-intelligence-tool'.\n"
        "**Step 2: Search Database.** After analyzing the location, you MUST use the 'warehouse-database-search' tool to find the warehouses.\n"
        "**PAGINATION RULE:** If the user asks for 'more options' or 'next', you MUST increment the 'page' number of the last database search.\n"
        "**OUTPUT RULE:** When the 'warehouse-database-search' tool returns a successful result (not an error or 'not found' message), your job is done. Your final output should be ONLY the direct, unmodified result from that tool. Do not add any conversational text or summarization.\n"
        "**USER INTERACTION:** If the database search is successful, do not ask a follow-up question. If the search fails or finds no results, then you should formulate a helpful conversational response."
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

# Using an in-memory store for this example. Replace with Redis for production.
chat_history_store = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in chat_history_store:
        chat_history_store[session_id] = ChatMessageHistory()
    return chat_history_store[session_id]

agent_with_chat_history = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

# --- Main Service Function ---
# CHANGED: The streaming logic is now more sophisticated.

async def run_agent_stream(user_input: str, session_id: str):
    """Runs the agent and streams structured JSON events, intercepting tool output for speed."""
    
    def format_event(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    async for event in agent_with_chat_history.astream_events(
        {"input": user_input},
        config={"configurable": {"session_id": session_id}},
        version="v1"
    ):
        kind = event["event"]
        
        if kind == "on_chain_start":
            if event["name"] == "AgentExecutor":
                yield format_event({"type": "status", "message": "Agent is thinking..."})

        elif kind == "on_tool_start":
            yield format_event({
                "type": "tool_call",
                "tool": event["name"],
                "input": event["data"].get("input")
            })
            
        elif kind == "on_tool_end":
            # This is the key change. We intercept the database tool's output.
            if event["name"] == "warehouse-database-search":
                output = event["data"].get("output")
                # Check if the tool returned actual data, not a "not found" message
                if output and "No warehouses found" not in output:
                    # Send the raw data as a special event and STOP the stream.
                    yield format_event({"type": "data_result", "data": output})
                    return # This bypasses the final LLM call.

            # We still want to see the output of the location tool for UX
            yield format_event({
                "type": "tool_output",
                "tool": event["name"],
                "output": event["data"].get("output")
            })

        elif kind == "on_chat_model_stream":
            # This will now only be used for conversational messages (e.g., error handling)
            content = event["data"]["chunk"].content
            if content:
                yield format_event({"type": "final_chunk", "content": content})