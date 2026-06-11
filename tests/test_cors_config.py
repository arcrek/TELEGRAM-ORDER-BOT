"""
CORS origin parsing must never combine wildcard with credentialed requests.
"""
import pytest

from src.dashboard.main import resolve_cors_origins


def test_explicit_origins_parsed():
    result = resolve_cors_origins("https://a.example.com, https://b.example.com")
    assert result == ["https://a.example.com", "https://b.example.com"]


def test_unset_defaults_to_localhost_dev_origins():
    result = resolve_cors_origins(None)
    assert "http://localhost:5173" in result
    assert "*" not in result


def test_wildcard_is_rejected():
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        resolve_cors_origins("*")
