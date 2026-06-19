# Broadcast notification image attachment — Design

**Date:** 2026-06-19
**Status:** Approved (design)

## Summary

Add the ability to attach a single optional image to a dashboard broadcast
notification. Today the **Broadcast** tab ("Phát tin") on the Notifications
page sends a text-only message to all / active / specific bot users via
`bot.send_message`. After this change, the admin can attach one image (uploaded
from their computer) that is delivered alongside the message via
`bot.send_photo`.

## Goals

- Admin can attach one image when composing a broadcast.
- Image is uploaded from the admin's device (multipart form-data).
- Image is sent in-flight only — **not** stored on the server.
- An **image-only** broadcast (image, no text) is allowed.
- The image uploads to Telegram **once** per broadcast, not once per recipient.

## Non-goals (out of scope)

- Server-side storage / audit trail of the image.
- Multiple images / Telegram media-group albums.
- Image-by-URL input.
- Changes to the Order-alerts tab.

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Image source | Upload from computer (multipart `UploadFile`) |
| Text + image delivery | Caption when text ≤ 1024 chars; fall back to photo + separate text message when longer |
| Attachment scope | Single optional image, sent in-flight, not stored |
| Image-only broadcast | Allowed (relax the empty-message guard) |
| API structure | **Approach A** — consolidate `/send` + `/send/active` into one multipart endpoint |

## Architecture

FastAPI cannot mix a JSON body with an `UploadFile`. Supporting a file forces
**every** field to become `Form(...)`. There is no "add an optional image to the
current JSON body" path — the existing JSON contract must change to multipart.
Given that, we consolidate the two existing endpoints into one.

### 1. Endpoint — `src/dashboard/routers/notifications.py`

Replace `POST /api/notifications/send` and `POST /api/notifications/send/active`
with a single multipart endpoint (admin role required):

```
POST /api/notifications/send   (multipart/form-data)
  message:   str          = Form("")
  audience:  str          = Form("all")     # "all" | "active" | "specific"
  user_ids:  str | None   = Form(None)      # comma-separated telegram_user_ids; used when audience == "specific"
  image:     UploadFile|None = File(None)
```

**Validation, once, before any send (return 400 on failure):**
- Require `message.strip()` OR an image (reject when both empty).
- If `audience == "specific"`, require a non-empty parsed `user_ids` list.
- If image present: content-type must be an image (`image/*`); size ≤ 10 MB
  (Telegram `send_photo` cap). Read bytes into memory once.
- Validate `audience` is one of the allowed values.

Dispatch by `audience` to the service:
- `all` → `send_notification_to_all_started_async`
- `active` → `send_notification_to_active_users_async`
- `specific` → `send_notification_to_multiple_users_async(parsed_ids, ...)`

Response shape stays `NotificationResponse` (success/total/successful/failed/details).

### 2. Service — `src/database/services/notification_service.py`

Thread an optional `image_bytes: Optional[bytes]` parameter through the broadcast
methods (`*_async` and their sync wrappers) and into
`send_notification_to_user_async`.

**Per-recipient send logic in `send_notification_to_user_async`:**

- **No image** → existing `send_message` path, unchanged.
- **Image present** → use `send_photo`, with a shared **file_id reuse** strategy
  across the broadcast:
  - The broadcast methods hold a small mutable holder (e.g. a dict or a single
    mutable variable closed over / passed by reference) for the captured
    `file_id`, initially `None`.
  - For each recipient: if `file_id` is known, pass `photo=file_id` (a string —
    Telegram serves the already-uploaded image, no re-upload). Otherwise wrap the
    raw bytes (`InputFile(BytesIO(image_bytes))`) and on success capture
    `msg.photo[-1].file_id` into the holder for subsequent recipients.
  - Bytes are the fallback whenever no `file_id` is captured yet (e.g. the first
    recipient has blocked the bot → that send fails → next recipient again sends
    bytes until one succeeds).
- **Caption vs separate message** (applies to the photo send):
  - `len(text) <= 1024` (including empty text) → `send_photo(caption=text or None)`.
  - `len(text) > 1024` → `send_photo` with no caption, then a separate
    `send_message(text)`.
- Forbidden/blocked handling unchanged: mark user inactive on `Forbidden`.

Because the broadcast methods iterate users sequentially (current behavior), the
file_id holder is naturally shared across the loop. The sync wrappers gain the
same optional `image_bytes` passthrough for signature parity (dashboard uses the
async path).

### 3. Frontend — `frontend/src/pages/NotificationsPage.tsx`

- Add to the compose card: an image file input, a thumbnail preview of the
  selected image, and a "remove" button. Store the `File` in component state and
  an object-URL for the preview.
- **Relax the send guard** (`handleSend`): allow send when text OR image is
  present; only warn when both are empty.
- **Switch to `FormData`:** build `FormData` with `message`, `audience`
  (derived from `audienceMode`), `user_ids` (comma-joined, only when
  `specific`), and `image` (when selected). POST to the single
  `/api/notifications/send`; drop the per-mode URL switching.
- Client-side guard before upload: reject non-image files and files > 10 MB with
  a toast.
- On successful send: clear `message`, the selected image/preview, and
  `selectedUserIds` (as today). Revoke the preview object-URL on clear/unmount.

### 4. i18n — `frontend/src/i18n/locales/{vi,en}/notifications.json`

The broadcast UI is the dashboard frontend, so all new strings go in the
frontend i18n resources (not the bot's `src/i18n/locales/*/bot.json`). Add VI
(default) + EN keys under the existing `notifications.*` namespace for: attach
image, remove image, preview alt text, "file too large", "not an image".

## Data flow

```
Admin (compose card) ──FormData(message, audience, user_ids?, image?)──▶
  POST /api/notifications/send
    └─ validate (text-or-image, image type/size ≤10MB, audience, ids)
    └─ read image bytes once
    └─ NotificationService.<dispatch by audience>(message, image_bytes)
         └─ for each recipient (sequential):
              ├─ image? → send_photo (bytes first → capture file_id → reuse string)
              │            caption if text≤1024 else photo + separate send_message
              └─ no image → send_message
              └─ Forbidden → mark inactive
    └─ NotificationResponse{ total, successful, failed, details }
```

## Error handling

- Invalid/missing input → 400 before any Telegram call.
- Bot instance unavailable → 503 (existing behavior).
- Per-recipient failures collected into `details`; `Forbidden` marks the user
  inactive (existing behavior).
- Oversized/non-image file rejected both client-side (toast) and server-side
  (400) as defense in depth.

## Testing

- **Service unit tests** (in-memory SQLite, mocked bot per existing test
  patterns):
  - Text-only broadcast still works (no regression).
  - Image broadcast: first recipient sent bytes, subsequent recipients sent the
    captured `file_id` string (assert `send_photo` called with the file_id on
    user 2+).
  - Caption path (text ≤ 1024) vs photo + separate message path (text > 1024).
  - Image-only (empty text) sends photo with no caption.
  - First-recipient failure → second recipient still sent bytes (file_id not yet
    captured).
- **Endpoint tests:** multipart accepted; validation 400s (both empty; bad image
  type; >10 MB; specific audience with empty ids); dispatch routes to the right
  service method per `audience`.
- **Frontend:** send guard allows image-only; FormData assembled with correct
  fields per audience mode.
