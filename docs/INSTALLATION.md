# Installation

## 1. Supported host and prerequisites

The release-tested deployment target is a Linux host with Bash and GNU coreutils. WSL 2 can use the same Linux path when Docker integration is enabled. Native Windows shells are not supported. Docker Desktop on macOS can build the stack, but `./manage.sh doctor` currently uses GNU `stat -c`; install GNU coreutils or use a Linux host for the supported diagnostic path.

Install Git, Docker Engine or Docker Desktop, and the Docker Compose v2 plugin. Confirm the daemon is available to your account:

```bash
git --version
docker --version
docker compose version
docker info
```

The setup wizard stops immediately if any check fails. Reserve at least 1 GiB of free space before setup and additional space for PostgreSQL, delivery inventory, and backups.

## 2. Create the Telegram bot and find the owner ID

1. Open the verified [@BotFather](https://t.me/BotFather) account in Telegram.
2. Run `/newbot`, choose a display name and username, and store the issued token in a password manager. Never paste the token into an issue or chat.
3. Find the positive numeric Telegram user ID for the person who will own the bot. Use a trusted ID lookup method or the Telegram Bot API after sending the new bot a message; do not give the bot token to an untrusted lookup service.
4. Keep both values ready for `setup.sh`. The configured owner is always a Telegram administrator and is the only identity allowed to add or remove other bot administrators.

If you use the Bot API to inspect `getUpdates`, avoid putting the token directly in shell history and unset it immediately afterward.

## 3. Obtain PayOS credentials

Create or select a merchant channel in the [PayOS merchant dashboard](https://my.payos.vn/). Record its client ID, API key, and checksum key. All three are required and secret. The checksum key signs payment requests and verifies webhook data; it is not interchangeable with the API key.

Use PayOS sandbox or a merchant-provided test channel for the first end-to-end payment. This release has no payment-provider selector: PayOS is the only supported provider.

## 4. Prepare DNS, HTTPS, and public URLs

The Compose stack does not include a reverse proxy or TLS automation. The operator is responsible for:

- DNS records for the frontend and API hostnames.
- Valid HTTPS termination in front of the published frontend and API ports.
- Forwarding the public frontend hostname to `frontend` and the public API hostname to `api`.
- Keeping PostgreSQL private; Compose does not publish its port.

Choose two URLs before setup, for example `https://shop.example` and `https://api.shop.example`. `VITE_API_BASE_URL` is compiled into the frontend image, while `CORS_ORIGINS` controls which browser origins may call the API. The PayOS webhook must reach the public API URL.

For a local-only rehearsal the frontend and API prompts accept HTTP. When the API URL uses HTTP, the runtime **API documentation URL** defaults to empty; leave it empty or enter a separate HTTPS URL. When the API URL uses HTTPS, the prompt defaults to that URL plus `/docs`. Non-empty HTTP documentation URLs are rejected. The FastAPI documentation remains available at the API URL plus `/docs` either way.

## 5. Run the setup wizard

From the repository root:

```bash
chmod +x setup.sh manage.sh
./setup.sh
```

On the first run, when `.env` does not exist, the wizard asks for these deployment values in order:

1. **Frontend URL** — absolute HTTP(S) URL; defaults to `http://localhost:8082`.
2. **API URL** — absolute HTTP(S) URL; defaults to `http://localhost:8001`.
3. **Dashboard port** — positive host port; defaults to `8001`.
4. **Frontend port** — positive host port; defaults to `8082`.
5. **Telegram bot token** — required and hidden while entered.
6. **Bot owner Telegram ID** — required positive integer.
7. **Database name** — defaults to `bot_order`.
8. **Database user** — defaults to `bot_order`.
9. **Database password** — required and hidden while entered.
10. **PayOS client ID** — required and hidden while entered.
11. **PayOS API key** — required and hidden while entered.
12. **PayOS checksum key** — required and hidden while entered.

The wizard generates `DASHBOARD_SECRET_KEY`; it is not displayed or requested. Values are written through a mode-`600` temporary file and atomically moved to `.env`. Unsupported control characters are rejected, and secret prompts do not echo input.

The wizard then asks for runtime identity and the first administrator on every run:

1. **System name** — required, 1–80 characters after trimming.
2. **Bot URL** — required `https://t.me/...` bot URL.
3. **Support line 1** — optional, at most 200 characters.
4. **Support line 2** — optional, at most 200 characters.
5. **Timezone** — valid IANA name; defaults to `Asia/Ho_Chi_Minh`.
6. **Order prefix** — 2–8 uppercase letters or digits and cannot start with `TU`; defaults to `ORD` in the wizard.
7. **API documentation URL** — optional absolute HTTPS URL; defaults to the API URL plus `/docs` only when the API URL uses HTTPS, otherwise empty.
8. **Admin username** — 3–64 letters, digits, dots, underscores, or hyphens.
9. **Admin full name** — 1–120 characters.
10. **Admin email** — valid email address.
11. **Admin password and confirmation** — hidden, matching, and 12–256 characters.

Setup starts `postgres` and `api`, waits up to two minutes for readiness, bootstraps the first administrator and settings in one transaction, then builds and starts `bot` and `frontend` and verifies final API/database readiness.

### Safe reruns

When `.env` already exists, `setup.sh` validates and reuses it; it does not overwrite deployment URLs or secrets. It still asks for runtime settings and administrator details, but the bootstrap operation preserves any existing first administrator and settings. A rerun starts/rebuilds the supported services and does not remove PostgreSQL or delivery data.

To change deployment values, edit `.env` deliberately, keep its permissions at `600`, and follow the restart guidance in [Configuration](CONFIGURATION.md). Use General Settings for runtime identity instead of rerunning setup.

## 6. Register the PayOS webhook

After setup prints the API URL, register this exact path in the PayOS merchant dashboard:

```text
https://your-api.example/api/payos/webhook
```

Do not use the frontend hostname or append a trailing service-specific port unless that port is part of the public API URL. The endpoint verifies webhook data with `PAYOS_CHECKSUM_KEY` before processing a payment.

## 7. First dashboard login

Open the frontend URL printed by setup and sign in with the administrator username and password you entered. There are no compiled default credentials.

Open **General Settings** and review all seven fields. Confirm the bot URL, timezone, order prefix, support lines, and API documentation URL before accepting orders. Changes there are runtime database settings and do not require a container rebuild.

## 8. Verify the installation

Run the supported diagnostic:

```bash
./manage.sh doctor
```

Every line should report `[ok]`; the command exits nonzero if Docker, `.env` permissions, Compose configuration, disk capacity, a service, PostgreSQL, or API readiness fails.

Then:

1. Open the bot in Telegram and send `/start`.
2. Confirm the Vietnamese menu appears by default and that English can be selected.
3. Create a low-value PayOS sandbox product order and confirm the amount, webhook receipt, and delivery.
4. Create a sandbox top-up and confirm that the balance is credited exactly once.
5. Check the dashboard order, balance transaction, and inventory records.

Do not enable real payments until both sandbox paths work.

## 9. Uninstall or preserve data

There is no automated uninstall command. `./manage.sh stop` stops services without deleting data. PostgreSQL state lives under `data/postgres_data/`, transient generated delivery files use the project-scoped Docker volume `delivery_data`, and database dumps live under `backups/`.

To uninstall while preserving data, create and verify a database backup and stop the system before removing containers or the checkout. A database dump is the supported portable copy of orders and pre-uploaded inventory; do not treat a live PostgreSQL data directory as a backup. Compose does not delete the `delivery_data` volume on `stop` or ordinary `down`; avoid `down -v` until any interrupted delivery has been resolved.

To remove all data, first copy any verified backup you intend to retain to protected off-host storage and confirm that no interrupted delivery or other retention requirement remains. Then, from the repository root, run this intentional destructive raw Compose command before deleting the checkout:

```bash
docker compose down -v
```

The `-v` flag removes the project-scoped `delivery_data` volume along with the containers. After that command succeeds, delete the checkout including `data/` and `backups/`; this permanently removes the database, delivery inventory, and any backup left inside the checkout. Do not use this remove-all path when preserving data.

Continue with [Configuration](CONFIGURATION.md), [Architecture](ARCHITECTURE.md), and [Operations](../OPERATIONS.md).
