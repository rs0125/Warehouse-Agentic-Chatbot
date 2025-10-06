# WareOnGo Warehouse Discovery API

AI-powered warehouse discovery platform with FastAPI backend and frontend integration examples.

## Architecture Overview

```
Frontend (React/Vue/HTML) ←→ FastAPI Backend ←→ LangGraph Workflow ←→ Database
```

### Key Design Principles
- **Stateless API**: No session storage in backend
- **Context-based**: Frontend sends conversation context with each request
- **Real-time**: Immediate responses through AI workflow
- **Scalable**: Can handle multiple simultaneous conversations

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
export OPENAI_API_KEY="your-openai-api-key-here"

# Database configuration (if using database features)
export DATABASE_URL="postgresql+asyncpg://user:password@localhost/warehouse_db"
```

### 3. Start the API Server
```bash
# Development server with auto-reload
python api.py

# Or using uvicorn directly
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Test the API
```bash
# Health check
curl http://localhost:8000/health

# Start conversation
curl -X POST http://localhost:8000/start

# Send message (replace context with actual context from previous response)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a warehouse in Mumbai", "context": null}'
```

## API Endpoints

### POST /start
Start a new conversation
- **Request**: No body required
- **Response**: Greeting message + initial context

### POST /chat
Send message and get response
- **Request**: `{"message": "user message", "context": {conversation_context}}`
- **Response**: `{"response": "agent response", "context": {updated_context}, "conversation_complete": false}`

### GET /health
Health check endpoint

### GET /
API documentation and endpoint list

## Frontend Integration

### How Frontend Communicates with Backend

1. **Start Conversation** (Page Load)
   ```javascript
   const response = await fetch('/start', { method: 'POST' });
   const data = await response.json();
   // Store data.context in component state
   ```

2. **Send User Message**
   ```javascript
   const response = await fetch('/chat', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       message: userInput,
       context: storedContext  // Send current context
     })
   });
   const data = await response.json();
   // Update stored context with data.context
   ```

3. **Context Management**
   - Store conversation context in component state (React) or Vuex (Vue)
   - Send entire context with every request
   - Update context with each response
   - No database needed on frontend

### Example Integrations

1. **HTML/JavaScript**: See `frontend_example.html`
2. **React Component**: See `WarehouseDiscoveryChat.tsx`
3. **Python Client**: See `frontend_demo.py`

## Workflow Stages

The API guides users through a 3-step process:

1. **Location & Size** - Collect location and square footage requirements
2. **Land Classification** - Determine if industrial or commercial land is needed
3. **Additional Requirements** - Fire NOC, budget, structure type, etc.

## Context Structure

The conversation context includes:
```json
{
  "messages": [{"role": "user|assistant", "content": "message"}],
  "location_query": "bangalore",
  "size_min": 40000,
  "size_max": 60000,
  "land_type_industrial": false,
  "fire_noc_required": true,
  "workflow_stage": "specifics",
  "conversation_complete": false
}
```

## Error Handling

- **503**: Agent not initialized (missing OpenAI API key)
- **500**: Processing error (invalid input, API failure, etc.)
- **422**: Invalid request format

## Production Considerations

1. **CORS**: Configure allowed origins appropriately
2. **Rate Limiting**: Add request rate limiting
3. **Authentication**: Add user authentication if needed
4. **Monitoring**: Add logging and monitoring
5. **Database**: Add persistent storage for analytics

## Development

### Testing the API
```bash
# Run the demo client
python frontend_demo.py

# Or open the HTML example
open frontend_example.html
```

### Adding New Features
1. Modify workflow in `nodes.py` and `graph.py`
2. Update context structure in `api.py` if needed
3. Test with frontend examples

## Deployment

### Docker (Recommended)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Cloud Deployment
- **Heroku**: Use `Procfile` with `web: uvicorn api:app --host 0.0.0.0 --port $PORT`
- **AWS/GCP**: Deploy as container or serverless function
- **DigitalOcean**: Use App Platform with Python runtime

## Support

For questions or issues, contact the development team or refer to the API documentation at `http://localhost:8000/docs` when the server is running.