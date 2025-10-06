# Warehouse Agentic Chatbot API Documentation

## Overview
A FastAPI-based conversational agent for warehouse discovery with a 3-stage workflow that maintains stateless operation through context passing.

## Base URL
```
http://localhost:8000
```

## Authentication
No authentication required for this demo API.

## API Endpoints

### 1. Health Check
**GET** `/health`

Check if the API is running and healthy.

**Response:**
```json
{
    "status": "healthy",
    "timestamp": "2024-10-06T10:30:00Z"
}
```

**Example:**
```bash
curl http://localhost:8000/health
```

### 2. Start Conversation
**POST** `/start`

Initialize a new conversation with the warehouse agent.

**Request Body:** None required

**Response:**
```json
{
    "message": "Welcome to the Warehouse Discovery Agent! I'll help you find the perfect warehouse for your needs. To get started, could you tell me about the area where you're looking for a warehouse and any size requirements you might have?",
    "context": {
        "current_stage": "area_size",
        "area": null,
        "size_constraint": null,
        "land_type_preference": null,
        "specific_requirements": [],
        "conversation_history": []
    }
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json"
```

### 3. Send Message
**POST** `/chat`

Send a message to the agent and receive a response with updated context.

**Request Body:**
```json
{
    "message": "string (required)",
    "context": {
        "current_stage": "string",
        "area": "string or null",
        "size_constraint": "string or null", 
        "land_type_preference": "string or null",
        "specific_requirements": ["array of strings"],
        "conversation_history": ["array of strings"]
    }
}
```

**Response:**
```json
{
    "message": "Agent response message",
    "context": {
        "current_stage": "updated_stage",
        "area": "extracted_area",
        "size_constraint": "extracted_size",
        "land_type_preference": "yes/no/null",
        "specific_requirements": ["updated requirements"],
        "conversation_history": ["updated history"]
    }
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "All warehouses in Bangalore",
    "context": {
        "current_stage": "area_size",
        "area": null,
        "size_constraint": null,
        "land_type_preference": null,
        "specific_requirements": [],
        "conversation_history": []
    }
  }'
```

## Workflow Stages

### Stage 1: Area/Size Collection (`area_size`)
**Purpose:** Gather location and size requirements

**User Input Examples:**
- "All warehouses in Bangalore"
- "10000 sq ft warehouse in Electronic City"
- "Small warehouse near Whitefield"

**Expected Context Updates:**
- `area`: Location string (e.g., "bangalore", "electronic city")
- `size_constraint`: Size requirement (e.g., "small", "10000 sq ft")

### Stage 2: Land Type Preference (`business_nature`)
**Purpose:** Determine if industrial land CLU is required

**Agent Question:** "Do you specifically need warehouses on industrial land with proper CLU (Change of Land Use)?"

**User Input Examples:**
- "Yes" or "Yes, I need industrial land"
- "No" or "Commercial land is fine"

**Expected Context Updates:**
- `land_type_preference`: "yes" or "no"

### Stage 3: Specific Requirements (`specifics`)
**Purpose:** Collect additional requirements and perform search

**User Input Examples:**
- "Fire NOC required"
- "Good road connectivity"
- "Show me all available options"

**Expected Context Updates:**
- `specific_requirements`: Array of requirement strings
- `current_stage`: "search_complete" when search is performed

## Context Management

### Context Structure
```typescript
interface Context {
    current_stage: "area_size" | "business_nature" | "specifics" | "search_complete"
    area: string | null                    // Location requirement
    size_constraint: string | null         // Size requirement  
    land_type_preference: string | null    // "yes" or "no" for industrial land
    specific_requirements: string[]        // Additional requirements
    conversation_history: string[]         // Previous messages
}
```

### Stateless Architecture
- Each request must include the current context
- Context is updated and returned with each response
- No server-side session storage
- Perfect for distributed deployments

## Database Integration

### Warehouse Search Logic
1. **Area Filtering:** Matches `area` field in database
2. **Size Filtering:** 
   - "small" → warehouses ≤ 5000 sq ft
   - "medium" → warehouses 5001-15000 sq ft  
   - "large" → warehouses > 15000 sq ft
   - Specific numbers → exact or range matching
3. **Land Type Filtering:** Uses `WarehouseData.land_clu` field
4. **Fire NOC Filtering:** Uses `WarehouseData.fire_noc` field

### Search Results Format
```html
<!-- Results are returned as formatted HTML -->
<h3>🏢 Found X warehouses matching your criteria:</h3>

<div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px;">
    <h4>📍 Warehouse Name</h4>
    <p><strong>📍 Location:</strong> Area, City</p>
    <p><strong>📏 Size:</strong> X sq ft</p>
    <p><strong>🌍 Land Type:</strong> Industrial/Commercial</p>
    <p><strong>🔥 Fire NOC:</strong> Available/Not Available</p>
    <p><strong>📞 Contact:</strong> Phone Number</p>
</div>
```

## Error Handling

### Standard Error Response
```json
{
    "detail": "Error description"
}
```

### Common Errors
- **422 Validation Error:** Invalid request body format
- **500 Internal Server Error:** Database connection issues or processing errors

## Example Complete Workflow

### 1. Start Conversation
```bash
curl -X POST http://localhost:8000/start
```

### 2. Specify Location/Size
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "10000 sq ft warehouse in Electronic City",
    "context": {
        "current_stage": "area_size",
        "area": null,
        "size_constraint": null,
        "land_type_preference": null,
        "specific_requirements": [],
        "conversation_history": []
    }
  }'
```

### 3. Answer Land Type Question
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Yes, I need industrial land",
    "context": {
        "current_stage": "business_nature",
        "area": "electronic city",
        "size_constraint": "10000 sq ft",
        "land_type_preference": null,
        "specific_requirements": [],
        "conversation_history": ["10000 sq ft warehouse in Electronic City"]
    }
  }'
```

### 4. Add Specific Requirements
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Fire NOC required",
    "context": {
        "current_stage": "specifics",
        "area": "electronic city",
        "size_constraint": "10000 sq ft", 
        "land_type_preference": "yes",
        "specific_requirements": [],
        "conversation_history": ["10000 sq ft warehouse in Electronic City", "Yes, I need industrial land"]
    }
  }'
```

## Testing the API

### Quick Test Script
```python
import requests
import json

BASE_URL = "http://localhost:8000"

# 1. Health check
response = requests.get(f"{BASE_URL}/health")
print("Health:", response.json())

# 2. Start conversation
response = requests.post(f"{BASE_URL}/start")
data = response.json()
print("Start:", data["message"])
context = data["context"]

# 3. Send message
response = requests.post(f"{BASE_URL}/chat", json={
    "message": "All warehouses in Bangalore",
    "context": context
})
data = response.json()
print("Response:", data["message"])
context = data["context"]
```

### JavaScript Fetch Example
```javascript
// Start conversation
const startResponse = await fetch('http://localhost:8000/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'}
});
const startData = await startResponse.json();
let context = startData.context;

// Send message
const chatResponse = await fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        message: "Small warehouse in Whitefield",
        context: context
    })
});
const chatData = await chatResponse.json();
context = chatData.context;
```

## Production Deployment

### Environment Variables
```bash
export OPENAI_API_KEY="your-openai-api-key"
export DATABASE_URL="postgresql://user:pass@host:port/dbname"  # Optional
```

### Running the Server
```bash
# Development
python api.py

# Production with Uvicorn
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4

# With Gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker api:app --bind 0.0.0.0:8000
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

## CORS Configuration
The API includes CORS middleware allowing all origins for development. For production, configure specific allowed origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domains
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```