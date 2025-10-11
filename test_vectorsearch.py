import os
import sys
import psycopg2
from dotenv import load_dotenv
from openai import OpenAI

# --- CONFIGURATION ---
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize API clients
try:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    sys.exit(1)

# --- HELPER FUNCTIONS ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        sys.exit(1)

def get_embedding(text):
    """Generates a vector embedding for a given text block."""
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding from OpenAI: {e}")
        return None

# --- MAIN SCRIPT ---
def main():
    """Takes a CLI query, searches the DB, and displays top 5 matches."""
    # 1. Get query from command-line arguments
    if len(sys.argv) < 2:
        print("Usage: python search.py \"<your search query>\"")
        sys.exit(1)
    
    query_text = " ".join(sys.argv[1:])
    print(f"🔍 Searching for locations similar to: \"{query_text}\"")

    # 2. Generate embedding for the user's query
    query_embedding = get_embedding(query_text)
    if query_embedding is None:
        sys.exit(1)
        
    # 3. Connect to the DB and perform the similarity search
    conn = get_db_connection()
    cur = conn.cursor()

    sql_query = """
        SELECT 
            w.id,
            w.address,
            w.city,
            w.state,
            wd."fireNocAvailable",
            wd."fireSafetyMeasures",
            wd."landType",
            wd.embedding <=> %s AS distance
        FROM "WarehouseData" wd
        JOIN "Warehouse" w ON w.id = wd."warehouseId"
        ORDER BY distance
        LIMIT 5;
    """
    
    try:
        # Pass the embedding as a string representation of the list
        cur.execute(sql_query, (str(query_embedding),))
        results = cur.fetchall()
        
        if not results:
            print("\nNo matches found.")
            return

        print("\n--- Top 5 Matches ---")
        for i, row in enumerate(results):
            (warehouse_id, address, city, state, 
             fire_noc, fire_safety, land_type, distance) = row
            
            # Convert distance to a more intuitive similarity score
            similarity_score = 1 - distance
            
            print(f"\n{i+1}. Warehouse ID: {warehouse_id} (Similarity Score: {similarity_score:.4f})")
            print(f"   Address: {address}, {city}, {state}")
            print(f"   Land Type: {land_type or 'N/A'}")
            print(f"   Fire NOC: {'Yes' if fire_noc else 'No' if fire_noc is not None else 'N/A'}")
            print(f"   Fire Safety: {fire_safety or 'N/A'}")
        print("\n-------------------")

    except Exception as e:
        print(f"An error occurred during the database query: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()