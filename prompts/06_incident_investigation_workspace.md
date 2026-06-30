# Prompt 6: Incident Investigation (II) 3-Panel Workspace
Context: When high-priority system alerts hit the workspace, managers use a multi-hop semantic graph view to evaluate dependencies and isolate root causes.
Task: Create the mission-critical 3-panel collaborative layout at `/investigation`.

Requirements:
1. History Mode: Top/Pre-view displaying past history cards filtered by status tabs (Open, Investigating, Waiting for Input, Resolved, Closed) showing system scopes and linked Jira ID strings.
2. Active Workspace (Fluid 3-Panel Desktop Grid Layout):
   - Left Panel (Chat Interface): High-fidelity conversational dialogue field parsing user input (e.g., "Payment Gateway is timing out. Jira: PROJ-992") with pre-baked chip suggestions tracking operational updates. Connect this to a backend mock streaming response simulating Cognee graph traversal results.
   - Center Panel (Core Diagnostics): Renders extracted 'Probable Root Cause', a radial gauge showing 'Confidence Score' (derived via mock graph distance algorithms), 'Immediate Emergency Workaround', and a control dropdown to mutate active incident states.
   - Right Panel (Context & Experts): Displays recommended Subject Matter Experts (SMEs) with calculated compatibility scores and real-time status indicators, followed by searchable references to past Slack threads, Notion pages, and postmortems.
