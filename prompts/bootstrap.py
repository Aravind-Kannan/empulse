import os

# Define project structure
directories = [
    "backend/app/routes",
    "frontend/src/app/dashboard",
    "frontend/src/app/era",
    "frontend/src/app/kra",
    "frontend/src/app/investigation",
    "frontend/src/app/exit",
    "frontend/src/app/onboarding",
    "frontend/src/components",
    "frontend/src/lib",
    "prompts"
]

for folder in directories:
    os.makedirs(folder, exist_ok=True)

# Content dictionary for file generation
files = {}

# ----------------------------------------------------
# PROMPT 1: PROJECT SETUP & CONFIGURATIONS
# ----------------------------------------------------
files["prompts/01_project_setup.md"] = """# Prompt 1: Multi-Repo Core Architecture Setup
Context: We are initializing a dual-stack monorepo for an engineering intelligence system.
Task: Configure the baseline workspace files for both the Next.js frontend and the FastAPI backend.

Requirements:
1. In `backend/requirements.txt`, add: fastapi, uvicorn, pydantic, cognee, sqlalchemy, psycopg2-binary, python-dotenv.
2. Create a foundational `backend/app/main.py` configuring FastAPI with CORS middleware pointing to `http://localhost:3000`.
3. In `frontend/package.json`, initialize a Next.js setup with React 19, Tailwind CSS, Lucide React, and Recharts.
4. Set up `frontend/src/app/layout.tsx` to include a global dark-mode theme layout (Slate/Zinc palette) featuring a persistent sidebar with matching icons navigation items: Dashboard, Employee Risk Assessment (ERA), Knowledge Risk Assessment (KRA), Incident Investigation (II), Employee Exit (EE), and Settings.
5. Create simple page stubs for each route displaying its header title.
"""

# ----------------------------------------------------
# PROMPT 2: DB & COGNEE BACKEND ENGINE
# ----------------------------------------------------
files["prompts/02_db_cognee_backend.md"] = """# Prompt 2: Database Schema & Cognee Graph Initialization
Context: The platform runs on a hybrid PostgreSQL operational layer and a Cognee knowledge graph memory layer.
Task: Code the data ingestion pipelines, mock schemas, and Cognee integration routines.

Requirements:
1. In `backend/app/config.py`, initialize Cognee layout setup parameters. Create a placeholder async utility to execute `cognee.add()` and `cognee.cognify()`.
2. Define a Pydantic user/org schema modeling Acme Company: 1 Manager, 4 Engineers, 1 Support.
3. Build backend data models representing:
   - Employee (id, name, role, email, tenure_years)
   - Component (id, name, description, open_tasks_count, unresolved_incidents)
   - Assignment / Knowledge Mapping (employee_id, component_id, codebase_share_pct)
4. Implement a POST route `/api/ingest/org-chart` that receives the validated JSON mapping from the frontend, uses Cognee to dynamically connect these entity nodes via custom edges (`reportsTo`, `manages`, `ownsComponent`), and persists operational attributes to PostgreSQL.
"""

# ----------------------------------------------------
# PROMPT 3: VISUAL ONBOARDING & ORG CHART
# ----------------------------------------------------
files["prompts/03_onboarding_org_chart.md"] = """# Prompt 3: Interactive Onboarding Flow & Org Chart Editor
Context: New managers must complete a multi-step onboarding wizard to initialize their team workspace graph.
Task: Build out the `/onboarding` multi-page wizard component on the frontend.

Requirements:
1. Step 1 (Sign Up): Minimal mock auth layout transitioning into the onboarding wrapper.
2. Step 2 (Integrations): Form layout capturing Slack Bot Token and Notion API configuration keys, storing them cleanly in local react state or context.
3. Step 3 (Org Chart Setup): Render an interactive visual tree hierarchy pre-populated with 'Acme Company' (1 Manager -> 4 Engineers, 1 Support).
4. Allow users to click any employee node to pull up a modal editing their text fields, reassigned reporting structures, or specific technical ownership focuses.
5. Add a prominent 'Confirm & Ingest to Cognee' CTA button that stringifies the tree schema into a normalized JSON payload and dispatches it to the `/api/ingest/org-chart` backend endpoint. Upon success, redirect to `/dashboard`.
"""

# ----------------------------------------------------
# PROMPT 4: EMPLOYEE RISK ASSESSMENT (ERA)
# ----------------------------------------------------
files["prompts/04_employee_risk_assessment.md"] = """# Prompt 4: Employee Risk Assessment (ERA) Analytics
Context: The ERA dashboard surfaces structural team vulnerabilities, burnout indexes, and knowledge bottlenecks.
Task: Build the full backend metrics engine and frontend analytics layout for `/era`.

Requirements:
1. Backend: Implement a GET endpoint `/api/analytics/era` returning metrics for Acme team members. Calculate a synthetic `Risk Factor Score` (0-100%) applying a weighted formula: `(Unresolved Issues * 5) + (Open Tasks * 3) + (Undocumented Solved Incidents * 10) + (Codebase Contribution Share % * 0.4)`. Ensure edge cases cap at 100%.
2. Frontend UI: Render an elegant, high-performance data table displaying all employee rows, their raw tracking counts, and color-coded risk flags (Red > 75%, Amber 40-75%, Green < 40%).
3. Integrate a Recharts Radar Chart or Bar Chart parsing out individual metric distributions to visually isolate exactly *why* a particular engineer has a high risk score.
4. Add interactive top-bar layout toggles allowing immediate sorting by 'Highest Risk' or 'Highest Code Ownership'.
"""

# ----------------------------------------------------
# PROMPT 5: KNOWLEDGE RISK VISUALIZER (KRA)
# ----------------------------------------------------
files["prompts/05_knowledge_graph_visualizer.md"] = """# Prompt 5: Knowledge Risk Assessment (KRA) Network Visualizer
Context: The KRA represents a topological visualization of structural engineering dependencies to highlight operational silos.
Task: Implement the interactive graph visualizer page at `/kra`.

Requirements:
1. Backend: Build an API endpoint `/api/analytics/kra` returning nodes and links. Nodes represent Systems/Microservices or Engineers. Links model ownership or domain expertise.
2. Inject a Single Point of Failure (SPOF) condition: If a System Component node is connected to <= 1 Engineer node, tag that component model with `isSPOF: true`.
3. Frontend UI: Build an interactive visual interface using an SVG layout, HTML Canvas, or a lightweight wrapper (e.g., Vis.js / React Flow). Map system components as square nodes and engineers as circle nodes.
4. Dynamically alert users by rendering SPOF system component nodes in clear neon-red/orange warning styles.
5. Implement a side drawer overlay that smoothly slides open when any system component node is clicked, pulling down metadata (Description, linked documentation sources) and an inline interactive form selector to map an immediate backup engineer to break the operational silo.
"""

# ----------------------------------------------------
# PROMPT 6: THREE-PANEL INCIDENT INVESTIGATION
# ----------------------------------------------------
files["prompts/06_incident_investigation_workspace.md"] = """# Prompt 6: Incident Investigation (II) 3-Panel Workspace
Context: When high-priority system alerts hit the workspace, managers use a multi-hop semantic graph view to evaluate dependencies and isolate root causes.
Task: Create the mission-critical 3-panel collaborative layout at `/investigation`.

Requirements:
1. History Mode: Top/Pre-view displaying past history cards filtered by status tabs (Open, Investigating, Waiting for Input, Resolved, Closed) showing system scopes and linked Jira ID strings.
2. Active Workspace (Fluid 3-Panel Desktop Grid Layout):
   - Left Panel (Chat Interface): High-fidelity conversational dialogue field parsing user input (e.g., "Payment Gateway is timing out. Jira: PROJ-992") with pre-baked chip suggestions tracking operational updates. Connect this to a backend mock streaming response simulating Cognee graph traversal results.
   - Center Panel (Core Diagnostics): Renders extracted 'Probable Root Cause', a radial gauge showing 'Confidence Score' (derived via mock graph distance algorithms), 'Immediate Emergency Workaround', and a control dropdown to mutate active incident states.
   - Right Panel (Context & Experts): Displays recommended Subject Matter Experts (SMEs) with calculated compatibility scores and real-time status indicators, followed by searchable references to past Slack threads, Notion pages, and postmortems.
"""

# ----------------------------------------------------
# PROMPT 7: OFFBOARDING GENERATOR & MANAGER DASHBOARD
# ----------------------------------------------------
files["prompts/07_offboarding_manager_dashboard.md"] = """# Prompt 7: Employee Exit (EE) Handover Generator & Manager Cockpit
Context: Wrapping the system requires linking individual module states back into a primary operations deck and handling asset transition flows.
Task: Complete the `/exit` offboarding view and the parent `/dashboard` control view.

Requirements:
1. Employee Exit `/exit`: Build a view featuring an employee selector dropdown. Selecting an engineer calls `/api/exit/handover?id=X`.
2. The backend queries the Cognee layer for everything that individual owns or touches, formatting a valid Markdown response split into headers: "System Components Requiring Transfer", "Active Open Tasks", and "Undocumented Hotfixes Needing Writeups".
3. Provide a clear frontend button action to copy or download this file directly as an asset pack.
4. Main Landing Dashboard `/dashboard`: Build high-level metric aggregate cards (Average Attrition Rate: 12%, Average Tenure: 2.4 years, Open Incident Counters, Count of Active SPOFs).
5. Add a sub-settings config interface enabling toggle-switches and cron selectors for automatic Weekly Executive Email Digests.
6. Interlink state variables using a shared state provider (React Context or light state framework) ensuring changes in one workspace (e.g., resolving an incident or assigning an SME) cascade across charts globally.
"""

# Write base configuration templates
files["backend/requirements.txt"] = "fastapi>=0.110.0\nuvicorn>=0.28.0\npydantic>=2.6.0\ncognee>=0.1.0\nsqlalchemy>=2.0.0\npsycopg2-binary>=2.9.0\npython-dotenv>=1.0.0\n"
files["backend/app/__init__.py"] = ""
files["backend/app/main.py"] = "from fastapi import FastAPI\nfrom fastapi.middleware.cors import CORSMiddleware\n\napp = FastAPI(title='Cognee Engineering Intelligence API')\n\napp.add_middleware(\n    CORSMiddleware,\n    allow_origins=['http://localhost:3000'],\n    allow_credentials=True,\n    allow_methods=['*'],\n    allow_headers=['*'],\n)\n\n@app.get('/')\ndef read_root():\n    return {'status': 'healthy', 'engine': 'Cognee Knowledge Graph'}\n"

# Write out files
for path, content in files.items():
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

print("🚀 Success! Your Cognee-Powered workspace generation blueprint has been created.")
print("👉 Type 'cd prompts' to see the exact sequence files to feed into Cursor Composer (Cmd+I / Ctrl+I).")