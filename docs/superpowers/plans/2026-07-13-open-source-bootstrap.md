# Open-Source Bootstrap and Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a sanitized AGPL-3.0, PayOS-only Docker Compose release that a new operator can initialize with `./setup.sh`, operate with `./manage.sh`, and maintain from complete public documentation.

**Architecture:** Keep secrets and deployment routing in `.env`; extend the existing `AppSettings` singleton for editable identity fields. The supported Compose graph is PostgreSQL → FastAPI API/PayOS webhook → customer bot and React frontend. A host-side Bash wizard orchestrates Docker while a container-side Python bootstrap command performs the transactional database initialization.

**Tech Stack:** Bash, Docker Compose, Python 3.11, FastAPI, SQLAlchemy/Alembic, PostgreSQL 16, python-telegram-bot, PayOS HTTP API, React 18, TypeScript, Vite, nginx, pytest, Vitest.

## Global Constraints

- Docker Compose is the only supported deployment path; do not add native host Python/Node setup.
- `setup.sh` supports Linux, macOS, and WSL with Bash, Git, Docker, and the Docker Compose plugin.
- PayOS and balance are the only executable payment paths.
- Supplier functionality stays in source but remains experimental, unsupported, and absent from default setup, Compose, and health checks.
- The public license is AGPL-3.0.
- `.env` owns secrets and infrastructure; `AppSettings` owns system name, bot URL, support lines, timezone, order prefix, and API docs URL.
- Do not add a general settings framework, plugin system, extra payment abstraction, host package manager, or shell framework.
- Use existing dependencies and standard-library code. Remove Flask and Gunicorn after the Pay2S IPN service is deleted.
- Never print, log, commit, or pass secrets/passwords as process arguments.
- Database schema changes require Alembic migrations.
- Preserve historical non-balance QR revenue without retaining a Pay2S runtime branch.
- Keep all user-facing bot copy in the existing i18n files; operator-entered support lines are data, not translation keys.
- Prefix all repository commands in this plan with `rtk`, following your environment's RTK instructions (typically `~/.codex/RTK.md`).

## File Responsibility Map

### Create

- `src/database/migrations/versions/n4b5c6d7e8f9_expand_app_settings.py` — add editable identity columns.
- `scripts/bootstrap_system.py` — read one JSON payload from stdin and initialize the first admin/settings transactionally.
- `setup.sh` — interactive first-run Docker orchestrator.
- `manage.sh` — supported lifecycle command dispatcher.
- `tests/test_app_settings_api.py` — authenticated/public settings API coverage.
- `tests/test_admin_check.py` — configured owner and DB-backed admin coverage.
- `tests/test_bootstrap_system.py` — bootstrap validation, idempotence, rollback, and output coverage.
- `tests/test_operator_scripts.py` — shell behavior through fake `docker`/`git` executables.
- `tests/test_health_endpoints.py` — liveness and database readiness coverage.
- `frontend/src/contexts/BrandingContext.tsx` — cached public system-name state.
- `frontend/src/contexts/BrandingContext.test.tsx` — branding load/fallback tests.
- `frontend/src/pages/GeneralSettingsPage.test.tsx` — load/edit/save behavior.
- `frontend/src/i18n/locales/{vi,en}/generalSettings.json` — complete settings-page copy.
- `docs/INSTALLATION.md`, `docs/CONFIGURATION.md`, `docs/ARCHITECTURE.md` — operator documentation.
- `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `ROADMAP.md` — public governance.

### Modify

- `src/payos/client.py`, payment handlers, auto-cancel service, statistics service, and shared fulfillment comments — PayOS-only runtime.
- `src/database/models/app_settings.py`, `src/database/services/app_settings_service.py`, `src/dashboard/routers/app_settings.py` — settings persistence and API.
- `src/bot/utils/admin_check.py`, `src/bot/handlers/commands.py` — configured owner permissions.
- `src/database/services/order_service.py`, `src/bot/handlers/apitoken.py`, `src/dashboard/routers/product_upload.py`, `src/ipn/processor.py` — runtime setting consumers.
- `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/GeneralSettingsPage.tsx`, `frontend/src/app/layouts/Sidebar.tsx`, `frontend/src/pages/ApiPage.tsx`, `frontend/src/i18n/config.ts` — editable branding/settings UI.
- `docker-compose.yml`, `Dockerfile.api`, `Dockerfile.bot`, `entrypoint.sh`, `.env.example` — deterministic supported stack.
- `scripts/create_admin.py`, `scripts/backup_database.sh`, `scripts/restore_database.sh` — safe credentials and custom DB handling.
- `.gitignore`, `.dockerignore`, `.github/workflows/ci.yml`, `requirements.txt` — publication/CI hygiene.
- `README.md`, `OPERATIONS.md`, `AGENTS.md`, `CLAUDE.md`, `frontend/README.md`, `scripts/README.md` — one consistent public operating model.

### Delete

- `src/pay2s/`, `config/`, `Dockerfile.ipn`, `wsgi.py`.
- `tests/test_payment.py`, `tests/test_ipn.py`, `tests/test_pay2s_ipn_rejection.py`, `tests/test_pay2s_signature_security.py`.
- Tracked `.claude/` workspace notes and vendored personal agent assets.

## Delivery Phases and Release Gates

| Phase | Tasks | Gate |
| --- | --- | --- |
| 0. Containment | 1 | Exposed credentials rotated externally; no executable Pay2S or personal defaults remain |
| 1. Configuration | 2-4 | Identity fields are validated, persisted, consumed, and dashboard-editable |
| 2. Docker bootstrap | 5-7 | Clean clone reaches a healthy system with one script and no host Python/Node |
| 3. Operations | 8 | All routine lifecycle actions use `manage.sh`; backup/restore/update drills pass |
| 4. Public project | 9-10 | Documentation, governance, CI, secret scan, license review, and clean-snapshot rehearsal pass |
| Beta | after Task 10 | Publish fresh-history `v0.1.0`; run one stable operating cycle |
| Stable | post-beta | Publish `v1.0.0` with no open installation, payment, update, or recovery blocker |

---

### Task 1: Remove Pay2S and Sanitize the Executable Tree

**Files:**
- Delete: `src/pay2s/__init__.py`, `src/pay2s/payment.py`, `src/pay2s/signature.py`, `src/pay2s/ipn.py`
- Delete: `config/__init__.py`, `config/config.py`, `Dockerfile.ipn`, `wsgi.py`
- Delete: `tests/test_payment.py`, `tests/test_ipn.py`, `tests/test_pay2s_ipn_rejection.py`, `tests/test_pay2s_signature_security.py`
- Modify: `src/payos/client.py:1-76`
- Modify: `src/bot/handlers/balance.py:109-350`
- Modify: `src/bot/handlers/callbacks.py:979-1340`
- Modify: `src/database/services/auto_cancel_service.py:90-125,250-280`
- Modify: `src/database/services/statistics_service.py:133-170`
- Modify: `src/database/models/order.py:41-42`
- Modify: `src/database/models/topup_order.py:27`
- Modify: `src/ipn/__init__.py:1-5`, `src/ipn/processor.py:1-125`
- Modify: `docker-compose.yml:1-175`, `.env.example:1-50`, `requirements.txt:1-45`
- Modify: `tests/test_statistics_service.py:330-350`
- Create: `tests/test_payos_client_config.py`

**Interfaces:**
- Consumes: existing `PayOSClient`, `PayOSCredentials`, `AppSettingsService.get_settings()`.
- Produces: `PAYOS_API_BASE_URL: str` and `build_payos_client() -> PayOSClient` in `src.payos.client`; no provider selector remains.

- [ ] **Step 0: Revoke exposed Pay2S credentials outside the repository**

The repository owner revokes or rotates every Pay2S partner/access/secret value
that has appeared in tracked files. Record only the completion date and provider
confirmation; never copy the old or replacement values into an issue, commit,
test log, or plan. Do not proceed toward a public remote while this gate is open.

- [ ] **Step 1: Write failing PayOS configuration and historical revenue tests**

Create `tests/test_payos_client_config.py`:

```python
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
```

Change the existing statistics fixture to use a provider name the runtime does
not know, proving history is counted generically:

```python
self._make_order(
    db_session,
    "v_legacy_qr",
    OrderStatus.DELIVERED,
    80000,
    "legacy_qr",
    now,
    now,
)
# payos (100k) + historical external QR (80k); balance/null excluded
assert service.get_vendor_revenue() == 180000
```

- [ ] **Step 2: Run the focused tests and verify the new helper is absent**

Run:

```bash
rtk pytest tests/test_payos_client_config.py tests/test_statistics_service.py::TestStatisticsServiceNewBehaviors::test_get_vendor_revenue_excludes_balance_orders -v
```

Expected: collection fails because `PAYOS_API_BASE_URL` and
`build_payos_client` do not exist.

- [ ] **Step 3: Centralize the three required PayOS credentials**

Update `src/payos/client.py`:

```python
import os

PAYOS_API_BASE_URL = "https://api-merchant.payos.vn"


@dataclass(frozen=True)
class PayOSCredentials:
    client_id: str
    api_key: str
    checksum_key: str


def build_payos_client() -> "PayOSClient":
    values = {
        "PAYOS_CLIENT_ID": os.getenv("PAYOS_CLIENT_ID", "").strip(),
        "PAYOS_API_KEY": os.getenv("PAYOS_API_KEY", "").strip(),
        "PAYOS_CHECKSUM_KEY": os.getenv("PAYOS_CHECKSUM_KEY", "").strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"Missing PayOS configuration: {', '.join(missing)}")
    return PayOSClient(
        base_url=PAYOS_API_BASE_URL,
        credentials=PayOSCredentials(
            client_id=values["PAYOS_CLIENT_ID"],
            api_key=values["PAYOS_API_KEY"],
            checksum_key=values["PAYOS_CHECKSUM_KEY"],
        ),
    )
```

Remove `partner_code` and its conditional header because it is not required by
the active integration.

- [ ] **Step 4: Replace both provider branches with direct PayOS calls**

In `_create_topup_qr` and the order QR function, delete provider selection,
`config.config` imports, Pay2S fallbacks, bank-account parsing, IPN URL logic,
and `PAYMENT_PROVIDER_DEFAULT`. Build the client and obtain runtime values from
the existing session:

```python
from src.database.services.app_settings_service import AppSettingsService
from src.payos.client import build_payos_client

settings = AppSettingsService(session).get_settings()
try:
    payos = build_payos_client()
except RuntimeError as exc:
    logger.error("PayOS configuration error: %s", exc)
    await context.bot.send_message(
        chat_id=user_id,
        text=t("payment.configuration_error", update),
    )
    return

description = f"{settings.order_prefix}{topup.id}"[:9]  # top-up path
# Product-order path uses: description = order.id[:9]
payos_resp = payos.create_payment_link(
    order_code=int(payos_order_code),
    amount=int(amount),
    description=description,
    return_url=settings.bot_url,
    cancel_url=settings.bot_url,
    expired_at=expired_at,
)
```

Add `payment.configuration_error` and `payment.creation_error` to both
`src/i18n/locales/vi/bot.json` and `src/i18n/locales/en/bot.json`; use those
keys in both handlers instead of new hard-coded messages.

Replace both `auto_cancel_service.py` credential blocks with
`payos = build_payos_client()`. Preserve its existing cancellation exception
handling.

- [ ] **Step 5: Count historical external QR orders without naming old providers**

Replace the statistics filter with:

```python
qr_query = self.session.query(func.sum(Order.total_amount)).filter(
    Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]),
    Order.payment_provider.is_not(None),
    Order.payment_provider != "balance",
)
```

Update model comments to `"payos" | "balance"` and make the shared IPN
docstrings provider-neutral.

- [ ] **Step 6: Delete Pay2S artifacts and remove dead dependencies/config**

Delete the files listed above with `apply_patch`. Remove `flask` and
`gunicorn` from `requirements.txt`. Remove Pay2S/IPN/provider-selector
variables, the commented IPN service, and the unused `pay2s-network` from
Compose and `.env.example`. Keep the FastAPI PayOS webhook and
`src/ipn/processor.py`.

- [ ] **Step 7: Verify the focused behavior and absence of executable references**

Run:

```bash
rtk pytest tests/test_payos_client_config.py tests/test_payos_signature.py tests/test_payos_webhook.py tests/test_ipn_idempotency.py tests/test_statistics_service.py -v
rtk rg -n -i "pay2s|PAYMENT_PROVIDER_DEFAULT|DEFAULT_BANK_ACCOUNTS" src config docker-compose.yml .env.example requirements.txt tests
```

Expected: tests pass; `rg` reports no matches and may report that deleted
`config` does not exist.

- [ ] **Step 8: Run backend regression tests and commit**

Run:

```bash
rtk pytest -q
rtk ruff check src tests
```

Expected: all tests pass and Ruff reports no new error.

Commit:

```bash
rtk git add -A
rtk git commit -m "refactor(payments): remove Pay2S"
```

---

### Task 2: Expand and Validate Runtime App Settings

**Files:**
- Create: `src/database/migrations/versions/n4b5c6d7e8f9_expand_app_settings.py`
- Create: `tests/test_app_settings_api.py`
- Modify: `src/database/models/app_settings.py:1-25`
- Modify: `src/database/services/app_settings_service.py:1-65`
- Modify: `src/dashboard/routers/app_settings.py:1-52`
- Modify: `src/dashboard/main.py:108-118`
- Modify: `tests/test_app_settings_service.py:25-83`

**Interfaces:**
- Consumes: existing singleton ID `global`, `validate_timezone()`, dashboard auth dependencies.
- Produces: `AppSettingsService.update_settings(...)`, `AppSettingsResponse`, `PublicAppSettingsResponse`, authenticated `GET/PUT /api/app-settings`, public `GET /api/app-settings/public`.

- [ ] **Step 1: Add failing service validation tests**

Append to `tests/test_app_settings_service.py`:

```python
def test_default_identity_values_are_generic(db_session):
    settings = AppSettingsService(db_session).get_settings()
    assert settings.system_name == "Bot Order System"
    assert settings.bot_url == ""
    assert settings.support_line_1 == ""
    assert settings.support_line_2 == ""
    assert settings.order_prefix == "ORD"
    assert settings.api_docs_url == ""


def test_update_normalizes_identity_values(db_session):
    updated = AppSettingsService(db_session).update_settings(
        system_name="  Example Shop  ",
        bot_url="https://t.me/example_shop_bot",
        support_line_1=" @support ",
        support_line_2=" ",
        timezone="UTC",
        order_prefix="abc",
        api_docs_url="https://shop.example/api",
    )
    assert updated.system_name == "Example Shop"
    assert updated.order_prefix == "ABC"
    assert updated.support_line_1 == "@support"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("system_name", "", "system_name"),
        ("bot_url", "http://t.me/example_shop_bot", "bot_url"),
        ("bot_url", "https://example.com/bot", "bot_url"),
        ("order_prefix", "TUX", "cannot start with TU"),
        ("order_prefix", "A-1", "order_prefix"),
        ("api_docs_url", "http://shop.example/api", "api_docs_url"),
        ("support_line_1", "x" * 201, "support_line_1"),
    ],
)
def test_invalid_identity_value_fails(db_session, field, value, message):
    service = AppSettingsService(db_session)
    valid = {
        "system_name": "Example Shop",
        "bot_url": "https://t.me/example_shop_bot",
        "support_line_1": "Support",
        "support_line_2": "",
        "timezone": "UTC",
        "order_prefix": "ORD",
        "api_docs_url": "https://shop.example/api",
    }
    valid[field] = value
    with pytest.raises(ValueError, match=message):
        service.update_settings(**valid)
```

- [ ] **Step 2: Run service tests and verify the model lacks the fields**

Run:

```bash
rtk pytest tests/test_app_settings_service.py -v
```

Expected: failures report missing AppSettings attributes and unsupported
`update_settings` keyword arguments.

- [ ] **Step 3: Add the Alembic migration and model columns**

Create `n4b5c6d7e8f9_expand_app_settings.py`:

```python
"""Expand global app settings with operator identity fields."""

from alembic import op
import sqlalchemy as sa

revision = "n4b5c6d7e8f9"
down_revision = "m3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("system_name", sa.String(length=80), nullable=False, server_default="Bot Order System"),
    )
    op.add_column(
        "app_settings",
        sa.Column("bot_url", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("support_line_1", sa.String(length=200), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("support_line_2", sa.String(length=200), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("order_prefix", sa.String(length=8), nullable=False, server_default="ORD"),
    )
    op.add_column(
        "app_settings",
        sa.Column("api_docs_url", sa.String(length=2048), nullable=False, server_default=""),
    )


def downgrade() -> None:
    for name in (
        "api_docs_url",
        "order_prefix",
        "support_line_2",
        "support_line_1",
        "bot_url",
        "system_name",
    ):
        op.drop_column("app_settings", name)
```

Mirror the exact lengths/defaults in `AppSettings` with non-null `Column`
definitions.

- [ ] **Step 4: Implement one validation path in `AppSettingsService`**

Add standard-library `re` and `urllib.parse.urlsplit`. Keep partial updates for
existing timezone-only callers:

```python
_ORDER_PREFIX_RE = re.compile(r"^[A-Z0-9]{2,8}$")
_BOT_URL_RE = re.compile(r"^https://t\.me/[A-Za-z0-9_]{5,32}/?$")


def _https_url(name: str, value: str, *, required: bool) -> str:
    value = value.strip()
    if not value and not required:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"{name} must be an absolute HTTPS URL")
    return value


def update_settings(
    self,
    *,
    system_name: str | None = None,
    bot_url: str | None = None,
    support_line_1: str | None = None,
    support_line_2: str | None = None,
    timezone: str | None = None,
    order_prefix: str | None = None,
    api_docs_url: str | None = None,
    commit: bool = True,
) -> AppSettings:
    settings = self.get_settings()
    if system_name is not None:
        value = system_name.strip()
        if not 1 <= len(value) <= 80:
            raise ValueError("system_name must contain 1-80 characters")
        settings.system_name = value
    if bot_url is not None:
        value = bot_url.strip()
        if not _BOT_URL_RE.fullmatch(value):
            raise ValueError("bot_url must be an https://t.me bot URL")
        settings.bot_url = value.rstrip("/")
    for name, value in (("support_line_1", support_line_1), ("support_line_2", support_line_2)):
        if value is not None:
            value = value.strip()
            if len(value) > 200:
                raise ValueError(f"{name} must contain at most 200 characters")
            setattr(settings, name, value)
    if timezone is not None:
        if not validate_timezone(timezone):
            raise ValueError(f"Invalid IANA timezone: {timezone!r}")
        settings.timezone = timezone
    if order_prefix is not None:
        value = order_prefix.strip().upper()
        if not _ORDER_PREFIX_RE.fullmatch(value):
            raise ValueError("order_prefix must contain 2-8 uppercase letters or digits")
        if value.startswith("TU"):
            raise ValueError("order_prefix cannot start with TU")
        settings.order_prefix = value
    if api_docs_url is not None:
        settings.api_docs_url = _https_url("api_docs_url", api_docs_url, required=False)
    if commit:
        self.session.commit()
        self.session.refresh(settings)
    else:
        self.session.flush()
    return settings
```

Change `get_settings()` to create generic model defaults only; remove
`APP_TIMEZONE` environment seeding so runtime configuration has one source of
truth. Update the four old env-seeding tests accordingly.

- [ ] **Step 5: Write failing authenticated/public router tests**

Create `tests/test_app_settings_api.py` with a temporary SQLite session and
dependency overrides:

```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.dashboard.main import app
from src.database.models.base import Base


def test_public_settings_exposes_only_system_name(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'settings.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def db_override():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = db_override
    try:
        response = TestClient(app).get("/api/app-settings/public")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"system_name": "Bot Order System"}


def test_admin_can_replace_all_settings(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'settings.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def db_override():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_admin_role] = lambda: object()
    app.dependency_overrides[require_viewer_or_admin] = lambda: object()
    payload = {
        "system_name": "Example Shop",
        "bot_url": "https://t.me/example_shop_bot",
        "support_line_1": "@support",
        "support_line_2": "",
        "timezone": "UTC",
        "order_prefix": "SHOP",
        "api_docs_url": "https://shop.example/api",
    }
    try:
        response = TestClient(app).put("/api/app-settings", json=payload)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == payload
```

- [ ] **Step 6: Implement router schemas and the public route**

Use one serializer so GET and PUT cannot drift:

```python
class AppSettingsResponse(BaseModel):
    system_name: str
    bot_url: str
    support_line_1: str
    support_line_2: str
    timezone: str
    order_prefix: str
    api_docs_url: str


class AppSettingsUpdateRequest(AppSettingsResponse):
    pass


class PublicAppSettingsResponse(BaseModel):
    system_name: str


def _response(settings) -> AppSettingsResponse:
    return AppSettingsResponse(
        system_name=settings.system_name,
        bot_url=settings.bot_url,
        support_line_1=settings.support_line_1,
        support_line_2=settings.support_line_2,
        timezone=settings.timezone,
        order_prefix=settings.order_prefix,
        api_docs_url=settings.api_docs_url,
    )


@router.get("/public", response_model=PublicAppSettingsResponse)
async def get_public_app_settings(db: Session = Depends(get_db)):
    settings = AppSettingsService(db).get_settings()
    return PublicAppSettingsResponse(system_name=settings.system_name)
```

Pass `**payload.model_dump()` to the service in PUT. Preserve admin/viewer
authorization on the existing endpoints.

- [ ] **Step 7: Run settings tests and migration syntax checks**

Run:

```bash
rtk pytest tests/test_app_settings_service.py tests/test_app_settings_api.py -v
rtk python3 -m compileall -q src/database/migrations/versions/n4b5c6d7e8f9_expand_app_settings.py
```

Expected: all tests pass and compileall exits 0.

- [ ] **Step 8: Commit the backend settings unit**

```bash
rtk git add src/database/models/app_settings.py src/database/services/app_settings_service.py src/database/migrations/versions/n4b5c6d7e8f9_expand_app_settings.py src/dashboard/routers/app_settings.py tests/test_app_settings_service.py tests/test_app_settings_api.py
rtk git commit -m "feat(settings): add operator identity"
```

---

### Task 3: Connect Runtime Settings and Configured Telegram Ownership

**Files:**
- Create: `tests/test_admin_check.py`
- Modify: `src/bot/utils/admin_check.py:1-113`
- Modify: `src/bot/handlers/commands.py:1-35,130-175,735-810`
- Modify: `src/bot/handlers/apitoken.py:1-45`
- Modify: `src/bot/handlers/balance.py:145-220`
- Modify: `src/bot/handlers/callbacks.py:1010-1130`
- Modify: `src/database/services/order_service.py:20-45`
- Modify: `src/dashboard/routers/product_upload.py:45-70`
- Modify: `src/dashboard/main.py:138-146`
- Modify: `src/ipn/processor.py:810-845`
- Modify: `tests/test_order_service.py:60-72`

**Interfaces:**
- Consumes: Task 2 `AppSettingsService`; Task 1 `build_payos_client()`.
- Produces: `get_owner_telegram_id() -> int | None`, `is_owner(int) -> bool`, prefixed new order IDs, runtime settings at every former environment/hard-coded consumer.

- [ ] **Step 1: Write failing owner permission tests**

Create `tests/test_admin_check.py`:

```python
from unittest.mock import MagicMock

from src.bot.utils import admin_check


def test_configured_owner_is_admin(monkeypatch):
    monkeypatch.setenv("BOT_OWNER_TELEGRAM_ID", "123456")
    monkeypatch.setattr(admin_check, "_get_session", MagicMock())
    monkeypatch.setattr(
        admin_check,
        "_database_admin_ids",
        lambda: [222],
        raising=False,
    )
    assert admin_check.get_owner_telegram_id() == 123456
    assert admin_check.is_owner(123456) is True
    assert admin_check.is_admin(123456) is True


def test_missing_or_invalid_owner_fails_closed(monkeypatch):
    monkeypatch.delenv("BOT_OWNER_TELEGRAM_ID", raising=False)
    assert admin_check.get_owner_telegram_id() is None
    monkeypatch.setenv("BOT_OWNER_TELEGRAM_ID", "not-a-number")
    assert admin_check.get_owner_telegram_id() is None


def test_owner_cannot_be_removed(monkeypatch):
    monkeypatch.setenv("BOT_OWNER_TELEGRAM_ID", "123456")
    assert admin_check.remove_admin(123456) is False
```

- [ ] **Step 2: Add order-prefix behavior to the existing service test**

Replace `test_generate_order_id` in `tests/test_order_service.py`:

```python
def test_generate_order_id_uses_runtime_prefix(order_service):
    AppSettingsService(order_service.session).update_settings(
        system_name="Example Shop",
        bot_url="https://t.me/example_shop_bot",
        timezone="UTC",
        order_prefix="SHOP",
    )
    order_id = order_service.generate_order_id()
    assert order_id.startswith("SHOP")
    assert len(order_id) == 12
```

Import `AppSettingsService` in the test module.

- [ ] **Step 3: Run the tests and confirm owner helpers/prefix behavior fail**

```bash
rtk pytest tests/test_admin_check.py tests/test_order_service.py::TestOrderService::test_generate_order_id_uses_runtime_prefix -v
```

Expected: missing owner helper failures and an unprefixed order ID assertion.

- [ ] **Step 4: Replace the compiled super-admin with required configuration**

Implement in `admin_check.py`:

```python
def get_owner_telegram_id() -> int | None:
    raw = os.getenv("BOT_OWNER_TELEGRAM_ID", "").strip()
    try:
        owner_id = int(raw)
    except ValueError:
        logger.error("BOT_OWNER_TELEGRAM_ID must be a positive integer")
        return None
    if owner_id <= 0:
        logger.error("BOT_OWNER_TELEGRAM_ID must be a positive integer")
        return None
    return owner_id


def _database_admin_ids() -> List[int]:
    session = _get_session()
    try:
        from src.database.services.bot_admin_service import BotAdminService
        return BotAdminService(session).get_all_telegram_ids()
    except Exception as exc:
        logger.warning("Failed to load bot admins from DB: %s", exc)
        return []
    finally:
        session.close()


def get_admin_telegram_ids() -> List[int]:
    owner_id = get_owner_telegram_id()
    values = ([owner_id] if owner_id is not None else []) + _database_admin_ids()
    return list(dict.fromkeys(values))


def is_owner(telegram_user_id: int) -> bool:
    return telegram_user_id == get_owner_telegram_id()
```

Use `is_owner()` in `remove_admin()` and `/setadmin`; label the configured
identity `[owner]`. Delete `GLOBAL_ADMIN_ID` and `ADMIN_TELEGRAM_IDS` handling.

- [ ] **Step 5: Make new order IDs and bot/payment links use App Settings**

Update `OrderService.generate_order_id()`:

```python
from src.database.services.app_settings_service import AppSettingsService

prefix = AppSettingsService(self.session).get_settings().order_prefix
return f"{prefix}{uuid.uuid4().hex[:8]}"
```

In PayOS order descriptions use `order.id[:9]`; top-ups use
`f"{settings.order_prefix}{topup.id}"[:9]`. Use `settings.bot_url` for return
and cancel URLs in both paths.

- [ ] **Step 6: Replace every former identity environment consumer**

Use the existing database session at each site:

```python
settings = AppSettingsService(session).get_settings()
```

Apply these exact mappings:

- `commands.start`: `settings.system_name`; append non-empty
  `support_line_1`/`support_line_2` after the translated help hint.
- `_api_menu_keyboard`: accept `api_docs_url: str` as an argument; load it in
  each handler's existing session and pass it instead of reading the environment.
- product-upload default header: `settings.system_name`.
- delivery file header: open a short session from the processor session factory,
  read `settings.system_name`, close it in `finally`.
- dashboard root response: inject `get_db`, return
  `{"message": f"{settings.system_name} Dashboard API", "version": "1.0.0"}`.

Do not expose support lines through the public settings endpoint.

- [ ] **Step 7: Verify all former owner/identity environment names are gone**

Run:

```bash
rtk pytest tests/test_admin_check.py tests/test_order_service.py tests/test_product_upload_api.py tests/test_ipn_idempotency.py -v
rtk rg -n "GLOBAL_ADMIN_ID|ADMIN_TELEGRAM_IDS|SYSTEM_NAME|SUPPORT_LINE_[12]|ORDER_PREFIX|API_DOCS_URL|PAYOS_RETURN_URL|PAYOS_CANCEL_URL" src
```

Expected: focused tests pass; `rg` reports no matches.

- [ ] **Step 8: Run backend regression tests and commit**

```bash
rtk pytest -q
rtk ruff check src tests
rtk git add src tests
rtk git commit -m "feat(config): use runtime operator settings"
```

Expected: tests pass; commit contains no `.env` or local data.

---

### Task 4: Make Branding and General Settings Editable in the Dashboard

**Files:**
- Create: `frontend/src/contexts/BrandingContext.tsx`
- Create: `frontend/src/contexts/BrandingContext.test.tsx`
- Create: `frontend/src/pages/GeneralSettingsPage.test.tsx`
- Create: `frontend/src/i18n/locales/vi/generalSettings.json`
- Create: `frontend/src/i18n/locales/en/generalSettings.json`
- Modify: `frontend/src/App.tsx:96-109`
- Modify: `frontend/src/main.tsx:8-18`
- Modify: `frontend/src/pages/GeneralSettingsPage.tsx:14-188`
- Modify: `frontend/src/pages/LoginPage.tsx:10-50`
- Modify: `frontend/src/app/layouts/Sidebar.tsx:35-52`
- Modify: `frontend/src/pages/ApiPage.tsx:120-145`
- Modify: `frontend/src/i18n/config.ts:8-55`

**Interfaces:**
- Consumes: Task 2 public/authenticated settings API.
- Produces: `BrandingProvider`, `useBranding(): { systemName: string; refresh(): Promise<void> }`, complete General Settings form payload.

- [ ] **Step 1: Write failing branding context tests**

Create `BrandingContext.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../shared/lib/api'
import { BrandingProvider, useBranding } from './BrandingContext'

vi.mock('../shared/lib/api', () => ({
  apiClient: { get: vi.fn() },
}))

function Probe() {
  const { systemName } = useBranding()
  return <span>{systemName}</span>
}

describe('BrandingProvider', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads the public system name', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { system_name: 'Example Shop' } })
    render(<BrandingProvider><Probe /></BrandingProvider>)
    await waitFor(() => expect(screen.getByText('Example Shop')).toBeInTheDocument())
  })

  it('keeps a generic fallback when the API is unavailable', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error('offline'))
    render(<BrandingProvider><Probe /></BrandingProvider>)
    expect(screen.getByText('Bot Order Admin')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run the test and verify the context is absent**

```bash
rtk npm test -- --run src/contexts/BrandingContext.test.tsx
```

Run from `frontend/`. Expected: module resolution fails for
`BrandingContext`.

- [ ] **Step 3: Implement the smallest shared branding context**

Create `BrandingContext.tsx`:

```tsx
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { apiClient } from '../shared/lib/api'

interface BrandingValue {
  systemName: string
  refresh: () => Promise<void>
}

const BrandingContext = createContext<BrandingValue | null>(null)

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [systemName, setSystemName] = useState('Bot Order Admin')
  const refresh = useCallback(async () => {
    try {
      const response = await apiClient.get<{ system_name: string }>('/api/app-settings/public')
      if (response.data.system_name.trim()) setSystemName(response.data.system_name.trim())
    } catch { /* generic fallback remains usable */ }
  }, [])
  useEffect(() => { void refresh() }, [refresh])
  const value = useMemo(() => ({ systemName, refresh }), [systemName, refresh])
  return <BrandingContext.Provider value={value}>{children}</BrandingContext.Provider>
}

export function useBranding(): BrandingValue {
  const value = useContext(BrandingContext)
  if (!value) throw new Error('useBranding must be used inside BrandingProvider')
  return value
}
```

Wrap both the normal `<App />` tree and standalone `<ApiPage />` render in
`BrandingProvider`. Replace three hard-coded brand labels with `systemName`.

- [ ] **Step 4: Write the failing General Settings save test**

Create `GeneralSettingsPage.test.tsx` using `ToastProvider` and
`BrandingProvider`. Mock the initial GET with all seven fields, change the
system-name input, submit, and assert the full PUT body:

```tsx
import i18n from '../i18n/config'

beforeEach(async () => {
  await i18n.changeLanguage('en')
})

expect(apiClient.put).toHaveBeenCalledWith('/api/app-settings', {
  system_name: 'Changed Shop',
  bot_url: 'https://t.me/example_shop_bot',
  support_line_1: '@support',
  support_line_2: '',
  timezone: 'UTC',
  order_prefix: 'SHOP',
  api_docs_url: 'https://shop.example/api',
})
```

Use `screen.getByLabelText('System name')`, `fireEvent.change`, and
`screen.getByRole('button', { name: 'Save' })` so the test also protects form
labels and accessibility.

- [ ] **Step 5: Expand the form and save one complete payload**

Replace the single timezone state with:

```tsx
interface AppSettingsResponse {
  system_name: string
  bot_url: string
  support_line_1: string
  support_line_2: string
  timezone: string
  order_prefix: string
  api_docs_url: string
}

const EMPTY_SETTINGS: AppSettingsResponse = {
  system_name: '',
  bot_url: '',
  support_line_1: '',
  support_line_2: '',
  timezone: 'Asia/Ho_Chi_Minh',
  order_prefix: 'ORD',
  api_docs_url: '',
}
```

Use one `settings` state and one saved-value ref. Render existing `Input`,
`FormField`, and `Select` components for all fields. Mark system name, bot URL,
timezone, and order prefix required. After a successful PUT, call
`await refresh()` from `useBranding()`.

- [ ] **Step 6: Add complete Vietnamese and English translation objects**

Each new JSON file must define `generalSettings` keys for description, load
error, save error/success, every label/hint, timezone note, and save shortcut.
Import and spread both files in `frontend/src/i18n/config.ts`; remove fallback-
only General Settings copy from JSX.

- [ ] **Step 7: Run frontend tests, lint, and build**

From `frontend/`:

```bash
rtk npm test -- --run src/contexts/BrandingContext.test.tsx src/pages/GeneralSettingsPage.test.tsx
rtk npm run lint
rtk npm run build
```

Expected: both tests pass, ESLint exits 0, TypeScript/Vite build exits 0.

- [ ] **Step 8: Commit the dashboard settings unit**

```bash
rtk git add frontend/src
rtk git commit -m "feat(dashboard): edit operator settings"
```

---

### Task 5: Make Docker Startup Deterministic and Observable

**Files:**
- Create: `tests/test_health_endpoints.py`
- Modify: `src/dashboard/main.py:1-150`
- Modify: `docker-compose.yml:1-175`
- Modify: `.env.example:1-50`
- Modify: `Dockerfile.api:40-75`
- Modify: `Dockerfile.bot:35-60`
- Modify: `entrypoint.sh:1-8`

**Interfaces:**
- Consumes: Task 1 PayOS-only environment; Task 2 settings database.
- Produces: `GET /health` liveness, `GET /ready` database readiness, Compose health ordering, supported four-service graph.

- [ ] **Step 1: Write failing liveness/readiness tests**

Create `tests/test_health_endpoints.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.dashboard.auth import get_db
from src.dashboard.main import app


def test_health_does_not_touch_database():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_ready_checks_database():
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/ready")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_503_when_database_fails():
    class BrokenSession:
        def execute(self, statement):
            raise RuntimeError("database unavailable")

    def override_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/ready")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
```

- [ ] **Step 2: Run the tests and confirm `/ready` is missing**

```bash
rtk pytest tests/test_health_endpoints.py -v
```

Expected: `/health` passes and both `/ready` tests receive 404.

- [ ] **Step 3: Add dependency-free liveness and database readiness**

In `src/dashboard/main.py` import `Depends`, `HTTPException`, `status`,
`sqlalchemy.text`, `sqlalchemy.orm.Session`, and `get_db`. Add:

```python
@app.get("/ready")
async def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logging.getLogger(__name__).error("Readiness database check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc
    return {"status": "ready"}
```

Keep `/health` exactly dependency-free.

- [ ] **Step 4: Rewrite Compose to the supported four-service graph**

Use required-value interpolation for secrets and no public PostgreSQL port:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: ${DB_NAME:?DB_NAME is required}
      POSTGRES_USER: ${DB_USER:?DB_USER is required}
      POSTGRES_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD is required}
    volumes:
      - ./data/postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \"$${POSTGRES_USER}\" -d \"$${POSTGRES_DB}\""]
      interval: 5s
      timeout: 5s
      retries: 12
    restart: unless-stopped

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    environment:
      DB_HOST: postgres
      DB_PORT: "5432"
      DB_NAME: ${DB_NAME:?DB_NAME is required}
      DB_USER: ${DB_USER:?DB_USER is required}
      DB_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD is required}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN is required}
      DASHBOARD_SECRET_KEY: ${DASHBOARD_SECRET_KEY:?DASHBOARD_SECRET_KEY is required}
      CORS_ORIGINS: ${CORS_ORIGINS:?CORS_ORIGINS is required}
      PAYOS_CLIENT_ID: ${PAYOS_CLIENT_ID:?PAYOS_CLIENT_ID is required}
      PAYOS_API_KEY: ${PAYOS_API_KEY:?PAYOS_API_KEY is required}
      PAYOS_CHECKSUM_KEY: ${PAYOS_CHECKSUM_KEY:?PAYOS_CHECKSUM_KEY is required}
    ports:
      - "${DASHBOARD_PORT:-8001}:8000"
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=2)"]
      interval: 10s
      timeout: 5s
      retries: 12
      start_period: 20s
    restart: unless-stopped
```

Define `bot` with the same database/Telegram/PayOS/owner variables and
`depends_on.api.condition: service_healthy`. Define `frontend` with
`VITE_API_BASE_URL` as a build argument, port
`${FRONTEND_PORT:-8082}:80`, and healthy API dependency. Do not include an IPN
or supplier service, custom network, or unused named volume declaration. Do
not use service-level `env_file`; list every consumed variable explicitly in
`environment` so `docker compose --env-file PATH ...` works without a root
`.env` file and the configuration surface remains auditable.

- [ ] **Step 5: Make `.env.example` the complete safe deployment inventory**

Use this order and no production-looking values:

```dotenv
# Public URLs
FRONTEND_URL=http://localhost:8082
VITE_API_BASE_URL=http://localhost:8001
CORS_ORIGINS=http://localhost:8082
DASHBOARD_PORT=8001
FRONTEND_PORT=8082

# Telegram
TELEGRAM_BOT_TOKEN=
BOT_OWNER_TELEGRAM_ID=

# PostgreSQL
DB_NAME=bot_order
DB_USER=bot_order
DB_PASSWORD=

# PayOS
PAYOS_CLIENT_ID=
PAYOS_API_KEY=
PAYOS_CHECKSUM_KEY=

# Dashboard signing
DASHBOARD_SECRET_KEY=
```

Do not include runtime App Settings, Pay2S, supplier, SQLite, bank-account, or
provider-selector values.

- [ ] **Step 6: Keep migrations in the API entrypoint and copy bootstrap scripts**

Keep `entrypoint.sh` minimal:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

echo "Running database migrations..."
alembic upgrade head
echo "Starting application..."
exec "$@"
```

Ensure `Dockerfile.api` copies `scripts/` and the executable entrypoint. Do not
run migrations from bot/frontend or add a second migration container.

- [ ] **Step 7: Validate health behavior and rendered Compose**

Create a temporary `.env` from `.env.example`, replace its empty values with
non-secret test values, then run:

```bash
rtk cp .env.example /tmp/bot-order-compose.env
rtk sed -i 's/^TELEGRAM_BOT_TOKEN=$/TELEGRAM_BOT_TOKEN=000000000:test-token/; s/^BOT_OWNER_TELEGRAM_ID=$/BOT_OWNER_TELEGRAM_ID=123456/; s/^DB_PASSWORD=$/DB_PASSWORD=ci-database-password/; s/^PAYOS_CLIENT_ID=$/PAYOS_CLIENT_ID=ci-client/; s/^PAYOS_API_KEY=$/PAYOS_API_KEY=ci-api-key/; s/^PAYOS_CHECKSUM_KEY=$/PAYOS_CHECKSUM_KEY=ci-checksum-key/; s/^DASHBOARD_SECRET_KEY=$/DASHBOARD_SECRET_KEY=ci-dashboard-secret/' /tmp/bot-order-compose.env
rtk pytest tests/test_health_endpoints.py -v
rtk docker compose --env-file /tmp/bot-order-compose.env config --services
rtk docker compose --env-file /tmp/bot-order-compose.env config -q
```

Expected services, one per line: `postgres`, `api`, `bot`, `frontend`.
`config -q` exits 0. Never create a repository `.env` during this check.

- [ ] **Step 8: Commit deterministic Docker startup**

```bash
rtk git add docker-compose.yml .env.example Dockerfile.api Dockerfile.bot entrypoint.sh src/dashboard/main.py tests/test_health_endpoints.py
rtk git commit -m "fix(docker): gate startup on readiness"
```

---

### Task 6: Add Transactional, Password-Safe System Bootstrap

**Files:**
- Create: `scripts/bootstrap_system.py`
- Create: `tests/test_bootstrap_system.py`
- Modify: `src/database/services/admin_service.py:55-95`
- Modify: `src/database/services/app_settings_service.py:23-100`
- Modify: `scripts/create_admin.py:1-104`
- Modify: `scripts/README.md`

**Interfaces:**
- Consumes: Task 2 service validation and AppSettings fields.
- Produces: `BootstrapPayload`, `bootstrap_system(session, payload) -> dict[str, bool]`, stdin-only CLI, commit-control arguments on existing services.

- [ ] **Step 1: Write failing bootstrap behavior tests**

Create `tests/test_bootstrap_system.py`:

```python
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scripts.bootstrap_system import BootstrapPayload, bootstrap_system
from src.database.models import Admin
from src.database.models.app_settings import AppSettings
from src.database.models.base import Base


def payload() -> BootstrapPayload:
    return BootstrapPayload.model_validate({
        "admin": {
            "username": "owner",
            "password": "long-password-123",
            "full_name": "System Owner",
            "email": "owner@example.test",
        },
        "settings": {
            "system_name": "Example Shop",
            "bot_url": "https://t.me/example_shop_bot",
            "support_line_1": "@support",
            "support_line_2": "",
            "timezone": "UTC",
            "order_prefix": "SHOP",
            "api_docs_url": "https://shop.example/api",
        },
    })


def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_bootstrap_creates_admin_and_settings():
    db = session()
    result = bootstrap_system(db, payload())
    assert result == {"admin_created": True, "settings_created": True}
    assert db.query(Admin).one().username == "owner"
    assert db.query(AppSettings).one().system_name == "Example Shop"


def test_bootstrap_rerun_preserves_existing_records():
    db = session()
    bootstrap_system(db, payload())
    result = bootstrap_system(db, payload())
    assert result == {"admin_created": False, "settings_created": False}
    assert db.query(Admin).count() == 1
    assert db.query(AppSettings).count() == 1


def test_invalid_payload_does_not_create_partial_records():
    db = session()
    invalid = payload().model_copy(deep=True)
    invalid.settings.order_prefix = "TU"
    try:
        bootstrap_system(db, invalid)
    except ValueError:
        pass
    assert db.query(Admin).count() == 0
    assert db.query(AppSettings).count() == 0
```

- [ ] **Step 2: Run tests and verify the bootstrap module is absent**

```bash
rtk pytest tests/test_bootstrap_system.py -v
```

Expected: collection fails for missing `scripts.bootstrap_system`.

- [ ] **Step 3: Let existing services participate in a caller-owned transaction**

Add `commit: bool = True` to `AdminService.create_admin()` and
`AppSettingsService.get_settings()/update_settings()`. Preserve existing
behavior by default:

```python
if commit:
    self.session.commit()
    self.session.refresh(record)
else:
    self.session.flush()
```

In `update_settings(commit=False)`, call `get_settings(commit=False)` so it
cannot commit halfway through bootstrap. Add:

```python
def settings_exist(self) -> bool:
    return self.session.query(AppSettings.id).filter_by(id=_SINGLETON_ID).first() is not None
```

- [ ] **Step 4: Implement typed stdin payload and one database transaction**

Create `scripts/bootstrap_system.py` with Pydantic models and these public
functions:

```python
class AdminPayload(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = None


class SettingsPayload(BaseModel):
    system_name: str
    bot_url: str
    support_line_1: str = ""
    support_line_2: str = ""
    timezone: str
    order_prefix: str
    api_docs_url: str = ""


class BootstrapPayload(BaseModel):
    admin: AdminPayload
    settings: SettingsPayload


def bootstrap_system(session: Session, payload: BootstrapPayload) -> dict[str, bool]:
    admin_service = AdminService(session)
    settings_service = AppSettingsService(session)
    admin_created = not admin_service.list_admins(include_inactive=True)
    settings_created = not settings_service.settings_exist()

    try:
        if admin_created:
            admin_service.create_admin(
                username=payload.admin.username,
                password_hash=get_password_hash(payload.admin.password),
                full_name=payload.admin.full_name.strip(),
                email=str(payload.admin.email) if payload.admin.email else None,
                role=AdminRole.ADMIN,
                commit=False,
            )
        if settings_created:
            settings_service.update_settings(
                **payload.settings.model_dump(),
                commit=False,
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {"admin_created": admin_created, "settings_created": settings_created}
```

`main()` must read exactly one JSON object with `json.load(sys.stdin)`, create
the normal engine/session, print only the two boolean result fields, close the
session, and return nonzero on failure. For `ValidationError`, print only the
invalid field paths from `exc.errors()`; never print input values.

- [ ] **Step 5: Remove insecure admin CLI defaults and argument passwords**

In `scripts/create_admin.py`, make username/full name required or interactive.
Delete `--password` and `admin123`. Read passwords with `getpass.getpass()` or
`--password-stdin`:

```python
password_group = parser.add_mutually_exclusive_group()
password_group.add_argument("--password-stdin", action="store_true")

if args.password_stdin:
    password = sys.stdin.readline().rstrip("\n")
else:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        parser.error("passwords do not match")
if len(password) < 12:
    parser.error("password must contain at least 12 characters")
```

Never print the password after creation. Document this secure command in
`scripts/README.md`.

- [ ] **Step 6: Add a subprocess test proving CLI output is secret-free**

Append a test that invokes `python -m scripts.bootstrap_system` against a
temporary SQLite `DATABASE_URL`, sends `json.dumps(payload().model_dump())`,
and asserts the password is absent from stdout/stderr. If PostgreSQL-only
connection policy prevents the CLI from accepting SQLite, monkeypatch
`create_engine_instance` and call `main()` with `io.StringIO` streams instead;
do not weaken production database validation.

- [ ] **Step 7: Run bootstrap/admin tests and commit**

```bash
rtk pytest tests/test_bootstrap_system.py tests/test_admin_service.py -v
rtk ruff check scripts/bootstrap_system.py scripts/create_admin.py src/database/services/admin_service.py src/database/services/app_settings_service.py tests/test_bootstrap_system.py
rtk git add scripts src/database/services tests/test_bootstrap_system.py
rtk git commit -m "feat(setup): add secure system bootstrap"
```

Expected: tests pass; no default dashboard password remains.

---

### Task 7: Add the One-Command Interactive Setup Wizard

**Files:**
- Create: `setup.sh`
- Modify: `.gitignore`
- Create/Modify: `tests/test_operator_scripts.py`

**Interfaces:**
- Consumes: Task 5 Compose/health graph; Task 6 stdin JSON bootstrap.
- Produces: executable `./setup.sh`; atomic mode-0600 `.env`; clean first run and safe rerun behavior.

- [ ] **Step 1: Write failing shell preflight and safe-rerun tests**

Create `tests/test_operator_scripts.py` with helpers that copy scripts into a
temporary project and put fake executables first in `PATH`:

```python
import os
import shutil
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "project"
    bin_dir = tmp_path / "bin"
    root.mkdir()
    bin_dir.mkdir()
    shutil.copy(ROOT / "setup.sh", root / "setup.sh")
    (root / "docker-compose.yml").write_text("services: {}\n")
    return root, bin_dir


def test_setup_refuses_to_overwrite_existing_env(tmp_path):
    root, bin_dir = project(tmp_path)
    existing = "DB_NAME=existing\n"
    (root / ".env").write_text(existing)
    executable(
        bin_dir / "docker",
        "#!/usr/bin/env bash\nexit 0\n",
    )
    executable(bin_dir / "git", "#!/usr/bin/env bash\nexit 0\n")
    result = subprocess.run(
        ["bash", "setup.sh"],
        cwd=root,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        input=(
            "Example Shop\nhttps://t.me/example_shop_bot\n@support\n\nUTC\n"
            "SHOP\nhttps://shop.example/api\nowner\nSystem Owner\n"
            "owner@example.test\nlong-password-123\nlong-password-123\n"
        ),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert (root / ".env").read_text() == existing
```

Add a missing-Docker test whose `PATH` contains a fake `git` but no `docker`;
assert a nonzero exit and `Docker is required`.

- [ ] **Step 2: Run the tests and confirm `setup.sh` is missing**

```bash
rtk pytest tests/test_operator_scripts.py -v
```

Expected: fixture copy fails because `setup.sh` does not exist.

- [ ] **Step 3: Implement strict preflight, prompts, and validators**

Start `setup.sh` with:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT_DIR"
TMP_ENV=""
trap '[[ -n "$TMP_ENV" ]] && rm -f "$TMP_ENV"' EXIT

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$2"; }
need git "Git is required"
need docker "Docker is required"
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin is required"
docker info >/dev/null 2>&1 || die "Docker daemon is not reachable"
```

Implement `prompt_required`, `prompt_default`, `prompt_secret_confirm`,
`validate_url`, `validate_positive_int`, and `random_hex` using Bash plus
`od`/`tr`. Reject newlines in every stored value. Validate production URLs as
absolute HTTP(S), Telegram owner as a positive integer, bot URL as
`https://t.me/...`, order prefix against `^[A-Z0-9]{2,8}$` and not `TU*`, and
password length at 12.

Use this prompt sequence so the wizard and its tests stay deterministic:

1. only when `.env` is absent: frontend URL, API URL, dashboard port, frontend
   port, Telegram token, bot owner Telegram ID, database name/user/password,
   three PayOS credentials; generate the dashboard signing secret;
2. on every run: system name, bot URL, two support lines, timezone, order
   prefix, API documentation URL, admin username/full name/email, then the
   confirmed admin password.

- [ ] **Step 4: Render `.env` atomically without evaluating input**

If `.env` is absent, collect deployment values and render only fixed keys:

```bash
umask 077
TMP_ENV="$(mktemp "${ROOT_DIR}/.env.tmp.XXXXXX")"
{
  printf 'FRONTEND_URL=%s\n' "$frontend_url"
  printf 'VITE_API_BASE_URL=%s\n' "$api_url"
  printf 'CORS_ORIGINS=%s\n' "$frontend_url"
  printf 'DASHBOARD_PORT=%s\n' "$dashboard_port"
  printf 'FRONTEND_PORT=%s\n' "$frontend_port"
  printf 'TELEGRAM_BOT_TOKEN=%s\n' "$telegram_token"
  printf 'BOT_OWNER_TELEGRAM_ID=%s\n' "$owner_id"
  printf 'DB_NAME=%s\n' "$db_name"
  printf 'DB_USER=%s\n' "$db_user"
  printf 'DB_PASSWORD=%s\n' "$db_password"
  printf 'PAYOS_CLIENT_ID=%s\n' "$payos_client_id"
  printf 'PAYOS_API_KEY=%s\n' "$payos_api_key"
  printf 'PAYOS_CHECKSUM_KEY=%s\n' "$payos_checksum_key"
  printf 'DASHBOARD_SECRET_KEY=%s\n' "$dashboard_secret"
} >"$TMP_ENV"
docker compose --env-file "$TMP_ENV" config -q
mv "$TMP_ENV" .env
TMP_ENV=""
chmod 600 .env
```

Never `source .env`. On rerun, print `Using existing .env` and validate it with
Compose without rewriting it. Read only the fixed public keys needed for the
completion message with a non-evaluating helper:

```bash
env_value() {
  local key="$1"
  sed -n "s/^${key}=//p" .env | tail -n 1
}

frontend_url="$(env_value FRONTEND_URL)"
api_url="$(env_value VITE_API_BASE_URL)"
```

The key argument is always a hard-coded identifier, never user input.

- [ ] **Step 5: Start dependencies, wait for readiness, and bootstrap via stdin**

Implement:

```bash
wait_ready() {
  local attempt
  for attempt in $(seq 1 60); do
    if docker compose exec -T api python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=2)" \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

docker compose up -d postgres api
wait_ready || die "API did not become ready; run ./manage.sh logs api"
```

Implement `json_string()` that escapes backslash, double quote, carriage
return, newline, and tab before `printf`. Build the fixed JSON object from the
prompted admin/settings values and pipe it directly:

```bash
json_string() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\t'/\\t}"
  printf '"%s"' "$value"
}

printf '%s' "$bootstrap_json" |
  docker compose exec -T api python scripts/bootstrap_system.py
unset admin_password bootstrap_json

docker compose up -d --build bot frontend
wait_ready || die "System started but readiness verification failed"
```

The JSON and password must never be echoed. Existing bootstrap records are
reported as preserved by the Python command.

- [ ] **Step 6: Print derived endpoints and operational next steps**

Print `FRONTEND_URL`, `${VITE_API_BASE_URL}/docs`, bot URL,
`${VITE_API_BASE_URL}/api/payos/webhook`, and these commands:

```text
./manage.sh status
./manage.sh logs bot
./manage.sh backup
```

State explicitly that the webhook URL must be registered in the PayOS merchant
dashboard.

- [ ] **Step 7: Extend shell tests through a fake successful first run**

The fake `docker` executable must append arguments to `$COMMAND_LOG`, return
success for `compose version`, `info`, `compose config`, `compose up`,
`compose exec`, and consume stdin for the bootstrap exec. Feed fixed answers to
the setup process and assert:

```python
assert result.returncode == 0
assert oct((root / ".env").stat().st_mode & 0o777) == "0o600"
assert "PAY2S" not in (root / ".env").read_text()
assert "admin-password-123" not in result.stdout + result.stderr
```

- [ ] **Step 8: Verify script syntax/behavior and commit**

```bash
rtk bash -n setup.sh
rtk pytest tests/test_operator_scripts.py -v
rtk git add setup.sh tests/test_operator_scripts.py .gitignore
rtk git commit -m "feat(setup): add Docker setup wizard"
```

Add `backups/`, `.codegraph/`, `.agents/`, `.claude/`, `.codex/`, `.env*`, and
`!.env.example` to `.gitignore` without touching the user's untracked
`.codegraph/` directory.

---

### Task 8: Add Safe Lifecycle, Backup, Restore, and Update Commands

**Files:**
- Create: `manage.sh`
- Modify: `scripts/backup_database.sh:1-45`
- Modify: `scripts/restore_database.sh:1-75`
- Modify: `tests/test_operator_scripts.py`
- Modify: `OPERATIONS.md` (temporary command reference; Task 9 completes it)

**Interfaces:**
- Consumes: Task 5 health endpoints/Compose; Task 7 root/script conventions.
- Produces: `./manage.sh {start|stop|restart|status|logs|doctor|backup|restore|update|help}` and database scripts that use container-side PostgreSQL environment.

- [ ] **Step 1: Add failing command-dispatch and update-ordering tests**

Extend the temporary project helper to copy `manage.sh` and database scripts.
Add:

```python
def test_manage_help_lists_supported_commands(tmp_path):
    root, bin_dir = project(tmp_path)
    shutil.copy(ROOT / "manage.sh", root / "manage.sh")
    result = subprocess.run(
        ["bash", "manage.sh", "help"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    for command in ("start", "stop", "restart", "status", "logs", "doctor", "backup", "restore", "update"):
        assert command in result.stdout


def test_update_refuses_dirty_tracked_worktree(tmp_path):
    root, bin_dir = project(tmp_path)
    shutil.copy(ROOT / "manage.sh", root / "manage.sh")
    (root / ".env").write_text("DB_NAME=test\n")
    executable(bin_dir / "docker", "#!/usr/bin/env bash\nexit 0\n")
    executable(
        bin_dir / "git",
        "#!/usr/bin/env bash\n[[ \"$1 $2\" == \"diff --quiet\" ]] && exit 1\nexit 0\n",
    )
    result = subprocess.run(
        ["bash", "manage.sh", "update"],
        cwd=root,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "tracked changes" in result.stderr
```

Add a fake-command log test asserting `backup` occurs before `git pull` and
`docker compose up -d --build`.

- [ ] **Step 2: Run the focused tests and verify `manage.sh` is absent**

```bash
rtk pytest tests/test_operator_scripts.py -v
```

Expected: failures report missing `manage.sh`.

- [ ] **Step 3: Implement shared checks and health polling in `manage.sh`**

Start with:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT_DIR"
COMPOSE=(docker compose)

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
require_env() { [[ -f .env ]] || die ".env is missing; run ./setup.sh"; }
compose_check() { require_env; "${COMPOSE[@]}" config -q; }
wait_ready() {
  local attempt
  for attempt in $(seq 1 60); do
    if "${COMPOSE[@]}" exec -T api python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=2)" \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}
```

`help` must run without Docker or `.env`; all state-changing commands call
`compose_check` first.

- [ ] **Step 4: Implement non-destructive lifecycle commands**

Use this dispatch behavior:

```bash
case "${1:-help}" in
  start)
    compose_check
    "${COMPOSE[@]}" up -d
    wait_ready || die "API readiness failed; run ./manage.sh logs api"
    ;;
  stop)
    compose_check
    "${COMPOSE[@]}" stop
    ;;
  restart)
    compose_check
    "${COMPOSE[@]}" up -d --build --force-recreate
    wait_ready || die "API readiness failed after restart"
    ;;
  status)
    compose_check
    "${COMPOSE[@]}" ps
    wait_ready || die "containers are present but API/database is not ready"
    ;;
  logs)
    compose_check
    service="${2:-}"
    case "$service" in ""|api|bot|frontend|postgres) ;; *) die "unknown service: $service" ;; esac
    if [[ -n "$service" ]]; then
      "${COMPOSE[@]}" logs --tail=200 -f "$service"
    else
      "${COMPOSE[@]}" logs --tail=200 -f
    fi
    ;;
esac
```

`doctor` checks Docker/Compose, `.env` existence and mode, Compose rendering,
at least 1 GiB free space from `df -Pk`, Compose state, PostgreSQL health, and
API readiness. Print one `[ok]`/`[fail]` line per check and exit nonzero when a
required check fails.

- [ ] **Step 5: Make backups atomic and independent of host environment**

Replace `scripts/backup_database.sh` with strict root-relative logic:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"
mkdir -p backups
name="${1:-backup_$(date -u +%Y%m%d_%H%M%S)}"
[[ "$name" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Invalid backup name" >&2; exit 1; }
target="backups/${name}.sql"
tmp="${target}.tmp"
trap 'rm -f "$tmp"' EXIT

docker compose exec -T postgres sh -c \
  'exec pg_dump -U "$POSTGRES_USER" --clean --if-exists "$POSTGRES_DB"' \
  >"$tmp"
[[ -s "$tmp" ]] || { echo "Backup is empty" >&2; exit 1; }
mv "$tmp" "$target"
trap - EXIT
printf '%s\n' "$target"
```

`manage.sh backup [name]` calls this script and propagates its exit code/path.

- [ ] **Step 6: Restore the clean SQL dump without rebuilding database names**

Replace `scripts/restore_database.sh` with:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"
file="${1:-}"
[[ -n "$file" && -s "$file" ]] || { echo "A non-empty backup file is required" >&2; exit 1; }
read -r -p "Type RESTORE to replace the current database: " confirmation
[[ "$confirmation" == "RESTORE" ]] || { echo "Restore cancelled"; exit 0; }

docker compose stop bot api
docker compose up -d postgres
for attempt in $(seq 1 30); do
  docker compose exec -T postgres sh -c \
    'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1 && break
  [[ "$attempt" == 30 ]] && { echo "PostgreSQL not ready" >&2; exit 1; }
  sleep 2
done
docker compose exec -T postgres sh -c \
  'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  <"$file"
docker compose up -d api bot frontend
```

The dump already contains `--clean --if-exists`; do not interpolate database
identifiers into SQL or drop/recreate the database.

- [ ] **Step 7: Implement backup-first, fast-forward-only update**

Add to `manage.sh`:

```bash
update_system() {
  compose_check
  git diff --quiet || die "tracked changes must be committed or reverted before update"
  git diff --cached --quiet || die "staged tracked changes block update"

  local previous backup
  previous="$(git rev-parse HEAD)"
  backup="$(scripts/backup_database.sh "pre_update_$(date -u +%Y%m%d_%H%M%S)")"
  printf 'Backup: %s\nPrevious commit: %s\n' "$backup" "$previous"
  git pull --ff-only
  "${COMPOSE[@]}" up -d --build
  if ! wait_ready; then
    printf 'Update failed readiness. Previous commit: %s Backup: %s\n' \
      "$previous" "$backup" >&2
    return 1
  fi
}
```

Inside repository scripts call plain `git`; `rtk` is an agent-shell requirement
and is not installed for end users.

- [ ] **Step 8: Run shell behavior tests and a local backup dry check**

```bash
rtk bash -n manage.sh scripts/backup_database.sh scripts/restore_database.sh
rtk pytest tests/test_operator_scripts.py -v
```

Expected: syntax checks and fake-command tests pass. Do not run restore against
the user's database during automated verification.

- [ ] **Step 9: Commit the operations unit**

```bash
rtk git add manage.sh scripts/backup_database.sh scripts/restore_database.sh tests/test_operator_scripts.py OPERATIONS.md
rtk git commit -m "feat(ops): add system lifecycle commands"
```

---

### Task 9: Publish Complete Documentation, License, and Governance

**Files:**
- Create: `LICENSE`
- Create: `SECURITY.md`
- Create: `CONTRIBUTING.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `ROADMAP.md`
- Create: `docs/INSTALLATION.md`
- Create: `docs/CONFIGURATION.md`
- Create: `docs/ARCHITECTURE.md`
- Modify: `README.md`
- Modify: `OPERATIONS.md`
- Modify: `AGENTS.md`, `CLAUDE.md`
- Modify: `frontend/README.md`, `scripts/README.md`
- Delete: tracked `.claude/` directory

**Interfaces:**
- Consumes: all commands, fields, endpoints, and supported services from Tasks 1-8.
- Produces: one authoritative public document per concern; AGPL-3.0 project terms; experimental supplier boundary.

- [ ] **Step 1: Add the canonical license and conduct/security policies**

Create `LICENSE` with the unmodified GNU Affero General Public License version
3 text from `https://www.gnu.org/licenses/agpl-3.0.txt`; its first line must be
`GNU AFFERO GENERAL PUBLIC LICENSE` and it must include section 13, “Remote
Network Interaction”.

Create `CODE_OF_CONDUCT.md` from Contributor Covenant 2.1. Use GitHub private
reporting to repository owners as the enforcement contact; do not add a
personal email or phone number.

Create `SECURITY.md` with exact policies:

```markdown
# Security Policy

## Supported versions

Only the latest published release receives security fixes.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for this repository. Do not open a
public issue for an undisclosed vulnerability and do not include credentials,
customer records, delivery inventory, or payment payloads in reports.

Include the affected version, reachable attack path, impact, reproduction
steps, and a suggested remediation when available. Maintainers acknowledge a
report within seven calendar days and coordinate disclosure after a fix is
available.

## Secret handling

Never commit `.env`, database dumps, backups, Telegram tokens, PayOS keys, JWT
keys, customer data, or delivery inventory. Rotate a credential immediately if
it enters Git history; deleting the current file is not sufficient.
```

- [ ] **Step 2: Rewrite README as the five-minute public entry point**

Use these top-level sections in order:

```markdown
# Bot Order System
## What it does
## Supported stack
## Requirements
## Quick start
## First login and PayOS webhook
## Routine operations
## Experimental supplier code
## Documentation
## Contributing
## License
```

Quick start begins after clone:

```bash
chmod +x setup.sh manage.sh
./setup.sh
./manage.sh status
```

List exactly `postgres`, `api`, `bot`, and `frontend`. State PostgreSQL-only,
PayOS-only, Docker Compose-only, Vietnamese default/English available, and
supplier experimental. Link every deeper document using relative Markdown
links. Remove SQLite, Pay2S, raw multi-terminal startup, default admin
credentials, disabled IPN service, and five-container claims.

- [ ] **Step 3: Write installation and configuration references**

`docs/INSTALLATION.md` must cover, in order:

1. supported OS and Docker/Compose/Git verification;
2. BotFather bot creation and finding the numeric owner ID;
3. PayOS client/API/checksum key acquisition;
4. DNS/HTTPS responsibility and public frontend/API URLs;
5. every `setup.sh` prompt, hidden secret behavior, and safe rerun behavior;
6. exact PayOS webhook path `/api/payos/webhook`;
7. first dashboard login and General Settings review;
8. `manage.sh doctor`, Telegram `/start`, and PayOS sandbox verification;
9. uninstall behavior that preserves or removes data explicitly.

`docs/CONFIGURATION.md` contains two tables. The `.env` table includes each
Task 5 variable with columns `Name`, `Required`, `Secret`, `Validation`,
`Default`, `Change method`, and `Restart/rebuild`. The App Settings table
includes all seven Task 2 fields and notes that order-prefix changes affect
new orders only. State that `.env` is never dashboard-editable or committed.

- [ ] **Step 4: Write architecture and operations references**

`docs/ARCHITECTURE.md` contains:

- the four-service graph and trust boundaries;
- volume/bind-mount ownership;
- product order flow for PayOS and balance;
- top-up flow and `TU` dispatch invariant;
- FastAPI webhook signature/amount/idempotence path;
- service-layer-only database rule;
- runtime settings vs deployment secret boundary;
- experimental supplier code boundary.

Rewrite `OPERATIONS.md` around `manage.sh` with one section per command,
expected output/exit semantics, update backup-first behavior, backup retention,
quarterly restore drills, logs, health endpoints, credential rotation,
dashboard/Telegram admin management, and symptom-driven troubleshooting. Raw
Compose commands may appear only in a clearly labeled break-glass section.

- [ ] **Step 5: Add contribution guidance and public roadmap**

`CONTRIBUTING.md` specifies Docker setup, feature branches, Alembic requirement,
service-layer access, bot i18n/edit-in-place conventions, tests/lint/build,
secret prohibition, and a pull-request checklist.

`ROADMAP.md` contains:

```markdown
# Roadmap

## v0.1.0 beta
- Docker setup and lifecycle scripts
- PayOS-only payment and balance flows
- Editable operator identity
- Public documentation and release gates

## v1.0.0
- One stable operating cycle
- No unresolved installation, payment, update, backup, or restore blocker

## After v1
1. Stabilize supplier workflows before adding an opt-in Compose profile.
2. Publish signed multi-architecture images.
3. Add an optional reverse-proxy/TLS profile.
4. Add guided credential rotation and audited admin recovery.
5. Add migration previews and supported release channels when usage warrants them.
```

- [ ] **Step 6: Update contributor-facing repository guides and remove local tooling**

Update `AGENTS.md` and `CLAUDE.md` to the four-service/PayOS-only commands and
new setup/management interfaces. Update frontend/scripts READMEs to link the
root authoritative docs instead of duplicating installation.

Delete tracked `.claude/` notes, plans, vendored skills, and data with
`apply_patch`. Keep root `AGENTS.md`, `CLAUDE.md`, and `docs/superpowers/`.

- [ ] **Step 7: Check documentation for contradictions and personal data**

Run:

```bash
rtk rg -n -i "sqlite|pay2s|admin123|five containers|ipn-server|SUPPLIER_TELEGRAM_BOT_TOKEN" README.md OPERATIONS.md docs SECURITY.md CONTRIBUTING.md ROADMAP.md AGENTS.md CLAUDE.md frontend/README.md scripts/README.md
rtk rg -n "TELEGRAM_BOT_TOKEN=.+|PAYOS_(API_KEY|CHECKSUM_KEY)=.+|DB_PASSWORD=.+|DASHBOARD_SECRET_KEY=.+" . --glob '!docs/superpowers/**' --glob '!.env.example' --glob '!tests/**'
rtk git diff --check
```

Expected: the first scan matches only explicit historical/experimental
explanations that agree with this plan; the credential-value scan has no
matches; diff check exits 0.

- [ ] **Step 8: Commit documentation and governance**

```bash
rtk git add -A
rtk git commit -m "docs: prepare public AGPL release"
```

Review the staged list before commit; it must not include `.env`, `.codegraph`,
data, backups, dumps, or delivery files.

---

### Task 10: Add Blocking Public-Release CI and Rehearse the Clean Snapshot

**Files:**
- Create: `scripts/check_public_tree.sh`
- Modify: `.github/workflows/ci.yml`
- Modify: `.gitignore`, `.dockerignore`
- Modify: `README.md`, `ROADMAP.md` after rehearsal results

**Interfaces:**
- Consumes: Tasks 1-9 complete tree and commands.
- Produces: blocking backend/frontend/shell/Compose/secret/license gates and a repeatable fresh-history publication checklist.

- [ ] **Step 1: Create a local public-tree guard**

Create `scripts/check_public_tree.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

for forbidden in .env '*.db' '*.sqlite' '*.sql' '*.dump' '*.pem' '*.key' 'backups/*' 'data/*' '.claude/*'; do
  if [[ -n "$(git ls-files -- "$forbidden")" ]]; then
    echo "Tracked private artifact matches: $forbidden" >&2
    exit 1
  fi
done

docker run --rm -v "$ROOT_DIR:/repo" zricethezav/gitleaks:v8.30.1 \
  dir /repo --redact --no-banner
```

The exact Gitleaks version is intentionally pinned. Do not add allowlist
entries for genuine credentials.

- [ ] **Step 2: Make backend/frontend checks blocking in CI**

Update `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: python -m pip install --upgrade pip
      - run: pip install -r requirements.txt pip-licenses==5.5.5
      - env:
          DASHBOARD_SECRET_KEY: ci-test-secret
        run: pytest -q --ignore=tests/test_database_connection.py
      - run: ruff check .
      - run: pip-licenses --from=mixed --fail-on="UNKNOWN"

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm test -- --run
      - run: npm run lint
      - run: npm run build
```

Remove `continue-on-error` from Ruff.

- [ ] **Step 3: Add shell, Compose, secret, and dependency review jobs**

Add jobs:

```yaml
  release-hygiene:
    runs-on: ubuntu-latest
    env:
      FRONTEND_URL: http://localhost:8082
      VITE_API_BASE_URL: http://localhost:8001
      CORS_ORIGINS: http://localhost:8082
      TELEGRAM_BOT_TOKEN: 000000000:test-token
      BOT_OWNER_TELEGRAM_ID: "123456"
      DB_NAME: bot_order
      DB_USER: bot_order
      DB_PASSWORD: ci-database-password
      PAYOS_CLIENT_ID: ci-client
      PAYOS_API_KEY: ci-api-key
      PAYOS_CHECKSUM_KEY: ci-checksum-key
      DASHBOARD_SECRET_KEY: ci-dashboard-secret
    steps:
      - uses: actions/checkout@v4
      - run: bash -n setup.sh manage.sh scripts/backup_database.sh scripts/restore_database.sh scripts/check_public_tree.sh
      - run: cp .env.example .env
      - run: docker compose config -q
      - run: test "$(docker compose config --services | sort | tr '\n' ' ')" = "api bot frontend postgres "
      - run: scripts/check_public_tree.sh

  dependency-review:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/dependency-review-action@v4
        with:
          fail-on-severity: moderate
          license-check: true
```

After Compose validation, remove `.env` in the same job with an `if: always()`
cleanup step.

- [ ] **Step 4: Run the full local release gate**

```bash
rtk pytest -q
rtk ruff check .
rtk npm test -- --run
rtk npm run lint
rtk npm run build
rtk bash -n setup.sh manage.sh scripts/backup_database.sh scripts/restore_database.sh scripts/check_public_tree.sh
rtk docker compose --env-file /tmp/bot-order-compose.env config -q
rtk bash scripts/check_public_tree.sh
```

Run frontend commands from `frontend/`. Expected: every command exits 0.
Gitleaks 8.30.1 is the pinned release used by the plan.

- [ ] **Step 5: Perform manual system rehearsals on a clean Linux host**

Record evidence for all seven acceptance checks:

1. clean clone → `./setup.sh` → all four services healthy;
2. PayOS sandbox product payment and fulfillment;
3. PayOS sandbox top-up and balance credit;
4. balance-paid order fulfillment;
5. General Settings change visible in bot/dashboard without image rebuild;
6. backup, destructive restore, and data verification;
7. setup rerun, successful update, and controlled failed-update report.

Do not use production customer data or credentials in rehearsal artifacts.

- [ ] **Step 6: Create and scan a fresh-history publication candidate**

Outside the working repository:

```bash
rtk git archive --format=tar HEAD > /tmp/bot-order-public.tar
mkdir -p /tmp/bot-order-public
tar -xf /tmp/bot-order-public.tar -C /tmp/bot-order-public
cd /tmp/bot-order-public
git init
git add .
git commit -m "chore: publish initial source release"
docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8.30.1 git /repo --redact --no-banner
```

Expected: one sanitized root commit and no leak findings. Inspect
`git ls-files` before connecting a public remote. The old private `.git`
directory must never be copied or pushed.

- [ ] **Step 7: Require the operator's credential-rotation confirmation**

Before any public push, obtain explicit confirmation that every credential
ever committed in the private repository has been revoked or rotated,
including the removed Pay2S credentials. Code deletion and fresh history do
not revoke a credential.

- [ ] **Step 8: Commit CI/release gates and tag only after rehearsal**

```bash
rtk git add .github/workflows/ci.yml scripts/check_public_tree.sh .gitignore .dockerignore README.md ROADMAP.md
rtk git commit -m "ci: enforce public release gates"
```

After the clean public repository CI passes and manual evidence is reviewed,
create annotated tag `v0.1.0`. Do not tag `v1.0.0` until the stable-cycle gate
in `ROADMAP.md` is met.

## Post-v1 Roadmap (Not Part of This Implementation)

1. Supplier support: reconnect and test all supplier API/dashboard/bot flows,
   then add an opt-in Compose profile.
2. Distribution: publish signed, versioned amd64/arm64 images.
3. Edge deployment: add an optional reverse-proxy/TLS profile.
4. Recovery: guided credential rotation and audited dashboard-admin recovery.
5. Upgrade safety: migration previews and supported release channels after
   operator volume justifies their maintenance cost.

Do not scaffold these items during Tasks 1-10.
