from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, UserSession, utc_now


COOKIE_NAME = "agrotec_session"
PASSWORD_ITERATIONS = 600_000


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(candidate, bytes.fromhex(digest_hex))
    except (ValueError, TypeError):
        return False


def _session_secret() -> bytes:
    secret = os.getenv("AGROTEC_SESSION_SECRET", "local-development-session-secret-change-me")
    if os.getenv("AGROTEC_ENV") == "production" and len(secret) < 32:
        raise RuntimeError("AGROTEC_SESSION_SECRET debe tener al menos 32 caracteres en producción.")
    return secret.encode("utf-8")


def hash_session_token(token: str) -> str:
    return hmac.new(_session_secret(), token.encode("utf-8"), hashlib.sha256).hexdigest()


def session_hours() -> int:
    return max(1, min(int(os.getenv("AGROTEC_SESSION_HOURS", "12")), 168))


def set_session_cookie(response: Response, token: str) -> None:
    lifetime = session_hours() * 3600
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=lifetime,
        httponly=True,
        secure=os.getenv("AGROTEC_COOKIE_SECURE", "0") == "1",
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        httponly=True,
        secure=os.getenv("AGROTEC_COOKIE_SECURE", "0") == "1",
        samesite="lax",
        path="/",
    )


def create_session(db: Session, user: User, request: Request) -> str:
    token = secrets.token_urlsafe(48)
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    db.add(UserSession(
        token_hash=hash_session_token(token),
        user_id=user.id,
        expires_at=utc_now() + timedelta(hours=session_hours()),
        user_agent=request.headers.get("user-agent", "")[:255] or None,
        ip_address=(forwarded or (request.client.host if request.client else ""))[:64] or None,
    ))
    user.last_login_at = utc_now()
    db.commit()
    return token


def revoke_session(db: Session, raw_token: str | None) -> None:
    if raw_token:
        db.execute(delete(UserSession).where(UserSession.token_hash == hash_session_token(raw_token)))
        db.commit()


def user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inicia sesión para continuar.")
    row = db.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(
            UserSession.token_hash == hash_session_token(token),
            UserSession.expires_at > utc_now(),
            User.is_active.is_(True),
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La sesión venció o no es válida.")
    return row[1]


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Se requiere acceso de administrador.")
    return user


def bootstrap_initial_admin(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)) is not None:
        return
    email = os.getenv("AGROTEC_ADMIN_EMAIL", "").strip()
    password = os.getenv("AGROTEC_ADMIN_PASSWORD", "")
    if not email or len(password) < 12:
        raise RuntimeError(
            "La primera ejecución requiere AGROTEC_ADMIN_EMAIL y AGROTEC_ADMIN_PASSWORD (mínimo 12 caracteres)."
        )
    db.add(User(
        email=normalize_email(email),
        full_name=os.getenv("AGROTEC_ADMIN_NAME", "Administrador Agrotec").strip() or "Administrador Agrotec",
        password_hash=hash_password(password),
        role="admin",
        is_active=True,
    ))
    db.commit()
