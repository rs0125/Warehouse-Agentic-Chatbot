# main.py
import asyncio
import uuid
from dotenv import load_dotenv
import colorama
from colorama import Fore, Style, Back
import os

# --- DIAGNOSTIC TEST ---
# 1. Load environment variables from the .env file
load_dotenv()

# 2. Check if the OPENAI_API_KEY was actually loaded
api_key = os.getenv("OPENAI_API_KEY")

if api_key:
    print(f"{Fore.GREEN}✅ SUCCESS: OpenAI API Key was found in the environment.{Style.RESET_ALL}")
else:
    print(f"{Fore.RED}❌ FAILURE: OpenAI API Key was NOT found after loading .env.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}   Please check that your .env file is named correctly, is in the same directory as this script, and contains the line: OPENAI_API_KEY=sk-...{Style.RESET_ALL}")
    exit() # Stop the script here if the key is missing

# 3. Only import the graph *after* the key has been verified
from graph import create_warehouse_graph

async def run_cli_chatbot():
    """Main CLI chatbot interface."""
    colorama.init()
    
    print(f"\n{Back.BLUE}{Fore.WHITE} 🏢 WAREHOUSE DISCOVERY AGENT (LangGraph) 🏢 {Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Welcome! I'll help you find warehouse properties.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Type 'quit', 'exit', or 'bye' to end the conversation.{Style.RESET_ALL}\n")
    
    app = create_warehouse_graph()
    
    config = {
        "configurable": {"thread_id": str(uuid.uuid4())},
        "recursion_limit": 50  # Increase from default 25 to 50
    }
    
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