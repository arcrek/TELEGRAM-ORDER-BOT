# Broadcast Notification Image Attachment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a dashboard admin attach one optional image to a broadcast notification, delivered to bot users via Telegram `send_photo`.

**Architecture:** FastAPI cannot mix a JSON body with a file upload, so the two existing JSON broadcast endpoints (`/send`, `/send/active`) are consolidated into one multipart endpoint that takes `message`, `audience`, optional `user_ids`, and an optional `image`. The image is validated once, read into memory, and passed through `NotificationService`; the service uploads the image to Telegram only on the first recipient, captures its `file_id`, and reuses that string for every subsequent recipient.

**Tech Stack:** Python 3.11+, FastAPI, python-telegram-bot, SQLAlchemy 2.0, pytest; React 18 + TypeScript, axios, vitest.

## Global Constraints

- All bot DB service functions and the dashboard endpoint handlers are written with `async def` where the existing code is async; the per-recipient send already supports both sync and async `bot.send_*` via `asyncio.iscoroutinefunction` — preserve that.
- Database access only through `src/database/services/` — no raw queries in routers.
- Telegram `send_photo` hard limits: image ≤ 10 MB; caption ≤ 1024 chars.
- Frontend strings use the existing `t('notifications.*', '<Vietnamese fallback>')` pattern (Vietnamese is the inline default; English lives in the `en` locale json).
- No server-side storage of the image — in-flight only.
- Existing text-only behavior must not regress: when no image is attached, the code path and the exact `bot.send_message(chat_id=..., text=...)` call are unchanged.

---

### Task 1: Service layer — image support in `NotificationService`

**Files:**
- Modify: `src/database/services/notification_service.py`
- Test: `tests/test_notification_service.py`

**Interfaces:**
- Consumes: existing `BotUserService.get_all_started_users()`, `get_active_users()`.
- Produces:
  - `send_notification_to_user_async(self, telegram_user_id: int, message: str, image_bytes: Optional[bytes] = None, file_id_holder: Optional[dict] = None) -> Dict`
  - `send_notification_to_all_started_async(self, message: str, image_bytes: Optional[bytes] = None) -> Dict`
  - `send_notification_to_active_users_async(self, message: str, image_bytes: Optional[bytes] = None) -> Dict`
  - `send_notification_to_multiple_users_async(self, telegram_user_ids: List[int], message: str, image_bytes: Optional[bytes] = None) -> Dict`
  - `file_id_holder` is a mutable dict `{"file_id": None | str}` shared across one broadcast so the image uploads once; when omitted, a fresh local holder is used (single-send case).

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_notification_service.py`. First extend the `mock_bot` fixture to also provide `send_photo`:

```python
@pytest.fixture
def mock_bot():
    """Create a mock Telegram bot."""
    bot = Mock()
    bot.send_message = Mock()
    bot.send_photo = Mock(return_value=Mock(photo=[Mock(file_id="FILEID_FIRST")]))
    return bot
```

Then add a new test class at the end of the file:

```python
class TestNotificationServiceImage:
    """Image-attachment behavior for broadcasts."""

    def test_text_only_path_unchanged(self, notification_service, mock_bot):
        """No image -> uses send_message, never send_photo."""
        mock_bot.send_message.return_value = Mock(message_id=1)
        result = notification_service.send_notification_to_user(
            telegram_user_id=111, message="hello"
        )
        assert result["success"] is True
        mock_bot.send_message.assert_called_once_with(chat_id=111, text="hello")
        mock_bot.send_photo.assert_not_called()

    def test_image_short_text_uses_caption(self, notification_service, mock_bot):
        """Image + short text -> single send_photo with caption."""
        res = asyncio.run(
            notification_service.send_notification_to_user_async(
                telegram_user_id=111, message="cap", image_bytes=b"PNGBYTES"
            )
        )
        assert res["success"] is True
        assert mock_bot.send_photo.call_count == 1
        _, kwargs = mock_bot.send_photo.call_args
        assert kwargs["chat_id"] == 111
        assert kwargs["caption"] == "cap"
        mock_bot.send_message.assert_not_called()

    def test_image_long_text_sends_photo_then_message(self, notification_service, mock_bot):
        """Image + text > 1024 chars -> send_photo (no caption) then send_message."""
        long_text = "x" * 1100
        mock_bot.send_message.return_value = Mock(message_id=2)
        res = asyncio.run(
            notification_service.send_notification_to_user_async(
                telegram_user_id=111, message=long_text, image_bytes=b"PNGBYTES"
            )
        )
        assert res["success"] is True
        _, photo_kwargs = mock_bot.send_photo.call_args
        assert photo_kwargs.get("caption") is None
        mock_bot.send_message.assert_called_once_with(chat_id=111, text=long_text)

    def test_image_only_no_caption(self, notification_service, mock_bot):
        """Image, empty text -> send_photo with caption=None, no send_message."""
        res = asyncio.run(
            notification_service.send_notification_to_user_async(
                telegram_user_id=111, message="", image_bytes=b"PNGBYTES"
            )
        )
        assert res["success"] is True
        _, kwargs = mock_bot.send_photo.call_args
        assert kwargs.get("caption") is None
        mock_bot.send_message.assert_not_called()

    def test_broadcast_reuses_file_id_after_first_send(self, notification_service, mock_bot, sample_users):
        """First recipient uploads bytes; later recipients get the captured file_id string."""
        res = notification_service.send_notification_to_all_started(
            "cap", image_bytes=b"PNGBYTES"
        )
        assert res["total"] == 3
        assert res["success"] == 3
        assert mock_bot.send_photo.call_count == 3
        photos = [c.kwargs["photo"] for c in mock_bot.send_photo.call_args_list]
        # First send wraps bytes (not a str); subsequent sends reuse the file_id string.
        assert not isinstance(photos[0], str)
        assert photos[1] == "FILEID_FIRST"
        assert photos[2] == "FILEID_FIRST"

    def test_broadcast_first_send_fails_keeps_using_bytes(self, notification_service, mock_bot, sample_users):
        """If the first recipient fails, no file_id is captured, so the next still uploads bytes."""
        from telegram.error import BadRequest
        calls = {"n": 0}

        def photo_side_effect(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise BadRequest("blocked")
            return Mock(photo=[Mock(file_id="FILEID_SECOND")])

        mock_bot.send_photo.side_effect = photo_side_effect
        res = notification_service.send_notification_to_all_started(
            "cap", image_bytes=b"PNGBYTES"
        )
        assert res["failed"] == 1
        assert res["success"] == 2
        photos = [c.kwargs["photo"] for c in mock_bot.send_photo.call_args_list]
        assert not isinstance(photos[0], str)   # first: bytes (failed)
        assert not isinstance(photos[1], str)   # second: bytes again (no file_id yet)
        assert photos[2] == "FILEID_SECOND"     # third: reuse captured id
```

Add `import asyncio` at the top of the test file if not present.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_notification_service.py::TestNotificationServiceImage -v`
Expected: FAIL (e.g. `send_notification_to_user_async() got an unexpected keyword argument 'image_bytes'`).

- [ ] **Step 3: Implement image support in the service**

In `src/database/services/notification_service.py`, add imports near the top:

```python
from io import BytesIO
from telegram import Bot, InputFile
```

(The file already imports `from telegram import Bot` — replace that line with the combined import above.)

Replace `send_notification_to_user_async` with this version (text-only branch is byte-for-byte the old behavior):

```python
    async def send_notification_to_user_async(
        self,
        telegram_user_id: int,
        message: str,
        image_bytes: Optional[bytes] = None,
        file_id_holder: Optional[dict] = None,
    ) -> Dict[str, any]:
        """Send a notification (optionally with one image) to a single user."""
        if not self.bot:
            return {
                "success": False,
                "error": "Bot instance not available",
                "telegram_user_id": telegram_user_id,
            }

        try:
            if image_bytes is None:
                # Text-only path — unchanged.
                send_message = self.bot.send_message
                if asyncio.iscoroutinefunction(send_message):
                    await send_message(chat_id=telegram_user_id, text=message)
                else:
                    send_message(chat_id=telegram_user_id, text=message)
            else:
                await self._send_photo_to_user(
                    telegram_user_id, message, image_bytes, file_id_holder
                )

            logger.info(f"Notification sent successfully to user {telegram_user_id}")
            return {"success": True, "telegram_user_id": telegram_user_id}
        except TelegramError as e:
            error_msg = str(e)
            logger.error(f"Failed to send notification to user {telegram_user_id}: {error_msg}")
            if isinstance(e, Forbidden):
                self.bot_user_service.update_user_active_status(telegram_user_id, False)
                logger.info(f"Marked user {telegram_user_id} as inactive (bot blocked)")
            return {"success": False, "error": error_msg, "telegram_user_id": telegram_user_id}
        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Unexpected error sending notification to user {telegram_user_id}: {error_msg}",
                exc_info=True,
            )
            return {"success": False, "error": error_msg, "telegram_user_id": telegram_user_id}

    async def _send_photo_to_user(
        self,
        telegram_user_id: int,
        message: str,
        image_bytes: bytes,
        file_id_holder: Optional[dict],
    ) -> None:
        """Send a photo, reusing a captured file_id across a broadcast when available."""
        holder = file_id_holder if file_id_holder is not None else {"file_id": None}
        cached_id = holder.get("file_id")

        # Reuse the already-uploaded image (a file_id string) when we have one;
        # otherwise upload the raw bytes.
        photo = cached_id if cached_id else InputFile(BytesIO(image_bytes))

        use_caption = len(message) <= 1024
        caption = message if (use_caption and message) else None

        send_photo = self.bot.send_photo
        if asyncio.iscoroutinefunction(send_photo):
            sent = await send_photo(chat_id=telegram_user_id, photo=photo, caption=caption)
        else:
            sent = send_photo(chat_id=telegram_user_id, photo=photo, caption=caption)

        # Capture the file_id from the first successful upload for later recipients.
        if not cached_id and sent is not None:
            photos = getattr(sent, "photo", None)
            if photos:
                holder["file_id"] = photos[-1].file_id

        # Text longer than the caption limit goes in a separate message.
        if not use_caption and message:
            send_message = self.bot.send_message
            if asyncio.iscoroutinefunction(send_message):
                await send_message(chat_id=telegram_user_id, text=message)
            else:
                send_message(chat_id=telegram_user_id, text=message)
```

Update the sync single-user wrapper `send_notification_to_user` to accept and forward `image_bytes`:

```python
    def send_notification_to_user(
        self, telegram_user_id: int, message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """Send notification to a single user (synchronous wrapper)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_notification_to_user_async(
                            telegram_user_id, message, image_bytes
                        ),
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.send_notification_to_user_async(
                        telegram_user_id, message, image_bytes
                    )
                )
        except RuntimeError:
            return asyncio.run(
                self.send_notification_to_user_async(
                    telegram_user_id, message, image_bytes
                )
            )
```

In each of the three async broadcast methods (`send_notification_to_all_started_async`, `send_notification_to_active_users_async`, `send_notification_to_multiple_users_async`), add the `image_bytes: Optional[bytes] = None` parameter, create a single shared holder before the loop, and pass it into each send. For example, in `send_notification_to_all_started_async`:

```python
    async def send_notification_to_all_started_async(
        self, message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        users = self.bot_user_service.get_all_started_users()
        results = {"total": len(users), "success": 0, "failed": 0, "details": []}
        file_id_holder = {"file_id": None}

        for user in users:
            result = await self.send_notification_to_user_async(
                user.telegram_user_id, message, image_bytes, file_id_holder
            )
            results["details"].append(result)
            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1

        logger.info(
            f"Notification broadcast: Total: {results['total']}, "
            f"Success: {results['success']}, Failed: {results['failed']}"
        )
        return results
```

Apply the identical change to `send_notification_to_active_users_async` (uses `get_active_users()`) and to `send_notification_to_multiple_users_async` (loops over `telegram_user_ids`, passing `user_id` instead of `user.telegram_user_id`).

Update the three sync broadcast wrappers (`send_notification_to_all_started`, `send_notification_to_active_users`, `send_notification_to_multiple_users`) to accept `image_bytes: Optional[bytes] = None` and forward it into the corresponding `*_async` call (mirror the wrapper edit shown above).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_notification_service.py -v`
Expected: PASS — the new `TestNotificationServiceImage` tests **and** all pre-existing `TestNotificationService` tests (the text-only `assert_called_once_with(chat_id=..., text=...)` assertions must still hold).

- [ ] **Step 5: Commit**

```bash
git add src/database/services/notification_service.py tests/test_notification_service.py
git commit -m "feat(notifications): add optional image support to broadcast service"
```

---

### Task 2: Endpoint — consolidate to one multipart `/send` with validation

**Files:**
- Modify: `src/dashboard/routers/notifications.py` (replace the `/send` and `/send/active` handlers, lines 106-188; keep `get_bot_instance`, `/users`, and all `order-settings` handlers)
- Test: `tests/test_notifications_api.py` (new file)

**Interfaces:**
- Consumes: `NotificationService.send_notification_to_all_started_async / send_notification_to_active_users_async / send_notification_to_multiple_users_async(message, image_bytes)` from Task 1; `require_admin_role`, `get_db` from `src.dashboard.auth`; `get_bot_instance` (module-local).
- Produces: `POST /api/notifications/send` (multipart). Form fields: `message: str` (default `""`), `audience: str` (default `"all"`, one of `all|active|specific`), `user_ids: Optional[str]` (comma-separated telegram ids), `image: Optional[UploadFile]`. Returns `NotificationResponse`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_notifications_api.py`:

```python
"""Tests for the consolidated multipart notifications /send endpoint."""
import io
import pytest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.dashboard.main import app
from src.dashboard.routers import notifications as notif_router
from src.database.models import Admin, AdminRole
from src.database.models.base import Base
from src.database.services.bot_user_service import BotUserService
from src.dashboard.auth import get_password_hash, create_access_token, get_db
from src.database.models import *  # noqa: F401,F403

import tempfile, os, atexit

test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
test_db_path = test_db_file.name
test_db_file.close()
atexit.register(lambda: os.path.exists(test_db_path) and os.unlink(test_db_path))

test_engine = create_engine(
    f"sqlite:///{test_db_path}", echo=False,
    connect_args={"check_same_thread": False}, pool_pre_ping=True,
)
Base.metadata.create_all(test_engine)
TestSession = sessionmaker(bind=test_engine)


def override_get_db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True, scope="function")
def setup_database():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_token():
    session = TestSession()
    admin = Admin(
        id="admin_1", username="testadmin", email="a@b.com",
        password_hash=get_password_hash("x"), full_name="A",
        role=AdminRole.ADMIN, is_active=True,
    )
    session.add(admin)
    session.commit()
    session.close()
    return create_access_token(data={"sub": "testadmin"})


@pytest.fixture
def started_user():
    session = TestSession()
    BotUserService(session).track_user(telegram_user_id=111, username="u1")
    session.commit()
    session.close()


@pytest.fixture
def mock_bot(monkeypatch):
    bot = Mock()
    bot.send_message = Mock(return_value=Mock(message_id=1))
    bot.send_photo = Mock(return_value=Mock(photo=[Mock(file_id="FID")]))
    monkeypatch.setattr(notif_router, "get_bot_instance", lambda: bot)
    return bot


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_send_requires_auth(client):
    r = client.post("/api/notifications/send", data={"message": "hi"})
    assert r.status_code == 401


def test_send_rejects_empty_text_and_no_image(client, auth_token, mock_bot):
    r = client.post("/api/notifications/send",
                    data={"message": "  ", "audience": "all"}, headers=_auth(auth_token))
    assert r.status_code == 400


def test_send_rejects_bad_audience(client, auth_token, mock_bot):
    r = client.post("/api/notifications/send",
                    data={"message": "hi", "audience": "nobody"}, headers=_auth(auth_token))
    assert r.status_code == 400


def test_send_specific_requires_ids(client, auth_token, mock_bot):
    r = client.post("/api/notifications/send",
                    data={"message": "hi", "audience": "specific", "user_ids": ""},
                    headers=_auth(auth_token))
    assert r.status_code == 400


def test_send_rejects_non_image(client, auth_token, mock_bot):
    files = {"image": ("x.txt", io.BytesIO(b"hello"), "text/plain")}
    r = client.post("/api/notifications/send",
                    data={"message": "hi", "audience": "all"}, files=files,
                    headers=_auth(auth_token))
    assert r.status_code == 400


def test_send_rejects_oversized_image(client, auth_token, mock_bot):
    big = io.BytesIO(b"\x00" * (10 * 1024 * 1024 + 1))
    files = {"image": ("x.png", big, "image/png")}
    r = client.post("/api/notifications/send",
                    data={"message": "hi", "audience": "all"}, files=files,
                    headers=_auth(auth_token))
    assert r.status_code == 400


def test_send_text_only_all(client, auth_token, started_user, mock_bot):
    r = client.post("/api/notifications/send",
                    data={"message": "hello", "audience": "all"}, headers=_auth(auth_token))
    assert r.status_code == 200
    assert r.json()["total"] == 1
    mock_bot.send_message.assert_called_once_with(chat_id=111, text="hello")


def test_send_image_only_all(client, auth_token, started_user, mock_bot):
    files = {"image": ("x.png", io.BytesIO(b"PNG"), "image/png")}
    r = client.post("/api/notifications/send",
                    data={"message": "", "audience": "all"}, files=files,
                    headers=_auth(auth_token))
    assert r.status_code == 200
    assert mock_bot.send_photo.call_count == 1


def test_send_specific_dispatch(client, auth_token, started_user, mock_bot):
    r = client.post("/api/notifications/send",
                    data={"message": "hi", "audience": "specific", "user_ids": "111,222"},
                    headers=_auth(auth_token))
    assert r.status_code == 200
    assert r.json()["total"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_notifications_api.py -v`
Expected: FAIL — current `/send` is a JSON endpoint, so multipart `data=` posts return 422, and `audience`/`image` validation does not exist yet.

- [ ] **Step 3: Implement the consolidated endpoint**

In `src/dashboard/routers/notifications.py`, update the FastAPI imports to include `Form`, `File`, `UploadFile`:

```python
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
```

Delete the `NotificationRequest` model (no longer used) and **replace both** the `send_notification` (`/send`) and `send_notification_to_active` (`/send/active`) handlers with a single handler. Keep `NotificationResponse`, `get_bot_instance`, `list_bot_users`, and every `order-settings` handler exactly as they are.

```python
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # Telegram send_photo cap
VALID_AUDIENCES = {"all", "active", "specific"}


def _parse_user_ids(raw: Optional[str]) -> List[int]:
    """Parse a comma-separated telegram id string into a deduped int list."""
    if not raw:
        return []
    seen, ids = set(), []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid user id: {part!r}",
            )
        if value not in seen:
            seen.add(value)
            ids.append(value)
    return ids


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    message: str = Form(""),
    audience: str = Form("all"),
    user_ids: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_admin=Depends(require_admin_role),
    db: Session = Depends(get_db),
):
    """
    Send a broadcast notification (optionally with one image) to bot users.
    Admin role required. Multipart form-data.
    """
    # --- Validate before touching the bot ---
    if audience not in VALID_AUDIENCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"audience must be one of {sorted(VALID_AUDIENCES)}",
        )

    has_text = bool(message and message.strip())
    image_bytes: Optional[bytes] = None
    if image is not None:
        if not (image.content_type or "").startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Attachment must be an image.",
            )
        image_bytes = await image.read()
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image exceeds the 10 MB limit.",
            )

    if not has_text and image_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a message, an image, or both.",
        )

    parsed_ids: List[int] = []
    if audience == "specific":
        parsed_ids = _parse_user_ids(user_ids)
        if not parsed_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="audience 'specific' requires at least one user id.",
            )

    bot = get_bot_instance()
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot instance not available. Please ensure TELEGRAM_BOT_TOKEN is set.",
        )

    notification_service = NotificationService(db, bot=bot)

    if audience == "active":
        results = await notification_service.send_notification_to_active_users_async(
            message, image_bytes=image_bytes
        )
    elif audience == "specific":
        results = await notification_service.send_notification_to_multiple_users_async(
            telegram_user_ids=parsed_ids, message=message, image_bytes=image_bytes
        )
    else:  # all
        results = await notification_service.send_notification_to_all_started_async(
            message, image_bytes=image_bytes
        )

    return NotificationResponse(
        success=results["failed"] == 0,
        total=results["total"],
        successful=results["success"],
        failed=results["failed"],
        details=results.get("details"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_notifications_api.py -v`
Expected: PASS (all cases — auth, the four 400 validations, text-only, image-only, specific dispatch).

- [ ] **Step 5: Commit**

```bash
git add src/dashboard/routers/notifications.py tests/test_notifications_api.py
git commit -m "feat(notifications): consolidate broadcast into one multipart /send with image"
```

---

### Task 3: Frontend — FormData, image picker, preview, relaxed guard

**Files:**
- Modify: `frontend/src/pages/NotificationsPage.tsx`
- Modify: `frontend/src/pages/NotificationsPage.css`

**Interfaces:**
- Consumes: `POST /api/notifications/send` (multipart) from Task 2; `apiClient` from `../shared/lib/api`.
- Produces: a compose card that posts `FormData{ message, audience, user_ids?, image? }` to the single endpoint.

- [ ] **Step 1: Add image state and the FormData send logic**

In `NotificationsPage.tsx`, add image state alongside the other broadcast state (near line 64):

```tsx
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
```

Add a constant near the top of the file (after imports):

```tsx
const MAX_IMAGE_BYTES = 10 * 1024 * 1024
```

Add an effect to revoke the preview object URL on change/unmount (after the existing effects):

```tsx
  useEffect(() => {
    return () => { if (imagePreview) URL.revokeObjectURL(imagePreview) }
  }, [imagePreview])
```

Add image handlers (near `toggleUser`):

```tsx
  const handlePickImage = (file: File | null) => {
    if (!file) return
    if (!file.type.startsWith('image/')) {
      toast.warning(t('notifications.imageNotImage', 'Tệp đính kèm phải là ảnh'))
      return
    }
    if (file.size > MAX_IMAGE_BYTES) {
      toast.warning(t('notifications.imageTooLarge', 'Ảnh vượt quá giới hạn 10MB'))
      return
    }
    if (imagePreview) URL.revokeObjectURL(imagePreview)
    setImageFile(file)
    setImagePreview(URL.createObjectURL(file))
  }

  const clearImage = () => {
    if (imagePreview) URL.revokeObjectURL(imagePreview)
    setImageFile(null)
    setImagePreview(null)
  }
```

Replace the entire `handleSend` function with a FormData version (allows text-or-image, single endpoint):

```tsx
  const handleSend = async () => {
    if (!message.trim() && !imageFile) {
      toast.warning(t('notifications.emptyMessage', 'Nhập nội dung tin nhắn hoặc đính kèm ảnh'))
      return
    }
    if (audienceMode === 'specific' && selectedUserIds.size === 0) {
      toast.warning(t('notifications.noUsersSelected', 'Chọn ít nhất một người dùng'))
      return
    }
    setSending(true)
    setSendResult(null)
    try {
      const form = new FormData()
      form.append('message', message)
      form.append('audience', audienceMode)
      if (audienceMode === 'specific') {
        form.append('user_ids', Array.from(selectedUserIds).join(','))
      }
      if (imageFile) form.append('image', imageFile)

      const res = await apiClient.post<NotificationResult>('/api/notifications/send', form)
      setSendResult(res.data)
      if (res.data.success) {
        setMessage('')
        setSelectedUserIds(new Set())
        clearImage()
        toast.success(t('notifications.sent', `Đã gửi: ${res.data.successful}/${res.data.total}`))
      }
    } catch (err) {
      toast.error(formatApiError(err, t('notifications.sendError', 'Không thể gửi thông báo')))
    } finally {
      setSending(false)
    }
  }
```

(axios sets the multipart boundary automatically when given a `FormData` body, overriding the client's default JSON content-type for this request.)

- [ ] **Step 2: Add the image picker UI**

In the compose card, immediately after the char-count `div` (around line 218) and before the audience selector, insert:

```tsx
                  {/* Image attachment */}
                  <div className="notifications-page__image-field">
                    {imagePreview ? (
                      <div className="notifications-page__image-preview">
                        <img src={imagePreview} alt={t('notifications.imageAlt', 'Ảnh đính kèm')} />
                        <Button variant="secondary" tone="ghost" size="sm" onClick={clearImage}>
                          {t('notifications.removeImage', 'Xóa ảnh')}
                        </Button>
                      </div>
                    ) : (
                      <label className="notifications-page__image-upload">
                        <input
                          type="file"
                          accept="image/*"
                          onChange={e => handlePickImage(e.target.files?.[0] ?? null)}
                        />
                        <span>{t('notifications.attachImage', 'Đính kèm ảnh (tùy chọn)')}</span>
                      </label>
                    )}
                  </div>
```

- [ ] **Step 3: Add styles**

Append to `frontend/src/pages/NotificationsPage.css`:

```css
.notifications-page__image-field {
  margin-top: 12px;
}
.notifications-page__image-upload {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px dashed #2a2a26;
  border-radius: 8px;
  color: #6EA8FF;
  cursor: pointer;
  font-size: 13px;
}
.notifications-page__image-upload input {
  display: none;
}
.notifications-page__image-preview {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.notifications-page__image-preview img {
  max-width: 160px;
  max-height: 160px;
  border-radius: 8px;
  border: 1px solid #2a2a26;
  object-fit: cover;
}
```

- [ ] **Step 4: Verify typecheck, lint, and build pass**

Run: `cd frontend && npm run lint && npm run build`
Expected: lint clean and a successful production build (TypeScript compiles with no errors). There is no existing component-test harness for dashboard pages, so verification here is type/lint/build plus the manual check below.

Manual check (with backend running): open the Notifications page → Broadcast tab → attach an image → preview shows with a remove button → send with text+image, image-only, and specific-users; confirm the result banner reports the counts.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/NotificationsPage.tsx frontend/src/pages/NotificationsPage.css
git commit -m "feat(notifications): attach image to broadcast from dashboard UI"
```

---

### Task 4: i18n keys for the new UI strings

**Files:**
- Modify: `frontend/src/i18n/locales/vi/notifications.json`
- Modify: `frontend/src/i18n/locales/en/notifications.json`

**Interfaces:**
- Consumes: the `t('notifications.*', …)` keys introduced in Task 3.
- Produces: resolved VI/EN strings for `attachImage`, `removeImage`, `imageAlt`, `imageTooLarge`, `imageNotImage`, `noUsersSelected`.

- [ ] **Step 1: Add keys to the Vietnamese locale**

Edit `frontend/src/i18n/locales/vi/notifications.json` so the `notifications` object includes the new keys (keep existing keys):

```json
{
  "notifications": {
    "title": "Thông báo",
    "sendToAll": "Gửi đến Tất cả Người dùng",
    "sendToActive": "Gửi đến Người dùng Hoạt động",
    "sendToUser": "Gửi đến Người dùng Cụ thể",
    "message": "Tin nhắn",
    "selectUser": "Chọn Người dùng",
    "send": "Gửi",
    "success": "Đã gửi thông báo thành công",
    "error": "Gửi thông báo thất bại",
    "attachImage": "Đính kèm ảnh (tùy chọn)",
    "removeImage": "Xóa ảnh",
    "imageAlt": "Ảnh đính kèm",
    "imageTooLarge": "Ảnh vượt quá giới hạn 10MB",
    "imageNotImage": "Tệp đính kèm phải là ảnh",
    "noUsersSelected": "Chọn ít nhất một người dùng"
  }
}
```

- [ ] **Step 2: Add the same keys to the English locale**

Edit `frontend/src/i18n/locales/en/notifications.json` to add (keep existing keys):

```json
    "attachImage": "Attach image (optional)",
    "removeImage": "Remove image",
    "imageAlt": "Attached image",
    "imageTooLarge": "Image exceeds the 10MB limit",
    "imageNotImage": "Attachment must be an image",
    "noUsersSelected": "Select at least one user"
```

- [ ] **Step 3: Verify the JSON parses and the build still passes**

Run: `cd frontend && npm run build`
Expected: successful build (invalid JSON would fail the build).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/i18n/locales/vi/notifications.json frontend/src/i18n/locales/en/notifications.json
git commit -m "i18n(notifications): add broadcast image attachment strings"
```

---

## Notes for the implementer

- **Run the full backend suite once after Task 2** (`pytest tests/test_notification_service.py tests/test_notifications_api.py tests/test_notification_commands.py -v`) to confirm no broadcast consumer relied on the removed `/send/active` route or the `NotificationRequest` model. Per project memory, ~52 env-driven suite failures elsewhere are pre-existing and unrelated.
- **No other caller of `/send` or `/send/active`:** the only consumer is `NotificationsPage.tsx`, updated in Task 3. If a grep (`grep -rn "notifications/send" frontend/src`) turns up another caller, update it to the multipart contract.
- The bot's own `/sendall`-style command handlers (tested in `test_notification_commands.py`) call the service methods directly; the added `image_bytes` parameter is optional and defaults to `None`, so they are unaffected.
