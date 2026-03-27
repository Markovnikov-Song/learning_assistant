from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from backend.app.settings import settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None


def _build_engine():
    if settings.database_url:
        url = settings.database_url.replace("postgres://", "postgresql://", 1)
        return create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            future=True,
        )
    else:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = settings.data_dir / "app.sqlite3"
        return create_engine(f"sqlite:///{db_path.as_posix()}", future=True)


def get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def SessionLocal() -> Session:
    """懒加载 session factory，确保在 settings.database_url 设置后才建连接"""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autocommit=False, autoflush=False, future=True
        )
    return _session_factory()


def init_db() -> None:
    from backend.app import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine(), checkfirst=True)

    from backend.app.services.auth import init_admin_user
    with SessionLocal() as db:
        init_admin_user(db)
