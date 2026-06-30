# Prompt 25: Deep Integration Testing & Automated Error Recovery Loop for Notion
Context: To guarantee the production readiness of our Notion ingestion engine, we need an iterative, self-healing test environment. This script runs a targeted data payload through the Notion integration, catches format or API edge cases, and traces exactly how Cognee handles unstructured text conversion.
Task: Create a dedicated diagnostic script `backend/scripts/debug_notion_pipeline.py` and an interactive step-by-step telemetry panel in the frontend under `/settings/notion-debugger`.

Requirements:

1. **Automated Integration Health Checks:**
   - Implement an active connectivity checker that queries the Notion API root (`https://api.notion.com/v1/users/me`) to validate token status, permissions, and database structural mapping before running the payload sync.
   - Return descriptive, friendly error payloads to the client if the integration token lacks page-read permissions or is improperly formatted.

2. **Granular Telemetry & Stage Tracing:**
   - In the script, wrap the document sync flow inside an explicit tracing dictionary structure:
     - **Stage 1:** Fetching block metrics from Notion (Tracking text blocks, headers, and bullet arrays).
     - **Stage 2:** Sanitizing text data payloads (Clearing markdown inconsistencies, extracting raw names/tokens).
     - **Stage 3:** Cognee Vector Insertion (`cognee.add()`).
     - **Stage 4:** Multi-hop Triangulation & Semantic Processing (`cognee.cognify()`).
   - For every stage, calculate and write execution runtimes and validation statuses to an active JSON log block (`backend/data/notion_debug_state.json`).

3. **Frontend Diagnostics & Resolution Terminal (`/settings/notion-debugger`):**
   - Build a clean layout showing a split-screen configuration:
     - **Left Side:** A simple markdown text preview pane displaying the test document data pulled down from the Notion integration.
     - **Right Side:** A rich live diagnostic grid tracking the 4 stages of pipeline processing. Each box must render status animations (`Idle` ⚪, `Syncing` 🔵, `Success` 🟢, or `Failed` 🔴).
   - If a step fails, display an inline error trace window along with a predictive "Recommended Fix" chip action (e.g., "Invalid OAuth Token Scope Detected", "Cognee Schema Mismatch - click to reset graph memory").

4. **Retry & Validation Engine:**
   - Include a "Force Re-Sync & Clear Cache" action toggle button that clears old vector fragments and forces a clean iteration loop, enabling the developer to tweak Notion page variables and view live updates instantly without crashing backend server threads.