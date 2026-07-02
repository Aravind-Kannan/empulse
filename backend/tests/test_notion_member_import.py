"""Notion workspace member import filters non-roster databases and rows."""

from app.services.notion_client import (
    fetch_notion_member_records,
    is_people_database_schema,
    parse_database_rows_to_records,
)


def test_is_people_database_schema_with_email_column():
    properties = {
        "Name": {"type": "title"},
        "Email": {"type": "email"},
        "Role": {"type": "select"},
    }
    assert is_people_database_schema(properties) is True


def test_is_people_database_schema_rejects_expense_tracker():
    properties = {
        "Name": {"type": "title"},
        "Amount": {"type": "number"},
        "Category": {"type": "select"},
    }
    assert is_people_database_schema(properties) is False


def test_parse_database_rows_skips_title_only_rows():
    rows = [
        {
            "id": "ea437189-07b0-8289-913e-010638b8ed56",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Groceries"}],
                },
                "Amount": {"type": "number", "number": 42},
            },
        }
    ]
    assert parse_database_rows_to_records(rows) == []


def test_parse_database_rows_keeps_real_email():
    rows = [
        {
            "id": "e8537189-07b0-83ec-8d75-0142a58df7cd",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Ramprasad R"}],
                },
                "Email": {"type": "email", "email": "ram@example.com"},
                "Role": {"type": "select", "select": {"name": "Engineer"}},
            },
        }
    ]
    records = parse_database_rows_to_records(rows)
    assert len(records) == 1
    assert records[0].name == "Ramprasad R"
    assert records[0].email == "ram@example.com"


def test_fetch_notion_member_records_without_db_ids_uses_workspace_only(monkeypatch):
    monkeypatch.setattr(
        "app.services.notion_client.discover_database_ids",
        lambda _token: ["expense-db-id"],
    )
    monkeypatch.setattr(
        "app.services.notion_client.query_database_pages",
        lambda *_args, **_kwargs: [
            {
                "id": "page-expense",
                "properties": {
                    "Name": {
                        "type": "title",
                        "title": [{"plain_text": "Bday Cash"}],
                    }
                },
            }
        ],
    )
    monkeypatch.setattr(
        "app.services.notion_client.fetch_notion_workspace_users",
        lambda _token: [
            type(
                "Record",
                (),
                {
                    "source": "notion",
                    "external_id": "user-1",
                    "name": "Ramprasad R",
                    "email": "ram@company.com",
                    "title": "Workspace Member",
                    "manager_email": None,
                },
            )()
        ],
    )

    from app.schemas.employee_master import MasterDataRecord

    workspace_record = MasterDataRecord(
        source="notion",
        external_id="user-1",
        name="Ramprasad R",
        email="ram@company.com",
        title="Workspace Member",
        manager_email=None,
    )
    monkeypatch.setattr(
        "app.services.notion_client.fetch_notion_workspace_users",
        lambda _token: [workspace_record],
    )

    records = fetch_notion_member_records("secret-token", database_ids=None)
    assert len(records) == 1
    assert records[0].email == "ram@company.com"
    assert records[0].name == "Ramprasad R"
