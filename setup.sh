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

validate_stored() {
  local value="${1//$'\t'/}"
  [[ "$value" != *[[:cntrl:]]* ]]
}

prompt_required() {
  local prompt="$1"
  while true; do
    read -r -p "$prompt: " REPLY || die "Input ended before setup was complete"
    validate_stored "$REPLY" || { printf 'Values cannot contain unsupported control characters.\n' >&2; continue; }
    [[ -n "$REPLY" ]] && return
    printf 'A value is required.\n' >&2
  done
}

prompt_default() {
  local prompt="$1" default="$2"
  read -r -p "$prompt [$default]: " REPLY || die "Input ended before setup was complete"
  validate_stored "$REPLY" || die "Values cannot contain unsupported control characters"
  REPLY="${REPLY:-$default}"
}

prompt_secret_required() {
  local prompt="$1"
  while true; do
    read -r -s -p "$prompt: " REPLY || die "Input ended before setup was complete"
    printf '\n' >&2
    validate_stored "$REPLY" || { printf 'Values cannot contain unsupported control characters.\n' >&2; continue; }
    [[ -n "$REPLY" ]] && return
    printf 'A value is required.\n' >&2
  done
}

prompt_secret_confirm() {
  local first
  while true; do
    prompt_secret_required "Admin password"
    first="$REPLY"
    if (( ${#first} < 12 )); then
      printf 'Password must be at least 12 characters.\n' >&2
      continue
    fi
    prompt_secret_required "Confirm admin password"
    [[ "$first" == "$REPLY" ]] || { printf 'Passwords do not match.\n' >&2; continue; }
    REPLY="$first"
    return
  done
}

validate_url() {
  local url="$1" rest authority host port="" label
  local -a labels=()
  [[ "$url" =~ ^https?:// && "$url" != *[[:space:]]* ]] || return 1
  rest="${url#*://}"
  authority="${rest%%[/?#]*}"
  [[ -n "$authority" && "$authority" != *"@"* ]] || return 1

  if [[ "$authority" == \[* ]]; then
    [[ "$authority" =~ ^\[([0-9A-Fa-f:.]+)\](:([0-9]+))?$ ]] || return 1
    host="${BASH_REMATCH[1]}"
    port="${BASH_REMATCH[3]:-}"
    [[ "$host" == *:* && "$host" != *:::* ]] || return 1
  else
    [[ "$authority" != *:*:* ]] || return 1
    if [[ "$authority" == *:* ]]; then
      host="${authority%:*}"
      port="${authority##*:}"
      [[ -n "$port" ]] || return 1
    else
      host="$authority"
    fi
    (( ${#host} <= 253 )) || return 1
    IFS=. read -r -a labels <<< "$host"
    for label in "${labels[@]}"; do
      (( ${#label} <= 63 )) || return 1
      [[ "$label" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]] || return 1
    done
  fi

  if [[ -n "$port" ]]; then
    [[ "$port" =~ ^[0-9]+$ ]] && (( ${#port} <= 5 )) || return 1
    (( 10#$port >= 1 && 10#$port <= 65535 )) || return 1
  fi
}

validate_positive_int() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

prompt_url() {
  local prompt="$1" default="$2"
  while true; do
    prompt_default "$prompt" "$default"
    validate_url "$REPLY" && return
    printf 'Enter an absolute HTTP(S) URL.\n' >&2
  done
}

prompt_positive_int() {
  local prompt="$1" default="$2"
  while true; do
    prompt_default "$prompt" "$default"
    validate_positive_int "$REPLY" && return
    printf 'Enter a positive integer.\n' >&2
  done
}

random_hex() {
  od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
}

dotenv_value() {
  local value="${1//\'/\\\'}"
  printf "'%s'" "$value"
}

env_value() {
  local key="$1" value
  value="$(sed -n "s/^${key}=//p" .env | tail -n 1)"
  if [[ "$value" == \'*\' ]]; then
    value="${value:1:${#value}-2}"
    value="${value//\\\'/\'}"
  fi
  printf '%s' "$value"
}

if [[ -f .env ]]; then
  printf 'Using existing .env\n'
  docker compose --env-file .env config -q || die "Existing .env is not valid for Docker Compose"
else
  prompt_url "Frontend URL" "http://localhost:8082"
  frontend_url="$REPLY"
  prompt_url "API URL" "http://localhost:8001"
  api_url="$REPLY"
  prompt_positive_int "Dashboard port" "8001"
  dashboard_port="$REPLY"
  prompt_positive_int "Frontend port" "8082"
  frontend_port="$REPLY"
  prompt_secret_required "Telegram bot token"
  telegram_token="$REPLY"
  prompt_positive_int "Bot owner Telegram ID" ""
  owner_id="$REPLY"
  prompt_default "Database name" "mtkbot"
  db_name="$REPLY"
  prompt_default "Database user" "mtkbot"
  db_user="$REPLY"
  prompt_secret_required "Database password"
  db_password="$REPLY"
  prompt_secret_required "PayOS client ID"
  payos_client_id="$REPLY"
  prompt_secret_required "PayOS API key"
  payos_api_key="$REPLY"
  prompt_secret_required "PayOS checksum key"
  payos_checksum_key="$REPLY"
  dashboard_secret="$(random_hex)"

  umask 077
  TMP_ENV="$(mktemp "${ROOT_DIR}/.env.tmp.XXXXXX")"
  {
    printf 'FRONTEND_URL=%s\n' "$(dotenv_value "$frontend_url")"
    printf 'VITE_API_BASE_URL=%s\n' "$(dotenv_value "$api_url")"
    printf 'CORS_ORIGINS=%s\n' "$(dotenv_value "$frontend_url")"
    printf 'DASHBOARD_PORT=%s\n' "$(dotenv_value "$dashboard_port")"
    printf 'FRONTEND_PORT=%s\n' "$(dotenv_value "$frontend_port")"
    printf 'TELEGRAM_BOT_TOKEN=%s\n' "$(dotenv_value "$telegram_token")"
    printf 'BOT_OWNER_TELEGRAM_ID=%s\n' "$(dotenv_value "$owner_id")"
    printf 'DB_NAME=%s\n' "$(dotenv_value "$db_name")"
    printf 'DB_USER=%s\n' "$(dotenv_value "$db_user")"
    printf 'DB_PASSWORD=%s\n' "$(dotenv_value "$db_password")"
    printf 'PAYOS_CLIENT_ID=%s\n' "$(dotenv_value "$payos_client_id")"
    printf 'PAYOS_API_KEY=%s\n' "$(dotenv_value "$payos_api_key")"
    printf 'PAYOS_CHECKSUM_KEY=%s\n' "$(dotenv_value "$payos_checksum_key")"
    printf 'DASHBOARD_SECRET_KEY=%s\n' "$(dotenv_value "$dashboard_secret")"
  } > "$TMP_ENV"
  docker compose --env-file "$TMP_ENV" config -q || die "Generated environment is not valid for Docker Compose"
  mv "$TMP_ENV" .env
  TMP_ENV=""
  chmod 600 .env
fi

frontend_url="$(env_value FRONTEND_URL)"
api_url="$(env_value VITE_API_BASE_URL)"

prompt_required "System name"
system_name="$REPLY"
while true; do
  prompt_required "Bot URL"
  bot_url="$REPLY"
  [[ "$bot_url" =~ ^https://t\.me/[A-Za-z0-9_]+/?$ ]] && break
  printf 'Bot URL must start with https://t.me/.\n' >&2
done
prompt_default "Support line 1" ""
support_line_1="$REPLY"
prompt_default "Support line 2" ""
support_line_2="$REPLY"
prompt_default "Timezone" "Asia/Ho_Chi_Minh"
timezone="$REPLY"
while true; do
  prompt_default "Order prefix" "MTK"
  order_prefix="$REPLY"
  if [[ "$order_prefix" == TU* ]]; then
    printf 'Order prefix cannot start with TU.\n' >&2
  elif [[ ! "$order_prefix" =~ ^[A-Z0-9]{2,8}$ ]]; then
    printf 'Order prefix must be 2-8 uppercase letters or digits.\n' >&2
  else
    break
  fi
done
prompt_url "API documentation URL" "${api_url%/}/docs"
api_docs_url="$REPLY"
prompt_required "Admin username"
admin_username="$REPLY"
prompt_required "Admin full name"
admin_full_name="$REPLY"
prompt_required "Admin email"
admin_email="$REPLY"
prompt_secret_confirm
admin_password="$REPLY"

wait_ready() {
  local attempt
  for ((attempt = 1; attempt <= 60; attempt++)); do
    if docker compose exec -T api python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=2)" \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

json_string() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\t'/\\t}"
  printf '"%s"' "$value"
}

docker compose up -d postgres api
wait_ready || die "API did not become ready; run ./manage.sh logs api"

printf -v bootstrap_json \
  '{"admin":{"username":%s,"password":%s,"full_name":%s,"email":%s},"settings":{"system_name":%s,"bot_url":%s,"support_line_1":%s,"support_line_2":%s,"timezone":%s,"order_prefix":%s,"api_docs_url":%s}}' \
  "$(json_string "$admin_username")" \
  "$(json_string "$admin_password")" \
  "$(json_string "$admin_full_name")" \
  "$(json_string "$admin_email")" \
  "$(json_string "$system_name")" \
  "$(json_string "$bot_url")" \
  "$(json_string "$support_line_1")" \
  "$(json_string "$support_line_2")" \
  "$(json_string "$timezone")" \
  "$(json_string "$order_prefix")" \
  "$(json_string "$api_docs_url")"

printf '%s' "$bootstrap_json" |
  docker compose exec -T api python scripts/bootstrap_system.py
unset admin_password bootstrap_json

docker compose up -d --build bot frontend
wait_ready || die "System started but readiness verification failed"

printf '\nSetup complete.\n'
printf 'Frontend: %s\n' "$frontend_url"
printf 'API docs: %s/docs\n' "${api_url%/}"
printf 'Telegram bot: %s\n' "$bot_url"
printf 'PayOS webhook: %s/api/payos/webhook\n' "${api_url%/}"
printf 'Register the webhook URL in the PayOS merchant dashboard.\n\n'
printf 'Next commands:\n'
printf '  ./manage.sh status\n'
printf '  ./manage.sh logs bot\n'
printf '  ./manage.sh backup\n'
