# LLM Agent Usage SOP

## Purpose
Provide natural language interface for querying inventory and jobs via LM Studio.

## Inputs
- User natural language query
- LM Studio connection at localhost:1234

## Tools
- `src/wired_part/agent/client.py` — OpenAI-compatible client
- `src/wired_part/agent/handler.py` — tool execution dispatcher
- `src/wired_part/agent/tools.py` — function definitions

## Configuration
1. Install and run LM Studio
2. Load a compatible model (7B+ parameters recommended)
3. Start the local server (default port 1234)
4. Configure `.env` with `LM_STUDIO_BASE_URL`

## Available Tools
- `search_parts` — keyword search across inventory
- `get_part_details` — full info for a specific part number
- `get_job_parts` — parts assigned to a job
- `get_low_stock_parts` — items below minimum quantity
- `get_inventory_summary` — totals and value
- `get_job_summary` — job counts by status

## Query Handling Flow
1. User sends message via chat UI
2. Message sent to LLM with system prompt + tools
3. LLM may call tools — handler executes against repository
4. Tool results returned to LLM
5. LLM generates final response
6. Response displayed in chat (runs in QThread for responsiveness)

## Security
- Agent is READ-ONLY — no database modifications
- All queries are parameterized (no SQL injection risk)
- Runs locally — no data leaves the machine

## Error Handling
- Connection failed: Status shows "Disconnected", send disabled
- Model not loaded: Connection check fails gracefully
- Timeout: Configurable via LM_STUDIO_TIMEOUT env var
