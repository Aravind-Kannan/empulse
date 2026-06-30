# Prompt 5: Knowledge Risk Assessment (KRA) Network Visualizer
Context: The KRA represents a topological visualization of structural engineering dependencies to highlight operational silos.
Task: Implement the interactive graph visualizer page at `/kra`.

Requirements:
1. Backend: Build an API endpoint `/api/analytics/kra` returning nodes and links. Nodes represent Systems/Microservices or Engineers. Links model ownership or domain expertise.
2. Inject a Single Point of Failure (SPOF) condition: If a System Component node is connected to <= 1 Engineer node, tag that component model with `isSPOF: true`.
3. Frontend UI: Build an interactive visual interface using an SVG layout, HTML Canvas, or a lightweight wrapper (e.g., Vis.js / React Flow). Map system components as square nodes and engineers as circle nodes.
4. Dynamically alert users by rendering SPOF system component nodes in clear neon-red/orange warning styles.
5. Implement a side drawer overlay that smoothly slides open when any system component node is clicked, pulling down metadata (Description, linked documentation sources) and an inline interactive form selector to map an immediate backup engineer to break the operational silo.
