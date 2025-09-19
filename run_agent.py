#!/usr/bin/env python3
"""
Simple runner script for the LangGraph Warehouse Agent CLI
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

try:
    from langgraph_warehouse_agent import run_cli_chatbot
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you have installed all requirements:")
    print("pip install -r requirements.txt")
    sys.exit(1)

def main():
    """Main entry point."""
    try:
        # Check if .env file exists
        if not os.path.exists(".env"):
            print("⚠️  Warning: No .env file found!")
            print("Please create a .env file with your database and OpenAI credentials:")
            print("DATABASE_URL=postgresql://...")
            print("OPENAI_API_KEY=sk-...")
            print()
        
        # Run the async chatbot
        asyncio.run(run_cli_chatbot())
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error starting agent: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()