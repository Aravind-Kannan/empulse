MOCK_GITHUB_ACTIVITY = [
    {
        "pr_number": 482,
        "commit_sha": "a1b2c3d4",
        "author_employee_id": "emp-eng-001",
        "branch": "main",
        "files": [
            {
                "path": "services/payments/checkout.py",
                "loc_added": 42,
                "loc_removed": 8,
                "component_id": "comp-payments",
            },
            {
                "path": "services/payments/refunds.py",
                "loc_added": 18,
                "loc_removed": 3,
                "component_id": "comp-payments",
            },
        ],
    },
    {
        "pr_number": 491,
        "commit_sha": "e5f6g7h8",
        "author_employee_id": "emp-eng-002",
        "branch": "main",
        "files": [
            {
                "path": "services/auth/session.py",
                "loc_added": 27,
                "loc_removed": 11,
                "component_id": "comp-auth",
            },
        ],
    },
    {
        "pr_number": 503,
        "commit_sha": "i9j0k1l2",
        "author_employee_id": "emp-eng-004",
        "branch": "feature/webhooks",
        "files": [
            {
                "path": "services/notifications/webhook_dispatcher.py",
                "loc_added": 64,
                "loc_removed": 5,
                "component_id": "comp-notifications",
            },
        ],
    },
]

MOCK_JIRA_ISSUES = [
    {
        "ticket_id": "ENG-142",
        "issue_type": "Bug",
        "priority": "High",
        "status": "In Progress",
        "assignee_employee_id": "emp-eng-002",
        "component_id": "comp-auth",
        "project_key": "ENG",
        "description": (
            "Task: Fix session token rotation inside the authentication-service. "
            "Assignee: @SarahDev. Redis connection pool exhaustion causes Auth Service "
            "timeouts that cascade into Payment Gateway checkout failures."
        ),
    },
    {
        "ticket_id": "ENG-156",
        "issue_type": "Task",
        "priority": "Medium",
        "status": "Open",
        "assignee_employee_id": "emp-eng-001",
        "component_id": "comp-payments",
        "project_key": "ENG",
        "description": (
            "Task: Migrate database pools inside the authentication-service. "
            "Assignee: @SarahDev. Payment Gateway settlement latency depends on "
            "Auth Service connection pooling configuration."
        ),
    },
    {
        "ticket_id": "ENG-180",
        "issue_type": "Epic",
        "priority": "High",
        "status": "In Progress",
        "assignee_employee_id": "emp-eng-001",
        "component_id": "comp-payments",
        "project_key": "ENG",
        "description": (
            "Epic: Modernize Payment Gateway webhook reconciliation. "
            "Spans authentication-service, notification-hub, and payments core."
        ),
    },
    {
        "ticket_id": "OPS-88",
        "issue_type": "Bug",
        "priority": "Critical",
        "status": "Blocked",
        "assignee_employee_id": "emp-eng-003",
        "component_id": "comp-payments",
        "project_key": "OPS",
        "description": (
            "Bug: Payment Gateway provider timeout during peak traffic. "
            "Blocks checkout pipeline. Requires authentication-service health check."
        ),
    },
    {
        "ticket_id": "ENG-161",
        "issue_type": "Task",
        "priority": "Low",
        "status": "Done",
        "assignee_employee_id": "emp-eng-004",
        "component_id": "comp-notifications",
        "project_key": "ENG",
        "description": (
            "Task: Add webhook retry policy to notification-hub dispatcher."
        ),
    },
    {
        "ticket_id": "ENG-201",
        "issue_type": "Bug",
        "priority": "High",
        "status": "Open",
        "assignee_employee_id": None,
        "component_id": "comp-payments",
        "project_key": "ENG",
        "description": (
            "Bug: Unassigned — refund reconciliation job stalls in Payment Gateway."
        ),
    },
    {
        "ticket_id": "ENG-202",
        "issue_type": "Bug",
        "priority": "Critical",
        "status": "Open",
        "assignee_employee_id": None,
        "component_id": "comp-auth",
        "project_key": "ENG",
        "description": (
            "Bug: Unassigned — Auth Service session store corruption after deploy."
        ),
    },
    {
        "ticket_id": "OPS-91",
        "issue_type": "Bug",
        "priority": "High",
        "status": "Open",
        "assignee_employee_id": None,
        "component_id": "comp-payments",
        "project_key": "OPS",
        "description": (
            "Bug: Unassigned — Payment Gateway settlement batch timeout."
        ),
    },
    {
        "ticket_id": "PLAT-44",
        "issue_type": "Task",
        "priority": "Medium",
        "status": "Open",
        "assignee_employee_id": "emp-eng-002",
        "component_id": "comp-auth",
        "project_key": "PLAT",
        "description": (
            "Task: Harden authentication-service rate limits for internal service mesh."
        ),
    },
]
