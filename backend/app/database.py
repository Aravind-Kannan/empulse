from collections.abc import Generator
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> tuple[bool, str | None]:
    """Lightweight Postgres ping for cold-start warmup and health checks."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        logger.warning("Postgres health check failed: %s", exc)
        return False, str(exc)


def init_db() -> None:
    from app.models import (  # noqa: F401
        ingest_job,
        integration_sync_job,
        integration_sync_record,
        jira_integration,
        operational,
        tenant,
        user,
        user_tenant_membership,
    )

    Base.metadata.create_all(bind=engine)

    from app.db_schema_patches import apply_schema_patches

    apply_schema_patches(engine)

    db = SessionLocal()
    try:
        from app.services.tenant_bootstrap import bootstrap_tenancy

        bootstrap_tenancy(db)
    finally:
        db.close()
