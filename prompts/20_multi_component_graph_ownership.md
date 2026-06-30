# Prompt 20: Relational Technical Ownership & Cognee-Driven ERA Code Metrics
Context: Technical ownership is currently constrained to a single component selection and a manually entered codebase percentage number. In reality, engineers own multiple features, microservices, and layers across various repositories. We must shift this to a multi-selection model and let Cognee calculate metrics dynamically.
Task: Redesign technical component mapping and refactor the Employee Risk Assessment (ERA) backend matrix.

Requirements:
1. **Multi-Component Selection Interface:**
   - In the employee management modal, replace the single component dropdown with a multi-select badge input (e.g., using a tag-input or searchable multi-select combobox).
   - Allow a single engineer to be linked to an unlimited number of system architectural assets or repository paths.
2. **Remove Hardcoded Code Share Percentage:** Completely strip out the manual numeric input box for code-share percentages from the UI.
3. **Cognee-Driven Analytics Engine (`backend/app/routes/analytics.py`):**
   - Refactor the `GET /api/analytics/era` calculation algorithm. Instead of reading a static scalar percentage from a database column, query the Cognee Multi-hop graph memory layer.
   - **Dynamic Calculation Rule:** Look up the total count of component nodes linked to the engineer vs. the network's global component count. Factor in the density of multi-hop links (e.g., number of open GitHub commits and unresolved Jira tickets connected to those specific nodes in Cognee).
   - Return this calculated complexity weight to the frontend ERA page as the new, mathematically grounded `Codebase Contribution Share %`.
4. **UI Update:** Ensure the analytics tables and radar charts seamlessly digest and display these dynamically computed values without requiring structural page redesigns.