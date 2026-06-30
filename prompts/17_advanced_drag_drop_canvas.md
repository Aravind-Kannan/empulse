# Prompt 17: High-Fidelity Drag-and-Drop Visual Org Chart Canvas
Context: The hierarchical org chart view needs a highly fluid, responsive, and visually modern drag-and-drop interface capable of handling smooth layout transitions when team nodes are re-parented.
Task: Implement an advanced visual canvas using a robust interactive graph/tree layout library (such as React Flow, Vis.js, or d3-hierarchy with custom drag handlers).

Requirements:
1. **Interactive Visual Nodes:** Render every employee as an individual visual card node showing their name, avatar, dynamic role, and assigned team group tag.
2. **Smooth Re-Parenting Drag-and-Drop:**
   - Allow users to click and drag an employee node card. As they hover over another node card, highlight the target card as a potential new manager/parent.
   - On drop, instantly recalculate the tree path link lines, animate the nodes smoothly into their new balanced layout positions, and update the internal configuration state array.
3. **Prevent Structural Graph Breaks:** Implement real-time structural boundary guardrails. If a user attempts to drag a manager node underneath one of their own direct or indirect reports, cancel the operation, snap the node back, and display a temporary warning toast ("Cyclical reporting lines are not allowed").
4. **Canvas Navigation Controls:** Add utility controls for the canvas: Zoom In, Zoom Out, Fit to Screen, and a search input bar that flashes/centers the viewport onto a specific employee node when typed.