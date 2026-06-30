# Prompt 7: Employee Exit (EE) Handover Generator & Manager Cockpit
Context: Wrapping the system requires linking individual module states back into a primary operations deck and handling asset transition flows.
Task: Complete the `/exit` offboarding view and the parent `/dashboard` control view.

Requirements:
1. Employee Exit `/exit`: Build a view featuring an employee selector dropdown. Selecting an engineer calls `/api/exit/handover?id=X`.
2. The backend queries the Cognee layer for everything that individual owns or touches, formatting a valid Markdown response split into headers: "System Components Requiring Transfer", "Active Open Tasks", and "Undocumented Hotfixes Needing Writeups".
3. Provide a clear frontend button action to copy or download this file directly as an asset pack.
4. Main Landing Dashboard `/dashboard`: Build high-level metric aggregate cards (Average Attrition Rate: 12%, Average Tenure: 2.4 years, Open Incident Counters, Count of Active SPOFs).
5. Add a sub-settings config interface enabling toggle-switches and cron selectors for automatic Weekly Executive Email Digests.
6. Interlink state variables using a shared state provider (React Context or light state framework) ensuring changes in one workspace (e.g., resolving an incident or assigning an SME) cascade across charts globally.
