# Prompt 15: Dual-Tab Interactive Org Workspace with Drag-and-Drop
Context: The current organizational chart is rigid. For larger enterprises, managing structures requires both high-density data tables and intuitive visual layouts, with support for flexible grouping.
Task: Build a comprehensive, dual-tab organizational management interface at `/onboarding/org-setup` and `/settings/org-chart`.

Requirements:
1. **Dual-Tab Layout Wrapper:** Implement a clean tab switcher interface featuring two main modes: "List Grid View" and "Hierarchical Chart View".
2. **Tab 1: Interactive High-Density Table:**
   - Render a tree-style collapsible table listing all employees.
   - Implement drag-and-drop row functionality (using `@hello-pangea/dnd` or `@dnd-kit`). Dragging an employee row underneath another row dynamically re-assigns their line of reporting (`reportsTo`).
   - Group reporting lines beneath nested, toggleable rows so managers can collapse or expand sub-teams at a glance.
3. **Tab 2: Drag-and-Drop Visual Tree:**
   - Render the structural hierarchy using an interactive visual tree nodes layout.
   - Support fluid drag-and-drop actions natively inside the visual canvas to re-parent nodes, instantly recalculating and visually animating the reporting linkages.
4. **Custom Team/Group Tags:** Add functionality to select a cluster of individuals and assign them a custom "Team Name" attribute (e.g., "Platform Reliability Squad", "Core Payments"). Ensure these group labels are passed along as metadata fields inside Cognee node attributes.