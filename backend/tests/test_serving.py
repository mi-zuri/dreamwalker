"""What the container has to get right that a `bun run dev` never exercises.

In deployment one Cloud Run service is the whole product: it answers the API
and serves the frontend that calls it. These are the seams that creates.
"""

import pytest
from pydantic import ValidationError

from app.settings import Settings, settings


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


def test_a_half_configured_backend_refuses_to_start():
    """The halves cannot disagree, because the mismatch is a boot failure.

    `AUTH_MODE=firebase` with nothing to sign into used to leave `/api/config`
    quietly answering as though this install had no accounts: the frontend
    then sent no token and every call came back "missing bearer token", a 401
    that blames the browser for an unset variable on the server.
    """
    with pytest.raises(ValidationError, match="FIREBASE_API_KEY"):
        Settings(
            _env_file=None,
            auth_mode="firebase",
            gcp_project="",
            firebase_api_key="",
            firebase_auth_domain="",
            firebase_app_id="",
        )


def test_a_fully_configured_backend_starts():
    Settings(
        _env_file=None,
        auth_mode="firebase",
        gcp_project="dreamwalker-test",
        firebase_api_key="test-key",
        firebase_auth_domain="dreamwalker-test.firebaseapp.com",
        firebase_app_id="1:1:web:1",
    )
