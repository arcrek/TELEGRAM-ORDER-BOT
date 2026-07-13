import pytest

from src.payos.client import PAYOS_API_BASE_URL, build_payos_client


def test_build_payos_client_reads_required_environment(monkeypatch):
    monkeypatch.setenv("PAYOS_CLIENT_ID", "client")
    monkeypatch.setenv("PAYOS_API_KEY", "api")
    monkeypatch.setenv("PAYOS_CHECKSUM_KEY", "checksum")

    client = build_payos_client()

    assert client.base_url == PAYOS_API_BASE_URL
    assert client.credentials.client_id == "client"
    assert client.credentials.api_key == "api"
    assert client.credentials.checksum_key == "checksum"


def test_build_payos_client_names_missing_environment(monkeypatch):
    for name in ("PAYOS_CLIENT_ID", "PAYOS_API_KEY", "PAYOS_CHECKSUM_KEY"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(
        RuntimeError,
        match="PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY",
    ):
        build_payos_client()
