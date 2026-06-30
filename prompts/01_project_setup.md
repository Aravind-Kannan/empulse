# Prompt 1: Multi-Repo Core Architecture Setup
Context: We are initializing a dual-stack monorepo for an engineering intelligence system.
Task: Configure the baseline workspace files for both the Next.js frontend and the FastAPI backend.

Requirements:
1. In `backend/requirements.txt`, add: fastapi, uvicorn, pydantic, cognee, sqlalchemy, psycopg2-binary, python-dotenv.
2. Create a foundational `backend/app/main.py` configuring FastAPI with CORS middleware pointing to `http://localhost:3000`.
3. In `frontend/package.json`, initialize a Next.js setup with React 19, Tailwind CSS, Lucide React, and Recharts.
4. Set up `frontend/src/app/layout.tsx` to include a global dark-mode theme layout (Slate/Zinc palette) featuring a persistent sidebar with matching icons navigation items: Dashboard, Employee Risk Assessment (ERA), Knowledge Risk Assessment (KRA), Incident Investigation (II), Employee Exit (EE), and Settings.
5. Create simple page stubs for each route displaying its header title.
