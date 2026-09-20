"""What the container has to get right that a `bun run dev` never exercises.

In deployment one Cloud Run service is the whole product: it answers the API
and serves the frontend that calls it. These are the seams that creates.
"""

import pytest

from app.settings import settings


@pytest.fixture
def firebase_mode():
    """A backend configured the way the deployed one is."""
    settings.auth_mode = "firebase"
    settings.gcp_project = "dreamwalker-test"
    settings.firebase_api_key = "test-key"
    settings.firebase_auth_domain = "dreamwalker-test.firebaseapp.com"
    settings.firebase_app_id = "1:1:web:1"
    settings.firebase_storage_bucket = "dreamwalker-test.appspot.com"
    settings.firebase_messaging_sender_id = "1"
    yield
    settings.auth_mode = "dev"
    settings.gcp_project = ""
    settings.firebase_api_key = ""


def test_dev_mode_sends_no_firebase_config(client):
    """The frontend follows the backend into dev mode.

    This is the whole point of serving the config rather than compiling it
    in: the two halves cannot disagree about whether this install has real
    accounts, so a stray `.env.local` can no longer put the browser into a
    Google sign-in that the backend is not checking.
    """
    body = client.get("/api/config").json()
    assert body["auth_mode"] == "dev"
    assert body["firebase"] is None


def test_firebase_mode_sends_the_project_identifiers(client, firebase_mode):
    body = client.get("/api/config").json()
    assert body["auth_mode"] == "firebase"
    assert body["firebase"] == {
        "api_key": "test-key",
        "auth_domain": "dreamwalker-test.firebaseapp.com",
        "project_id": "dreamwalker-test",
        "app_id": "1:1:web:1",
        "storage_bucket": "dreamwalker-test.appspot.com",
        "messaging_sender_id": "1",
    }


def test_config_needs_no_token(client, firebase_mode):
    """It is read before there is anyone to authenticate."""
    assert client.get("/api/config").status_code == 200


def test_a_half_configured_backend_stays_in_dev_mode(client):
    """Missing config is not a reason to send the browser at a broken login."""
    settings.auth_mode = "firebase"
    try:
        assert client.get("/api/config").json()["firebase"] is None
    finally:
        settings.auth_mode = "dev"
