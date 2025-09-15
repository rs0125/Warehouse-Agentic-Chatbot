

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![LangChain](https://img.shields.io/badge/🦜%EF%B8%8F%20LangChain-v0.2-green)](https://www.langchain.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-purple)](https://openai.com/)
[![Database](https://img.shields.io/badge/Database-Supabase%20(Postgres)-orange)](https://supabase.com/)

An intelligent, conversational agent for discovering warehouse properties using natural language. This chatbot leverages a multi-layer agentic architecture to understand user intent, resolve ambiguities, perform robust database searches, and handle failures gracefully.

## ✨ Key Features

* **Location Intelligence**: Understands regional queries ("warehouses in North Bangalore"), aliases ("blr" for "Bengaluru"), and misspellings, using a dedicated tool to resolve them into canonical city names.
* **Self-Correcting Search**: Automatically performs fallback queries with relaxed constraints. If a search for warehouses under ₹15/sqft fails, it retries with a slightly higher budget (e.g., up to ₹17.25/sqft).
* **Fuzzy Expansion**: If a search returns too few results, it intelligently expands the criteria (e.g., price) to provide more relevant options and prevent dead-end conversations.
* **Stateful Conversation**: Remembers search criteria and pagination context across multiple turns, allowing users to refine searches ("now show me only PEB warehouses") or ask for more results ("show me the next page").
* **Optimized Performance**: Utilizes an in-memory LLM cache to avoid redundant API calls and streams responses to the user for better perceived speed.
* **Supervisor-Worker Architecture**: Employs a robust two-agent design where a high-level **Supervisor** plans tasks and a set of specialized **Worker Tools** execute them.

##  Demo Interaction

Here's a sample conversation flow:

**User:** `find warehouses in blr with at least 2 docks for under 18 rs/sqft`

> **Bot:** *[Thinking Process]*
> 1.  **Supervisor:** User query has a location. I must use `location-intelligence-tool` first.
> 2.  **Tool Call:** `analyze_location_query(location_query='blr')` -> Returns `{'cities': ['Bangalore', 'Bengaluru']}`.
> 3.  **Supervisor:** Now I have cities and other criteria. I must use `warehouse-database-search`.
> 4.  **Tool Call:** `find_warehouses_in_db(cities=['Bangalore', 'Bengaluru'], min_docks=2, max_rate_per_sqft=18)`
> 5.  **Supervisor:** Presenting results to the user.

> **Bot:** I found these warehouses for you in and around Bangalore/Bengaluru:
>
> ID: 101, Type: PEB, City: Bangalore, Spaces: 50000, 75000 sqft, Rate: 16, Docks: 4
> ID: 105, Type: RCC, City: Bengaluru, Spaces: 120000 sqft, Rate: 18, Docks: 3
>
> Would you like to filter these further by warehouse type or compliance requirements?

---

**User:** `show me more`

> **Bot:** *[Thinking Process]*
> 1.  **Supervisor:** User wants more results. I must re-run the previous search but increment the page number to 2.
> 2.  **Tool Call:** `find_warehouses_in_db(cities=['Bangalore', 'Bengaluru'], min_docks=2, max_rate_per_sqft=18, page=2)`

> **Bot:** Of course, here are the next set of results:
>
> ID: 112, Type: PEB, City: Bangalore, Spaces: 85000 sqft, Rate: 17, Docks: 2
> ...

---

**User:** `any options in Tumkur for 10 rs`

> **Bot:** *[Thinking Process]*
> 1.  **Supervisor:** New location and price. Must use `location-intelligence-tool` first.
> 2.  **Tool Call:** `analyze_location_query(location_query='Tumkur')` -> `{'cities': ['Tumkur', 'Tumakuru']}`
> 3.  **Supervisor:** Now search the database.
> 4.  **Tool Call:** `find_warehouses_in_db(cities=['Tumkur', 'Tumakuru'], max_rate_per_sqft=10)` -> Returns `No warehouses found...`
> 5.  **DB Worker Tool (Internal Logic):** Initial search failed. Automatically relaxing `max_rate_per_sqft` by 15% (to 11.5) and retrying.
> 6.  **Tool Call (Retry):** `find_warehouses_in_db(...)` -> Returns results.
> 7.  **Supervisor:** Presenting fallback results with a helpful message.

> **Bot:** I couldn't find anything at your exact price of ₹10/sqft, but found these with a rate up to ₹11.5/sqft:
>
> ID: 240, Type: PEB, City: Tumkur, Spaces: 60000 sqft, Rate: 11, Docks: 2
>
> Would this option work for you?

## ⚙️ System Architecture

The agent uses a **Supervisor-Worker** model to separate planning from execution.

1.  **Supervisor Agent (`chatbot.py`)**: The main conversational agent that interacts with the user. It analyzes the user's request, determines which tool to use, and formulates the final response. It is responsible for the multi-step reasoning (Location -> Search) and managing conversational state (like pagination).

2.  **Location Intelligence Tool (`location_tools.py`)**: A specialized "reasoning" tool. It takes a raw location query and uses a targeted LLM call to resolve it into a canonical list of city names for the database query.

3.  **Database Worker Tool (`tools.py`)**: The "execution" tool. It takes a structured request from the Supervisor and queries the PostgreSQL database. It contains all the logic for building SQL queries, handling data type casting, and implementing the self-correction and fuzzy expansion fallbacks.

## 🛠️ Technology Stack

* **Runtime**: Python 3.9+
* **Core AI Framework**: LangChain (v0.2+)
* **LLM Provider**: OpenAI (`gpt-4o`)
* **Database**: Supabase (PostgreSQL)
* **Python Packages**: `langchain`, `langchain-openai`, `sqlalchemy`, `psycopg2-binary`, `python-dotenv`

## 📦 Database Schema

The agent is designed to work with the following PostgreSQL schema (defined using Prisma syntax for clarity).

```prisma
model Warehouse {
  id                    Int       @id @default(autoincrement())
  warehouseOwnerType    String?
  warehouseType         String
  address               String    @db.Text
  googleLocation        String?
  city                  String
  state                 String
  postalCode            String?
  zone                  String
  contactPerson         String
  contactNumber         String
  totalSpaceSqft        Int[]
  offeredSpaceSqft      Int[]
  numberOfDocks         String?
  clearHeightFt         String?
  compliances           String
  otherSpecifications   String?   @db.Text
  ratePerSqft           String
  availability          String?
  uploadedBy            String
  isBroker              String?
  photos                String?

  createdAt             DateTime? @default(now())
  statusUpdatedAt       DateTime? @updatedAt @map("status_updated_at")
}
````

## 🏁 Getting Started

### 1\. Prerequisites

  * Python 3.9 or higher
  * Git
  * A Supabase account with a new project or a standalone PostgreSQL database.

### 2\. Installation & Setup

1.  **Clone the repository:**

    ```bash
    git clone [https://github.com/your-username/warehouse-chatbot.git](https://github.com/your-username/warehouse-chatbot.git)
    cd warehouse-chatbot
    ```

2.  **Create and activate a virtual environment:**

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    # On Windows, use: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    A `requirements.txt` file should be created with the following content:

    ```txt
    langchain
    langchain-openai
    langchain-community
    langchain-core
    psycopg2-binary
    SQLAlchemy
    python-dotenv
    openai
    ```

    Then run:

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up the database:**

      * In your Supabase project, go to the **SQL Editor**.
      * Create a new query to create the `Warehouse` table using the schema above.
      * Populate the table with some sample data. **Important**: Ensure text-based number fields like `ratePerSqft`, `numberOfDocks`, etc., contain string values that can be cast to numbers (e.g., `"18"`, `"4"`).

5.  **Configure Environment Variables:**

      * Create a file named `.env` in the root directory.
      * Copy the contents of the provided `.env` example and fill in your credentials:

    <!-- end list -->

    ```ini
    # .env
    OPENAI_API_KEY="sk-..."
    DATABASE_URL="postgresql://postgres:[YOUR-PASSWORD]@[YOUR-DB-HOST]:5432/postgres"
    ```

      * You can find your `DATABASE_URL` in Supabase under `Project Settings` \> `Database` \> `Connection string`.

### 3\. Running the Chatbot

Execute the main agent file from your terminal:

```bash
python chatbot.py
```

You can now start interacting with your intelligent warehouse chatbot directly in the console\!

## 📂 Code Overview

  * `chatbot.py`: The main entry point. Initializes and runs the Supervisor Agent, manages chat history, and handles the user interaction loop.
  * `tools.py`: Defines the `warehouse-database-search` tool. Contains all the SQL query logic, connection handling, and self-correction/expansion features.
  * `location_tools.py`: Defines the `location-intelligence-tool` used to resolve location names and regions before hitting the database.
  * `.env`: Stores confidential keys and connection strings.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
