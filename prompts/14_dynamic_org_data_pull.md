# Prompt 14: Dynamic Employee Master Data Ingestion Pipeline
Context: Instead of relying on static hardcoded values, the system must utilize connected integration APIs (such as Slack, Jira, or Notion) to automatically fetch employee master records, roles, and structural hierarchies.
Task: Create the backend extraction routines and frontend ingestion state management.

Requirements:
1. **Dynamic Schema & Role Management:** Remove any hardcoded roles (e.g., 'Engineer', 'Support'). Allow roles to be dynamic strings pulled directly from external metadata or custom-inputted by the manager.
2. **Multi-Source Master Data Pull:**
   - Create a backend API endpoint `GET /api/integrations/fetch-users` that polls connected platforms (e.g., Slack's `users.list` or Jira's user management endpoints).
   - Aggregate these records into a unified "Employee Master Data" payload containing names, primary emails, titles, and structural reporting indicators if present.
3. **Onboarding Integration:** If the user connects integrations during onboarding, substitute the static 'Acme Company' default dataset with this freshly pulled live master data to seed the organizational structure layout.