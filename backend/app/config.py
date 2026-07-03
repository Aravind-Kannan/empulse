import os
import shutil
import sqlite3
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(BACKEND_ROOT / ".env")


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/empulse"

    llm_provider: str = "ollama"
    llm_model: str = "llama3.2"
    llm_endpoint: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"

    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    embedding_endpoint: str = "http://localhost:11434/api/embed"
    embedding_api_key: str = "ollama"
    huggingface_tokenizer: str = "nomic-ai/nomic-embed-text-v1.5"

    cognee_data_root: str = str(BACKEND_ROOT / ".data_storage")
    cognee_system_root: str = str(BACKEND_ROOT / ".cognee_system")
    cognee_cache_root: str = str(BACKEND_ROOT / ".cognee_cache")
    cognee_dataset_name: str = "empulse_org_chart"
    cognee_vector_db_provider: str = "lancedb"
    cognee_graph_db_provider: str = "neo4j"
    cognee_graph_db_url: str = "bolt://localhost:7687"
    cognee_graph_db_username: str = "neo4j"
    cognee_graph_db_password: str = "pleaseletmein"
    cognee_graph_db_name: str = "neo4j"
    cognee_backend_access_control: bool = False

    internal_debug_key: str = ""

    jwt_secret: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_expire_seconds: int = 60 * 60 * 24 * 7
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"

    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    era_v2_scoring: bool = True

    # When unset, enrichment auto-skips for Ollama (local models fail Cognee summarization schema).
    cognify_enrichment_enabled: bool | None = None

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


def _apply_runtime_env(settings: Settings) -> None:
    os.environ.setdefault(
        "ENABLE_BACKEND_ACCESS_CONTROL",
        "true" if settings.cognee_backend_access_control else "false",
    )
    os.environ.setdefault("CACHE_ROOT_DIRECTORY", settings.cognee_cache_root)
    os.environ.setdefault("DATABASE_URL", settings.database_url)
    os.environ.setdefault("LLM_PROVIDER", settings.llm_provider)
    os.environ.setdefault("LLM_MODEL", settings.llm_model)
    os.environ.setdefault("LLM_ENDPOINT", settings.llm_endpoint)
    os.environ.setdefault("LLM_API_KEY", settings.llm_api_key)
    os.environ.setdefault("EMBEDDING_PROVIDER", settings.embedding_provider)
    os.environ.setdefault("EMBEDDING_MODEL", settings.embedding_model)
    os.environ.setdefault("EMBEDDING_DIMENSIONS", str(settings.embedding_dimensions))
    os.environ.setdefault("EMBEDDING_ENDPOINT", settings.embedding_endpoint)
    os.environ.setdefault("EMBEDDING_API_KEY", settings.embedding_api_key)
    os.environ.setdefault("HUGGINGFACE_TOKENIZER", settings.huggingface_tokenizer)
    os.environ.setdefault("GRAPH_DATABASE_PROVIDER", settings.cognee_graph_db_provider)
    os.environ.setdefault("GRAPH_DATABASE_URL", settings.cognee_graph_db_url)
    os.environ.setdefault("GRAPH_DATABASE_USERNAME", settings.cognee_graph_db_username)
    os.environ.setdefault("GRAPH_DATABASE_PASSWORD", settings.cognee_graph_db_password)
    os.environ.setdefault("GRAPH_DATABASE_NAME", settings.cognee_graph_db_name)
    os.environ.setdefault("GRAPH_DATASET_DATABASE_HANDLER", "neo4j")
    os.environ.setdefault("VECTOR_DATASET_DATABASE_HANDLER", "lancedb")


_apply_runtime_env(Settings())

import cognee


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _cognee_metadata_is_healthy(db_path: Path) -> bool:
    if not db_path.is_file() or db_path.stat().st_size < 1024:
        return False
    try:
        with sqlite3.connect(db_path) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        return {"datasets", "users", "acls"}.issubset(tables)
    except sqlite3.Error:
        return False


def ensure_cognee_metadata_database(settings: Settings) -> None:
    """
    Seed Cognee's SQLite metadata DB when missing or left in a broken state.

    Fresh Alembic runs on an empty file can stall before core tables exist
    (ab7e313804ae expects legacy ``acls``). Copy the packaged template, then
    let ``run_relational_migrations()`` advance it to head.
    """
    db_dir = Path(settings.cognee_system_root) / "databases"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "cognee_db"

    if _cognee_metadata_is_healthy(db_path):
        return

    if db_path.exists():
        db_path.unlink()

    template = (
        Path(cognee.__file__).resolve().parent
        / ".cognee_system"
        / "databases"
        / "cognee_db"
    )
    if not template.is_file():
        raise RuntimeError(
            "Cognee metadata template missing. Reinstall cognee in the backend venv."
        )

    shutil.copy2(template, db_path)


def setup_cognee() -> None:
    """Initialize Cognee storage layout, Ollama LLM, and provider configuration."""
    settings = get_settings()

    cognee.config.data_root_directory(settings.cognee_data_root)
    cognee.config.system_root_directory(settings.cognee_system_root)
    cognee.config.set("vector_db_provider", settings.cognee_vector_db_provider)
    cognee.config.set_vector_db_config(
        {
            "vector_dataset_database_handler": "lancedb",
            "vector_db_subprocess_enabled": False,
        }
    )

    graph_db_config: dict = {
        "graph_database_provider": settings.cognee_graph_db_provider,
    }
    if settings.cognee_graph_db_provider == "neo4j":
        graph_db_config.update(
            {
                "graph_database_url": settings.cognee_graph_db_url,
                "graph_database_username": settings.cognee_graph_db_username,
                "graph_database_password": settings.cognee_graph_db_password,
                "graph_database_name": settings.cognee_graph_db_name,
                "graph_database_subprocess_enabled": False,
                "graph_dataset_database_handler": "neo4j",
            }
        )
    cognee.config.set_graph_db_config(graph_db_config)

    cognee.config.set_llm_provider(settings.llm_provider)
    cognee.config.set_llm_model(settings.llm_model)
    cognee.config.set_llm_endpoint(settings.llm_endpoint)
    cognee.config.set_llm_api_key(settings.llm_api_key)
    cognee.config.set_embedding_provider(settings.embedding_provider)
    cognee.config.set_embedding_model(settings.embedding_model)
    cognee.config.set_embedding_dimensions(settings.embedding_dimensions)
    cognee.config.set_embedding_endpoint(settings.embedding_endpoint)
    cognee.config.set_embedding_api_key(settings.embedding_api_key)

    for path in (
        settings.cognee_data_root,
        settings.cognee_system_root,
        settings.cognee_cache_root,
        str(Path(settings.cognee_system_root) / "databases"),
    ):
        Path(path).mkdir(parents=True, exist_ok=True)

    ensure_cognee_metadata_database(settings)


async def run_cognee_add_and_cognify(
    content: str,
    *,
    dataset_name: str | None = None,
    custom_prompt: str | None = None,
) -> dict:
    """
    Placeholder async utility that ingests unstructured text via cognee.add()
    and builds the retrieval graph via cognee.cognify().
    """
    settings = get_settings()
    target_dataset = dataset_name or settings.cognee_dataset_name

    await cognee.add(content, dataset_name=target_dataset)
    result = await cognee.cognify(
        datasets=target_dataset,
        custom_prompt=custom_prompt,
    )
    return {"dataset": target_dataset, "cognify_result": result}
