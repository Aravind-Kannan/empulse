"""Cognee SQLite metadata bootstrap on fresh installs (no packaged template)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

from app.config import Settings, ensure_cognee_metadata_database


def test_ensure_cognee_metadata_skips_when_template_missing(tmp_path: Path) -> None:
    settings = Settings(
        cognee_system_root=str(tmp_path / ".cognee_system"),
        cognee_data_root=str(tmp_path / ".data_storage"),
        cognee_cache_root=str(tmp_path / ".cognee_cache"),
    )
    db_path = Path(settings.cognee_system_root) / "databases" / "cognee_db"

    with patch("app.config._cognee_metadata_template_path", return_value=None):
        ensure_cognee_metadata_database(settings)

    assert not db_path.exists()


def test_ensure_cognee_metadata_copies_template_when_present(tmp_path: Path) -> None:
    settings = Settings(
        cognee_system_root=str(tmp_path / ".cognee_system"),
        cognee_data_root=str(tmp_path / ".data_storage"),
        cognee_cache_root=str(tmp_path / ".cognee_cache"),
    )
    db_path = Path(settings.cognee_system_root) / "databases" / "cognee_db"
    template = tmp_path / "template_cognee_db"
    with sqlite3.connect(template) as conn:
        conn.executescript(
            """
            CREATE TABLE datasets (id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT NOT NULL);
            CREATE TABLE acls (id TEXT PRIMARY KEY);
            """
        )
        conn.execute("INSERT INTO datasets (id, name) VALUES ('d1', 'seed')")
        conn.commit()

    with patch("app.config._cognee_metadata_template_path", return_value=template):
        ensure_cognee_metadata_database(settings)

    assert db_path.is_file()
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {"datasets", "users", "acls"}.issubset(tables)
