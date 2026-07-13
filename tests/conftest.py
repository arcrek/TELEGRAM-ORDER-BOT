"""
Shared pytest fixtures and patches for the test suite.

Patches the database session factory so handler tests that call t() or
track_user() do not require a live database connection.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

# Set DASHBOARD_SECRET_KEY before any test module imports src.dashboard.auth
# so the module-level `SECRET_KEY = os.getenv(...)` picks it up.
if not os.environ.get("DASHBOARD_SECRET_KEY"):
    os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key-for-pytest"


@pytest.fixture(autouse=True)
def patch_language_db(request):
    """Patch the DB session factory for unit tests that don't use a real DB.

    Patches both the language utility and the bot-command handlers so that
    any call to get_session_factory() falls back gracefully instead of
    raising RuntimeError when DATABASE_URL is not configured.

    Skipped for tests that manage their own DB session (those that use the
    db_session fixture or are marked with 'integration').
    """
    # Don't patch if the test already sets up a real DB session
    if "db_session" in request.fixturenames or request.node.get_closest_marker("integration"):
        yield
        return

    mock_session = MagicMock()
    # BotUserService / UserPreferenceService queries return None → no-op / fallback
    mock_session.query.return_value.filter_by.return_value.first.return_value = None
    mock_session.execute.return_value.scalars.return_value.first.return_value = None
    mock_session_factory = MagicMock(return_value=mock_session)

    patches = [
        patch("src.bot.utils.language.get_session_factory", return_value=mock_session_factory),
        patch("src.bot.utils.admin_check._get_session", return_value=mock_session),
        patch("src.bot.handlers.commands.get_session_factory", return_value=mock_session_factory),
        patch("src.bot.handlers.callbacks.get_session_factory", return_value=mock_session_factory),
    ]
    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()


@pytest.fixture(autouse=True)
def set_dashboard_secret_key(monkeypatch):
    """Ensure DASHBOARD_SECRET_KEY is set so JWT helpers work in unit tests.

    If the real env var is already set, leave it alone.  Otherwise inject a
    dummy secret so create_access_token / verify tests can run without a
    real deployment key.
    """
    import os
    if not os.environ.get("DASHBOARD_SECRET_KEY"):
        monkeypatch.setenv("DASHBOARD_SECRET_KEY", "test-secret-key-for-pytest")
        # Also patch the module-level SECRET_KEY constant that was set at import time
        import src.dashboard.auth as auth_mod
        monkeypatch.setattr(auth_mod, "SECRET_KEY", "test-secret-key-for-pytest")
