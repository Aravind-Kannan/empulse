# Prompt 4: Employee Risk Assessment (ERA) Analytics
Context: The ERA dashboard surfaces structural team vulnerabilities, burnout indexes, and knowledge bottlenecks.
Task: Build the full backend metrics engine and frontend analytics layout for `/era`.

Requirements:
1. Backend: Implement a GET endpoint `/api/analytics/era` returning metrics for Acme team members. Calculate a synthetic `Risk Factor Score` (0-100%) applying a weighted formula: `(Unresolved Issues * 5) + (Open Tasks * 3) + (Undocumented Solved Incidents * 10) + (Codebase Contribution Share % * 0.4)`. Ensure edge cases cap at 100%.
2. Frontend UI: Render an elegant, high-performance data table displaying all employee rows, their raw tracking counts, and color-coded risk flags (Red > 75%, Amber 40-75%, Green < 40%).
3. Integrate a Recharts Radar Chart or Bar Chart parsing out individual metric distributions to visually isolate exactly *why* a particular engineer has a high risk score.
4. Add interactive top-bar layout toggles allowing immediate sorting by 'Highest Risk' or 'Highest Code Ownership'.
