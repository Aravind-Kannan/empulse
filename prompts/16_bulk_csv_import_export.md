# Prompt 16: Bulk CSV Import, Export, & Re-upload Operations
Context: For mid-to-large-scale organizations, manually editing rows or moving nodes in a UI can become tedious. We need bulk operations to manage larger employee directories.
Task: Build a robust CSV export, parsing, and bulk validation system for the organizational chart workspace.

Requirements:
1. **Structure Export Routine:** Add an "Export Configuration as CSV" action button. This generates and downloads a structured file mapping the current state: `id, name, email, dynamic_role, team_name, reports_to_email_or_id`.
2. **Bulk Upload Parsing Engine:**
   - Implement a secure file upload dropzone supporting `.csv` files.
   - Build a client-side parser (using `papaparse`) or a dedicated backend processing endpoint `POST /api/org/bulk-upload` to ingest modified files.
3. **Data Validation & Diff Viewer:**
   - Before applying the upload globally, parse the CSV records to check for cyclical dependency errors (e.g., an engineer marked as reporting to someone who reports to them).
   - Display a brief "Changes Summary" layout listing new entries, modified fields, or updated reporting hierarchies.
4. **Cognee Mass Commit Sync:** Upon clicking "Apply Bulk Changes", clear old organizational graph linkages and trigger a bulk `cognee.add()` and `cognee.cognify()` execution layer to re-index the updated enterprise structure seamlessly.