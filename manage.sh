#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT_DIR"
COMPOSE=(docker compose)

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
require_env() { [[ -f .env ]] || die ".env is missing; run ./setup.sh"; }
compose_check() {
  require_env
  "${COMPOSE[@]}" config -q >/dev/null 2>&1 || die "Compose configuration is invalid"
}

wait_ready() {
  local attempt
  for ((attempt = 1; attempt <= 60; attempt++)); do
    if "${COMPOSE[@]}" exec -T api python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=2)" \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

help() {
  cat <<'EOF'
Usage: ./manage.sh COMMAND [ARG]

Commands:
  start             Start the system and wait for API readiness
  stop              Stop all services without deleting data
  restart           Rebuild and recreate services
  status            Show services and verify readiness
  logs [service]    Follow the last 200 log lines
  doctor            Check host, Compose, database, and API health
  backup [name]     Create an atomic PostgreSQL backup
  restore FILE      Restore FILE after typing RESTORE
  update            Back up, fast-forward pull, rebuild, and verify
  help              Show this help
EOF
}

all_services_running() {
  local configured running service
  configured="$("${COMPOSE[@]}" config --services 2>/dev/null)" || return 1
  running="$("${COMPOSE[@]}" ps --services --status running 2>/dev/null)" || return 1
  [[ -n "$configured" ]] || return 1
  while IFS= read -r service; do
    [[ -z "$service" ]] || grep -Fxq -- "$service" <<<"$running" || return 1
  done <<<"$configured"
}

doctor() {
  local available mode failures=0

  doctor_check() {
    local label="$1"
    shift
    if "$@" >/dev/null 2>&1; then
      printf '[ok] %s\n' "$label"
    else
      printf '[fail] %s\n' "$label"
      failures=1
    fi
  }

  doctor_check "Docker CLI" command -v docker
  doctor_check "Docker daemon" docker info
  doctor_check "Docker Compose plugin" docker compose version

  if [[ -f .env ]]; then
    printf '[ok] .env exists\n'
    mode="$(stat -c '%a' .env 2>/dev/null || true)"
    if [[ "$mode" == 600 ]]; then
      printf '[ok] .env permissions are 600\n'
    else
      printf '[fail] .env permissions are 600\n'
      failures=1
    fi
  else
    printf '[fail] .env exists\n'
    printf '[fail] .env permissions are 600\n'
    failures=1
  fi

  doctor_check "Compose configuration" docker compose config -q
  available="$(df -Pk "$ROOT_DIR" 2>/dev/null | awk 'END {print $4}')" || available=""
  if [[ "$available" =~ ^[0-9]+$ ]] && ((available >= 1048576)); then
    printf '[ok] at least 1 GiB disk space is free\n'
  else
    printf '[fail] at least 1 GiB disk space is free\n'
    failures=1
  fi
  doctor_check "all configured Compose services are running" all_services_running
  doctor_check "PostgreSQL readiness" docker compose exec -T postgres sh -c \
    'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
  doctor_check "API readiness" docker compose exec -T api python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=2)"

  return "$failures"
}

update_system() {
  compose_check
  git diff --quiet -- || die "tracked changes must be committed or reverted before update"
  git diff --cached --quiet -- || die "staged tracked changes block update"

  local previous backup
  previous="$(git rev-parse HEAD)"
  backup="$(scripts/backup_database.sh "pre_update_$(date -u +%Y%m%d_%H%M%S)")"
  printf 'Backup: %s\nPrevious commit: %s\n' "$backup" "$previous"
  if ! git pull --ff-only; then
    printf 'Update failed during pull. Previous commit: %s Backup: %s\n' \
      "$previous" "$backup" >&2
    return 1
  fi
  if ! "${COMPOSE[@]}" up -d --build; then
    printf 'Update failed during build. Previous commit: %s Backup: %s\n' \
      "$previous" "$backup" >&2
    return 1
  fi
  if ! wait_ready; then
    printf 'Update failed during readiness. Previous commit: %s Backup: %s\n' \
      "$previous" "$backup" >&2
    return 1
  fi
}

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
  doctor)
    doctor
    ;;
  backup)
    compose_check
    scripts/backup_database.sh "${2:-}"
    ;;
  restore)
    compose_check
    scripts/restore_database.sh "${2:-}"
    ;;
  update)
    update_system
    ;;
  help|-h|--help)
    help
    ;;
  *)
    die "unknown command: $1; run ./manage.sh help"
    ;;
esac
