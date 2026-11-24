from pathlib import Path
import time
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from starlette.requests import Request

from app.auth import bootstrap_initial_admin, hash_password, verify_password
from app.main import app, check_login_rate, login_attempts
from app.models import Base, User


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("Contrasena-Muy-Segura-2026")
    second = hash_password("Contrasena-Muy-Segura-2026")
    assert first != second
    assert verify_password("Contrasena-Muy-Segura-2026", first)
    assert not verify_password("Contrasena-Incorrecta", first)


def test_initial_admin_is_created_once(monkeypatch):
    path = Path(__file__).parent / f"test-auth-{uuid4().hex}.db"
    target = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(target)
    Session = sessionmaker(bind=target)
    monkeypatch.setenv("AGROTEC_ADMIN_EMAIL", "ADMIN@AGROTEC.TEST")
    monkeypatch.setenv("AGROTEC_ADMIN_PASSWORD", "Administrador-Seguro-2026")
    monkeypatch.setenv("AGROTEC_ADMIN_NAME", "Administrador")
    with Session() as db:
        bootstrap_initial_admin(db)
        bootstrap_initial_admin(db)
        users = db.scalars(select(User)).all()
        assert len(users) == 1
        assert users[0].email == "admin@agrotec.test"
        assert users[0].role == "admin"
        assert verify_password("Administrador-Seguro-2026", users[0].password_hash)
    target.dispose()
    path.unlink()


def test_every_business_endpoint_has_the_expected_role_dependency():
    dependencies = {
        (route.path, next(iter(route.methods))): {item.call.__name__ for item in route.dependant.dependencies}
        for route in app.routes
        if route.path.startswith("/api/") and route.path not in {"/api/health", "/api/auth/login", "/api/auth/logout"}
    }
    admin_routes = {
        ("/api/users", "GET"), ("/api/users", "POST"), ("/api/users/{user_id}", "PATCH"),
        ("/api/import", "POST"), ("/api/products/{product_id}/commercial-preference", "PUT"),
        ("/api/products/{product_id}", "PATCH"), ("/api/products/bulk-family", "POST"),
        ("/api/rules", "GET"), ("/api/rules", "PUT"), ("/api/rules/preview", "POST"),
        ("/api/rules/bulk-products", "POST"), ("/api/rules/{scope_type}/{scope_key}", "DELETE"),
        ("/api/settings", "GET"), ("/api/settings", "PATCH"),
    }
    for route, names in dependencies.items():
        if route in admin_routes:
            assert "require_admin" in names
        else:
            assert "get_current_user" in names


def test_login_rate_limit_blocks_repeated_attempts():
    request = Request({"type": "http", "headers": [], "client": ("192.0.2.15", 1234)})
    login_attempts.clear()
    for number in range(8):
        key = check_login_rate(request)
        login_attempts.setdefault(key, []).append(time.time() + number / 1000)
    try:
        check_login_rate(request)
        assert False, "El noveno intento debió ser bloqueado."
    except HTTPException as error:
        assert error.status_code == 429
    finally:
        login_attempts.clear()
