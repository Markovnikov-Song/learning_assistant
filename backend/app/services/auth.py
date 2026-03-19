from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.app.db import SessionLocal
from backend.app.models import User
from backend.app.settings import settings

# HTTP Bearer 认证
security = HTTPBearer()

# 密码哈希配置
HASH_ALGORITHM = "pbkdf2_hmac_sha256"
HASH_ITERATIONS = 100000
HASH_SALT_LENGTH = 32


def _hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """使用 PBKDF2-HMAC-SHA256 哈希密码"""
    if salt is None:
        salt = secrets.token_bytes(HASH_SALT_LENGTH)
    password_bytes = password.encode('utf-8')
    hash_bytes = hashlib.pbkdf2_hmac(
        'sha256',
        password_bytes,
        salt,
        HASH_ITERATIONS
    )
    return hash_bytes, salt


def get_password_hash(password: str) -> str:
    """生成密码哈希（返回格式：iterations$salt$hash）"""
    hash_bytes, salt = _hash_password(password)
    salt_hex = salt.hex()
    hash_hex = hash_bytes.hex()
    return f"{HASH_ITERATIONS}${salt_hex}${hash_hex}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        iterations_hex, salt_hex, hash_hex = hashed_password.split('$')
        iterations = int(iterations_hex)
        salt = bytes.fromhex(salt_hex)
        stored_hash = bytes.fromhex(hash_hex)

        password_bytes = plain_password.encode('utf-8')
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password_bytes,
            salt,
            iterations
        )
        return secrets.compare_digest(computed_hash, stored_hash)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """创建 JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """解码 JWT token"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Session = Depends(get_db),
) -> User:
    """获取当前登录用户"""
    token = credentials.credentials
    payload = decode_access_token(token)
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """获取当前管理员用户"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要管理员权限",
        )
    return current_user


def create_user(db: Session, username: str, password: str, is_admin: bool = False) -> User:
    """创建用户"""
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )
    # 创建新用户
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """验证用户凭据"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def init_admin_user(db: Session) -> None:
    """初始化管理员用户（如果不存在）"""
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            password_hash=get_password_hash("123456"),
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        # 不打印默认密码到控制台，避免日志泄露
        # 默认密码已在 README 中说明