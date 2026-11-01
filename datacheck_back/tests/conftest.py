import pytest
from fastapi.testclient import TestClient

from app.database import Base, get_engine


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATACHECK_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DATACHECK_SECRET_KEY", "test-secret-with-at-least-32-characters")
    monkeypatch.setenv("DATACHECK_TEMP_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DATACHECK_DATA_DIR", str(tmp_path / "storage"))
    Base.metadata.create_all(get_engine())


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def register(client, email="ana@example.com", name="Ana", password="senha-segura-1"):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def user_client(client):
    """Cliente sem login: usa o usuário visitante."""
    return client


@pytest.fixture
def account_client(client):
    register(client)
    return client


@pytest.fixture
def other_client():
    from app.main import app
    c = TestClient(app)
    register(c, email="bruno@example.com", name="Bruno")
    return c
