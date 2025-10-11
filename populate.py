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
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# --- DATABASE HELPER ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        sys.exit(1)

# --- API HELPER ---
def get_embedding(text):
    """Generates a vector embedding for a given text block."""
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None

# --- MAIN SCRIPT ---
def main():
    """Updates the embedding column for all warehouses based on location."""
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Fetch the location info for ALL warehouses from the main table
    cur.execute("""
        SELECT id, address, city, state
        FROM "Warehouse";
    """)
    warehouses_to_process = cur.fetchall()

    print(f"Found {len(warehouses_to_process)} warehouses. Starting embedding update process...")

    for row in warehouses_to_process:
        warehouse_id, address, city, state = row
        print(f"\nProcessing Warehouse ID: {warehouse_id}...")

        # 2. Create the location-only text for the new embedding
        text_for_embedding = f"Warehouse located at: {address}, {city}, {state}."

        embedding = get_embedding(text_for_embedding)
        if not embedding:
            print("  -> Embedding generation failed. Skipping.")
            continue
        print("  -> New embedding generated.")

        # 3. Execute a targeted UPDATE command
        # This ONLY changes the 'embedding' column and leaves all others untouched.
        try:
            embedding_str = str(embedding)
            cur.execute(
                """
                UPDATE "WarehouseData"
                SET embedding = %s
                WHERE "warehouseId" = %s;
                """,
                (embedding_str, warehouse_id)
            )
            
            # Check if a row was actually updated
            if cur.rowcount > 0:
                conn.commit()
                print(f"  -> Successfully updated embedding for Warehouse ID {warehouse_id}.")
            else:
                # This handles cases where a warehouse exists but has no entry in WarehouseData
                print(f"  -> WARNING: No row in WarehouseData for Warehouse ID {warehouse_id}. No update performed.")


        except Exception as e:
            print(f"  -> Database update failed: {e}")
            conn.rollback()

    cur.close()
    conn.close()
    print("\nUpdate process complete.")

if __name__ == "__main__":
    main()