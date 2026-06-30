# Prompt 23: Frontend Tenant Routing Guardrails & State Alignment
Context: With multi-tenancy running on the server, the frontend framework must cleanly isolate application state, headers, and UI parameters based on the authenticated session.
Task: Configure client-side API interceptors and protective navigation route guards.

Requirements:
1. **Global Auth & Tenant Provider Context:**
   - Implement a React Context or state hook (`useAuth`) tracking active parameters: `user`, `activeTenant`, and `authStatus`.
2. **Global Network Interceptor Guard:**
   - Update your centralized fetching framework or Axios instance wrapper to automatically pull the active tenant token and inject it as a bearer token header (`Authorization: Bearer <token>`) on all outbound backend API requests.
3. **Dynamic Workspace Layout Polish:**
   - Update the top navigation header or persistent side panel to render the active workspace tenant name dynamically (e.g., displaying "Acme Corp Workspace").
   - Include a secondary sub-account switcher dropdown within the settings sub-pane if a user profile is linked to multiple organizational client groups.