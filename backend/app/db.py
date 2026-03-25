from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.app.settings import settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    if settings.database_url:
        # 云端 PostgreSQL（Supabase/Neon 给的 URL 可能是 postgres://，需替换）
        url = settings.database_url.replace("postgres://", "postgresql://", 1)
        return create_engine(
            url,
            pool_pre_ping=True,   # 自动检测断连
            pool_size=5,
            max_overflow=10,
            future=True,
        )
    else:
        # 本地 SQLite 兜底
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = settings.data_dir / "app.sqlite3"
        return create_engine(f"sqlite:///{db_path.as_posix()}", future=True)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def init_db() -> None:
    from backend.app import models  # noqa: F401

    Base.metadata.create_all(bind=engine, checkfirst=True)

    from backend.app.services.auth import init_admin_user
    with SessionLocal() as db:
        init_admin_user(db)
