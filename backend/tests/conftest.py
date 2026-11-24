import os
import asyncio
from pathlib import Path

import httpx
import pytest


TEST_DB = Path(__file__).resolve().parent / "test-agrotec.db"
os.environ["AGROTEC_DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AGROTEC_SKIP_MIGRATION_BACKUP"] = "1"
os.environ["AGROTEC_ADMIN_EMAIL"] = "admin@agrotec.test"
os.environ["AGROTEC_ADMIN_PASSWORD"] = "Pruebas-Seguras-2026"
os.environ["AGROTEC_ADMIN_NAME"] = "Administrador de pruebas"
os.environ["AGROTEC_SESSION_SECRET"] = "test-session-secret-with-more-than-32-characters"
os.environ["AGROTEC_COOKIE_SECURE"] = "0"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.family_classifier import classify_catalog  # noqa: E402
from app.importer import import_catalog  # noqa: E402
from app.auth import bootstrap_initial_admin  # noqa: E402
from app.main import app  # noqa: E402


class SyncASGIClient:
    def __init__(self):
        self.cookies = httpx.Cookies()

    def request(self, method: str, path: str, **kwargs):
        async def send():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test", cookies=self.cookies
            ) as client:
                response = await client.request(method, path, **kwargs)
                self.cookies.update(client.cookies)
                return response
        return asyncio.run(send())

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs):
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self.request("DELETE", path, **kwargs)


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        import_catalog(db)
        classify_catalog(db)
        bootstrap_initial_admin(db)
        db.commit()
    test_client = SyncASGIClient()
    response = test_client.post("/api/auth/login", json={
        "email": "admin@agrotec.test", "password": "Pruebas-Seguras-2026",
    })
    assert response.status_code == 200
    yield test_client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def anonymous_client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        import_catalog(db)
        classify_catalog(db)
        bootstrap_initial_admin(db)
        db.commit()
    yield SyncASGIClient()
    Base.metadata.drop_all(bind=engine)

