from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.app.settings import settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    if settings.database_url:
        url = settings.database_url.replace("postgres://", "postgresql://", 1)
        return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10, future=True)
    else:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = settings.data_dir / "app.sqlite3"
        return create_engine(f"sqlite:///{db_path.as_posix()}", future=True)


def SessionLocal():
    """每次调用时根据当前 settings 创建 session，确保 Secrets 加载后生效"""
    engine = _make_engine()
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    return factory()


def init_db() -> None:
    from backend.app import models  # noqa: F401
    engine = _make_engine()
    Base.metadata.create_all(bind=engine, checkfirst=True)

    from backend.app.services.auth import init_admin_user
    with SessionLocal() as db:
        init_admin_user(db)
