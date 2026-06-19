"""
Shared pytest fixtures and patches for the test suite.

Patches the database session factory used by the language utility so that
handler tests that call t() do not require a live database connection.
"""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def patch_language_db(request):
    """Patch the DB session used by language.get_user_language so t() works
    without a live database in unit tests.

    Skipped for tests that manage their own DB session (those that use the
    db_session fixture or are marked with 'integration').
    """
    # Don't patch if the test already sets up a real DB session
    if "db_session" in request.fixturenames or request.node.get_closest_marker("integration"):
        yield
        return

    mock_session = MagicMock()
    # UserPreferenceService.get_user_preference returns None → falls back to DEFAULT_LANGUAGE
    mock_session.execute.return_value.scalars.return_value.first.return_value = None
    mock_session_factory = MagicMock(return_value=mock_session)

    with patch("src.bot.utils.language.get_session_factory", return_value=mock_session_factory):
        yield
