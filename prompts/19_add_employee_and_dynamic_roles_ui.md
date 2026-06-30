# Prompt 19: Dynamic Inline Role Creation & "Add Employee" Canvas Control
Context: The current edit modal hardcodes roles in a static dropdown, blocking updates or custom titles. Additionally, there is no quick way to scale the team by creating a new node directly on the interface.
Task: Update the editing modal and add an inline node creation feature to both the visual canvas and the table view.

Requirements:
1. **Dynamic Role Combobox:**
   - Replace the static role dropdown select menu with a search-and-add combobox input. 
   - It must pool and list all unique role strings currently used across the organization. If a user types a new role title that doesn't exist yet (e.g., "Principal Infrastructure Architect"), display an inline action: `Create new role: "..."`.
2. **"Add Employee" Flow:**
   - Add a floating action button `(+) Add Employee` to the top controls of both the Hierarchical Canvas and the Table View.
   - Clicking it opens a modal requesting basic details: Name, Email, Dynamic Role, Team Group Name, and a "Reports To" supervisor dropdown populated from the existing staff list.
3. **Canvas State Insertion:** On saving, inject the new node immediately into the active client state tree, trigger an automated layout re-balance, and map it into the temporary save structure before exporting to Cognee.