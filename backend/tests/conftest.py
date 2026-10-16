import os

os.environ.setdefault(
    "RIVER_DATABASE_URL", "postgresql+psycopg://river:river@localhost:54329/river_test"
)
os.environ["RIVER_DEV_MODE"] = "true"

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def schema():
    with engine.begin() as conn:
        conn.execute(text("drop schema public cascade; create schema public"))
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")


def wipe() -> None:
    with engine.begin() as conn:
        conn.execute(text("truncate users, messages, catches, reports, purchases cascade"))


@pytest.fixture
def clean(schema):
    wipe()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


class Dev:
    """A dev user talking to the API through the X-Dev-User header."""

    def __init__(self, client: TestClient, name: str):
        self.client = client
        self.name = name
        self.headers = {"X-Dev-User": name}

    def get(self, path):
        return self.client.get("/api" + path, headers=self.headers)

    def post(self, path, json=None):
        return self.client.post("/api" + path, json=json, headers=self.headers)

    def write(self, text, option="any"):
        r = self.post("/messages", {"text": text, "return_option": option})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def catch(self):
        r = self.post("/catch")
        assert r.status_code == 200, r.text
        return r.json()

    def me(self):
        return self.get("/me").json()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user(client):
    return lambda name: Dev(client, name)
