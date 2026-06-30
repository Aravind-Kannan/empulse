# Prompt 18: Dynamic Role Evolution Engine & Cognee Edge Lifecycle
Context: Roles within the platform cannot be hardcoded or treat people statically (e.g., an engineer today can be promoted to a manager tomorrow). The system must treat roles as dynamic metadata fields and update relationship predicates inside Cognee dynamically.
Task: Refactor the backend schema models and Cognee edge assignment logic to handle dynamic career trajectories.

Requirements:
1. **Database Schema Refactor:**
   - In `backend/app/models/`, verify that the `Employee` model defines `role` simply as a customizable string variable (`role: str`), completely decoupling it from any hardcoded enums.
   - Implement a history tracking table or array log (`RoleHistory`) to store a timeline of changes (`old_role`, `new_role`, `changed_at`).
2. **Dynamic Cognee Graph Edge Re-typing:**
   - When an employee's role changes from an individual contributor role to a managerial role, the backend must update their structural graph properties.
   - If an employee is assigned direct reports, dynamically drop old individual contributor edge constraints and execute `cognee.add()` to build new custom relational predicates (e.g., creating a `manages` or `directReportOf` multi-hop edge relationship inside the graph memory layer).
3. **Frontend Role Configuration UI:**
   - On the employee modification modals across both the table view and the visual canvas, replace static dropdown selections with an editable, auto-suggest combobox input.
   - Allow managers to either pick from roles currently active within the company or type in a brand new, custom title string on the fly.
4. **State Sync Validation:** Verify that updating an employee's role or reporting structure immediately cascades into the **Employee Risk Assessment (ERA)** and **Knowledge Risk Assessment (KRA)** engines, shifting ownership and metrics balances globally across the application.