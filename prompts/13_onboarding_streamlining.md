# Prompt 13: Onboarding Streamlining & Multi-App Account Mapping Gateway
Context: The initial signup step is redundant because core user data is already gathered via the authentication dialogue boxes. Additionally, integrations need to be skippable, and we must resolve identity fragmentation (mapping different usernames/emails across GitHub, Jira, Slack, and Notion to a single employee entity).
Task: Refactor the onboarding flow entry logic and implement an Identity Mapping configuration screen.

Requirements:
1. **Streamline Onboarding Entry:** Eliminate the redundant first screen. When a new user completes the auth dialogue box, route them directly to the Integrations step inside `/onboarding`.
2. **Skippable Integrations:** Add a prominent "Skip for Now" action to the integrations step, allowing users to proceed to the workspace setup and configure apps later in the main settings hub.
3. **Dynamic Multi-App Mapping Model:**
   - On the backend, create an `EmployeeIdentity` model/table tracking alias mappings: `employee_id`, `provider` (github, jira, slack, notion), and `provider_username_or_id`.
   - Create a frontend configuration page at `/settings/identity-mapping`.
   - When a new application data source is connected, fetch its member list via API and display a mapping workspace. Render an intelligent reconciliation table listing all employees side-by-side with dropdown selectors for their respective GitHub handles, Jira emails, and Slack IDs to ensure Cognee merges multi-source graph nodes accurately.