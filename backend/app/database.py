from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

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


def init_db() -> None:
    from app.models import operational, tenant, user, user_tenant_membership  # noqa: F401

    Base.metadata.create_all(bind=engine)

    from app.db_schema_patches import apply_schema_patches

    apply_schema_patches(engine)

    db = SessionLocal()
    try:
        from app.services.tenant_bootstrap import bootstrap_tenancy

        bootstrap_tenancy(db)
    finally:
        db.close()
