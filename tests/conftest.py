"""Pytest fixtures for Navigator Chat backend tests."""

import os

# Use shared in-memory SQLite so all connections see the same DB
os.environ["DATABASE_PATH"] = "file:testdb?mode=memory&cache=shared"

import pytest
from fastapi.testclient import TestClient

from main import app
from auth import get_current_uid
from sqlalchemy import text

from database import get_db, init_db, engine


# Test user ID used when auth is mocked
TEST_UID = "test-user-123"


def mock_get_current_uid():
    """Override auth to return test UID without Firebase."""
    return TEST_UID


@pytest.fixture(autouse=True)
def db_cleanup():
    """Clear DB between tests so they don't share state."""
    init_db()
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM messages"))
        conn.execute(text("DELETE FROM conversations"))
        conn.execute(text("DELETE FROM users"))
        conn.commit()
    yield


@pytest.fixture
def client():
    """Test client with mocked auth (no Firebase required)."""
    app.dependency_overrides[get_current_uid] = mock_get_current_uid
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client():
    """Test client without auth override - uses real auth (401 when no token)."""
    # Ensure no override so real get_current_uid runs
    if get_current_uid in app.dependency_overrides:
        del app.dependency_overrides[get_current_uid]
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    """Headers that would normally contain Bearer token (unused when auth mocked)."""
    return {"Authorization": "Bearer fake-token-for-test"}


@pytest.fixture
def other_user_client():
    """Client authenticated as a different user (for 403 tests)."""
    def mock_other_uid():
        return "other-user-456"

    app.dependency_overrides[get_current_uid] = mock_other_uid
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def conv_owned_by_test_user(client, auth_headers):
    """Create a conversation owned by TEST_UID via API (for 403 tests)."""
    r = client.post("/conversations", headers=auth_headers)
    return r.json()["id"]
