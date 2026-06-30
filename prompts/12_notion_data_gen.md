Context: We need an end-to-end simulation utility to validate our Notion integration and witness exactly how Cognee builds multi-hop semantic graphs from raw documents.
Task: Create a unified backend script `backend/scripts/test_notion_cognee.py` and an accompanying visual debugging view at `/settings/graph-debugger`.

Requirements:

1. **Ollama Data Generation Engine:**
   - Inside the script, use `requests` or the `ollama` Python library to interact with a local Ollama instance (defaulting to `llama3` or `mistral`).
   - Write a structured prompt to Ollama to generate mock engineering documentation for 'Acme Company'. It must generate 3 highly detailed, distinct documents:
     - An architecture design review (e.g., "Payment Gateway Architecture & Failure Modes").
     - An incident postmortem (e.g., "Postmortem: Auth Service Redis Cache Outage").
     - A team rotation/handover wiki page listing component owners.
   - Ensure the generated text explicitly references engineering names (e.g., Lisa Wang, Mike Chen) and system links to make it perfect for graph extraction.

2. **Notion API Sync Writer:**
   - Use the standard `client-notion` or raw `requests` against `https://api.notion.com/v1/pages` using the integration tokens set during onboarding.
   - Programmatically create these 3 pages inside the targeted Notion database or workspace root.

3. **Cognee Pipeline Ingestion Trigger:**
   - Immediately following a successful Notion upload, pull the text data back down (simulating a Notion webhook or sync poll).
   - Feed these raw text payloads into Cognee using `cognee.add()` and run `await cognee.cognify()`.

4. **Frontend Graph State Visualizer (`/settings/graph-debugger`):**
   - Create a clean frontend visual debugging page. 
   - Expose a button "Run End-to-End Notion -> Cognee Simulation Pipeline". Clicking it hits a new backend endpoint `/api/test/run-simulation`.
   - Below the button, render a live textual terminal log showing progress: `[Ollama generating data...] -> [Writing to Notion...] -> [Cognee Extracting Triples...] -> [Graph Built Successfully!]`.
   - Integrate a simple visual node map underneath to reveal the extracted Cognee graph vectors (Entities & their relational edges like `Lisa Wang -> AUTHOR_OF -> Redis Postmortem -> IMPACTS -> Auth Service`).