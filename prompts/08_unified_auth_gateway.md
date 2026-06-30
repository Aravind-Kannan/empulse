Context: We need to wire up a high-fidelity landing/auth screen that dynamically determines if a user is a new manager requiring onboarding or an existing manager returning to their dashboard.
Task: Refactor the main root route (`/`) and implement authentication routing logic.

Requirements:
1. Update `frontend/src/app/page.tsx` to serve as a clean, enterprise landing page with a hero section ("Engineering Intelligence Powered by Cognee") and clear "Login" and "Get Started / Sign Up" CTAs.
2. Build a mock stateful Auth Modal or page handling toggles between Sign Up and Login.
3. Implement routing logic:
   - Clicking **Sign Up** routes the user directly to the `/onboarding` multi-page wizard.
   - Clicking **Login** bypasses onboarding and deep-links directly into the `/dashboard` workspace view.
4. Ensure global state tracking sets an `isAuthenticated` flag and records user session metadata to prevent unauthenticated access to sub-routes.