from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 关键修改：使用绝对导入（以 backend 为根）
from backend.app.settings import settings


class Base(DeclarativeBase):
    pass


def _db_path() -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / "app.sqlite3"


engine = create_engine(f"sqlite:///{_db_path().as_posix()}", future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def init_db() -> None:
    # 导入所有模型（确保 Base 能识别表结构）
    from backend.app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

