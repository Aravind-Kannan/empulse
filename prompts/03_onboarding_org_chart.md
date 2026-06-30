# Prompt 3: Interactive Onboarding Flow & Org Chart Editor
Context: New managers must complete a multi-step onboarding wizard to initialize their team workspace graph.
Task: Build out the `/onboarding` multi-page wizard component on the frontend.

Requirements:
1. Step 1 (Sign Up): Minimal mock auth layout transitioning into the onboarding wrapper.
2. Step 2 (Integrations): Form layout capturing Slack Bot Token and Notion API configuration keys, storing them cleanly in local react state or context.
3. Step 3 (Org Chart Setup): Render an interactive visual tree hierarchy pre-populated with 'Acme Company' (1 Manager -> 4 Engineers, 1 Support).
4. Allow users to click any employee node to pull up a modal editing their text fields, reassigned reporting structures, or specific technical ownership focuses.
5. Add a prominent 'Confirm & Ingest to Cognee' CTA button that stringifies the tree schema into a normalized JSON payload and dispatches it to the `/api/ingest/org-chart` backend endpoint. Upon success, redirect to `/dashboard`.
