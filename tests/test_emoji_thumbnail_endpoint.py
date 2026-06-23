import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models.base import Base
from src.dashboard.auth import get_db
from src.dashboard.routers import emoji_thumbnails
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService


@pytest.fixture
def ctx(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    # Seed a placeholder referencing emoji id "111".
    seed = Session()
    psvc = EmojiPlaceholderService(seed)
    pid = psvc.create("P")
    psvc.set_content(pid, [{"t": "emoji", "id": "111", "fb": "🔔"}], raw_text="🔔", set_by=None)
    seed.close()

    app = FastAPI()
    app.include_router(emoji_thumbnails.router, prefix="/api/emoji-thumbnails")

    def override_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_db
    # Bot is non-None; fetch is mocked per-test.
    monkeypatch.setattr(emoji_thumbnails, "_get_bot", lambda: object())
    return TestClient(app), monkeypatch


def test_unknown_id_returns_404_without_fetch(ctx):
    client, monkeypatch = ctx
    fake = AsyncMock()
    monkeypatch.setattr(emoji_thumbnails, "fetch_thumbnail_bytes", fake)
    resp = client.get("/api/emoji-thumbnails/999")  # not referenced
    assert resp.status_code == 404
    fake.assert_not_called()


def test_fetch_then_cache_hit(ctx):
    client, monkeypatch = ctx
    fake = AsyncMock(return_value=(b"imgbytes", "image/webp"))
    monkeypatch.setattr(emoji_thumbnails, "fetch_thumbnail_bytes", fake)

    r1 = client.get("/api/emoji-thumbnails/111")
    assert r1.status_code == 200
    assert r1.content == b"imgbytes"
    assert r1.headers["content-type"] == "image/webp"

    r2 = client.get("/api/emoji-thumbnails/111")  # served from cache
    assert r2.status_code == 200
    assert r2.content == b"imgbytes"
    assert fake.call_count == 1  # not fetched again


def test_fetch_failure_negative_cached(ctx):
    client, monkeypatch = ctx
    fake = AsyncMock(return_value=None)
    monkeypatch.setattr(emoji_thumbnails, "fetch_thumbnail_bytes", fake)

    r1 = client.get("/api/emoji-thumbnails/111")
    assert r1.status_code == 404
    r2 = client.get("/api/emoji-thumbnails/111")  # fresh negative cache
    assert r2.status_code == 404
    assert fake.call_count == 1  # not retried while fresh


def test_fetch_helper_parses_sticker():
    bot = AsyncMock()
    bot.get_custom_emoji_stickers.return_value = [type("S", (), {"thumbnail": type("T", (), {"file_id": "fid"})()})()]
    tg_file = AsyncMock()
    tg_file.download_as_bytearray.return_value = bytearray(b"png")
    bot.get_file.return_value = tg_file

    data, mime = asyncio.run(
        emoji_thumbnails.fetch_thumbnail_bytes(bot, "111")
    )
    assert data == b"png"
    assert mime == "image/webp"
