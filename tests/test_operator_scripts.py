import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PATH = "/usr/bin:/bin"
DOCTOR_LABELS = (
    "Docker CLI",
    "Docker daemon",
    "Docker Compose plugin",
    ".env exists",
    ".env permissions are 600",
    "Compose configuration",
    "at least 1 GiB disk space is free",
    "all configured Compose services are running",
    "PostgreSQL readiness",
    "API readiness",
)


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


def operator_project(tmp_path: Path) -> tuple[Path, Path]:
    root, bin_dir = project(tmp_path)
    scripts = root / "scripts"
    scripts.mkdir()
    for name in ("backup_database.sh", "restore_database.sh"):
        shutil.copy(ROOT / "scripts" / name, scripts / name)
    manage = ROOT / "manage.sh"
    if manage.exists():
        shutil.copy(manage, root / "manage.sh")
    return root, bin_dir


def fake_tools(bin_dir: Path) -> None:
    executable(bin_dir / "git", "#!/usr/bin/env bash\nexit 0\n")
    executable(
        bin_dir / "docker",
        r"""#!/usr/bin/env bash
decode_compose_value() {
  local value="$1" output="" char escaped index length="${#1}"
  if [[ "$value" != \"* ]]; then
    printf '%s' "$value"
    return
  fi
  for ((index = 1; index < length; index++)); do
    char="${value:index:1}"
    if [[ "$char" == '"' ]]; then
      (( index == length - 1 )) || return 1
      printf '%s' "$output"
      return
    elif [[ "$char" == \\ ]]; then
      ((++index < length)) || return 1
      escaped="${value:index:1}"
      case "$escaped" in
        \\|'"'|'$') output+="$escaped" ;;
        t) output+=$'\t' ;;
        *) return 1 ;;
      esac
    elif [[ "$char" == '$' ]]; then
      return 1
    else
      output+="$char"
    fi
  done
  return 1
}

printf '%s\n' "$*" >> "$COMMAND_LOG"
if [[ "$*" == *"scripts/bootstrap_system.py"* ]]; then
  cat > "$BOOTSTRAP_STDIN"
fi
if [[ "${FAIL_CONFIG:-0}" == 1 && "$*" == *" config -q" ]]; then
  printf '%s\n' "${COMPOSE_ERROR_SECRET:-compose config failed}" >&2
  exit 1
fi
if [[ "$*" == *"config --environment"* ]]; then
  if [[ "${FAIL_CONFIG_ENVIRONMENT:-0}" == 1 ]]; then
    printf '%s\n' "${COMPOSE_ERROR_SECRET:-compose environment failed}" >&2
    exit 1
  fi
  env_file=""
  while (($#)); do
    if [[ "$1" == --env-file ]]; then
      env_file="$2"
      break
    fi
    shift
  done
  [[ -n "$env_file" ]] || exit 1
  while IFS= read -r line; do
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    decoded="$(decode_compose_value "$value")" || exit 1
    printf '%s=%s\n' "$key" "$decoded"
  done < "$env_file"
fi
exit 0
""",
    )


def environment(bin_dir: Path, tmp_path: Path, **extra: str) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": f"{bin_dir}:{SYSTEM_PATH}",
        "COMMAND_LOG": str(tmp_path / "commands.log"),
        "BOOTSTRAP_STDIN": str(tmp_path / "bootstrap.json"),
        **extra,
    }


def fake_doctor_docker(bin_dir: Path) -> None:
    executable(
        bin_dir / "docker",
        "#!/usr/bin/env bash\n"
        "case \"$*\" in\n"
        "  'compose config --services') printf '%s\\n' postgres api bot frontend ;;\n"
        "  'compose ps --services --status running') printf '%s\\n' \"$RUNNING_SERVICES\" ;;\n"
        "esac\n"
        "exit 0\n",
    )


def fake_compose_env(path: Path) -> dict[str, str]:
    parsed = {}
    for line in path.read_text().splitlines():
        key, value = line.split("=", 1)
        assert value.startswith('"'), "missing opening double quote"
        decoded = []
        index = 1
        while True:
            assert index < len(value), "unterminated double-quoted value"
            if value[index] == '"':
                assert index == len(value) - 1, "garbage after closing quote"
                break
            if value[index] == "\\":
                assert index + 1 < len(value), "unterminated escape"
                escaped = value[index + 1]
                assert escaped in {"\\", '"', "$", "t"}, "unsupported escape"
                decoded.append("\t" if escaped == "t" else escaped)
                index += 2
            else:
                assert value[index] != "$", "unescaped dollar"
                decoded.append(value[index])
                index += 1
        parsed[key] = "".join(decoded)
    return parsed


@pytest.mark.parametrize(
    "value",
    [
        "plain",
        '"unterminated',
        '"value"garbage',
        '"unsupported\\q"',
        '"unescaped$value"',
        '"trailing\\"',
    ],
)
def test_fake_compose_env_rejects_invalid_double_quoted_values(
    tmp_path: Path,
    value: str,
) -> None:
    path = tmp_path / ".env"
    path.write_text(f"KEY={value}\n")

    with pytest.raises(AssertionError):
        fake_compose_env(path)


def deployment_answers() -> list[str]:
    return [
        "https://shop.example",
        "https://api.shop.example",
        "8001",
        "8082",
        "telegram-token-secret",
        "123456789",
        "shopdb",
        "shopuser",
        "database-password-secret",
        "payos-client-secret",
        "payos-api-secret",
        "payos-checksum-secret",
    ]


def bootstrap_answers() -> list[str]:
    return [
        "Example Shop",
        "https://t.me/example_shop_bot",
        'Support "desk"\\night\tshift',
        "",
        "UTC",
        "SHOP",
        "https://shop.example/api/docs",
        "owner",
        "System Owner",
        "owner@example.test",
        "admin-password-123",
        "admin-password-123",
    ]


def run_setup(
    root: Path,
    env: dict[str, str],
    answers: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", "setup.sh"],
        cwd=root,
        env=env,
        input="\n".join(answers) + "\n",
        text=True,
        capture_output=True,
    )


def test_setup_requires_git(tmp_path: Path) -> None:
    core_dir = tmp_path / "core"
    core_dir.mkdir()
    (core_dir / "dirname").symlink_to("/usr/bin/dirname")
    root = tmp_path / "project"
    root.mkdir()
    shutil.copy(ROOT / "setup.sh", root / "setup.sh")

    result = subprocess.run(
        ["/bin/bash", "setup.sh"],
        cwd=root,
        env={**os.environ, "PATH": str(core_dir)},
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "Git is required" in result.stderr


def test_setup_requires_docker(tmp_path: Path) -> None:
    root, bin_dir = project(tmp_path)
    executable(bin_dir / "git", "#!/usr/bin/env bash\nexit 0\n")
    (bin_dir / "dirname").symlink_to("/usr/bin/dirname")
    isolated_env = {**os.environ, "PATH": str(bin_dir)}

    assert shutil.which("docker", path=isolated_env["PATH"]) is None

    result = subprocess.run(
        ["/bin/bash", "setup.sh"],
        cwd=root,
        env=isolated_env,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "Docker is required" in result.stderr


@pytest.mark.parametrize(
    ("docker_body", "message"),
    [
        ("[[ \"$*\" != 'compose version' ]]", "Docker Compose plugin is required"),
        ("[[ \"$*\" != info ]]", "Docker daemon is not reachable"),
    ],
)
def test_setup_checks_docker_runtime(
    tmp_path: Path,
    docker_body: str,
    message: str,
) -> None:
    root, bin_dir = project(tmp_path)
    executable(bin_dir / "git", "#!/usr/bin/env bash\nexit 0\n")
    executable(
        bin_dir / "docker",
        f"#!/usr/bin/env bash\n{docker_body}\n",
    )

    result = run_setup(root, environment(bin_dir, tmp_path), [])

    assert result.returncode != 0
    assert message in result.stderr


def test_setup_refuses_to_overwrite_existing_env(tmp_path: Path) -> None:
    root, bin_dir = project(tmp_path)
    marker = root / "env-was-sourced"
    existing = (
        "FRONTEND_URL=https://existing.example\n"
        "VITE_API_BASE_URL=https://api.existing.example\n"
        "DB_NAME=existing\n"
        f"DB_PASSWORD=$(touch {marker})\n"
    )
    (root / ".env").write_text(existing)
    fake_tools(bin_dir)

    result = run_setup(root, environment(bin_dir, tmp_path), bootstrap_answers())

    assert result.returncode == 0
    assert (root / ".env").read_text() == existing
    assert not marker.exists()
    assert "Using existing .env" in result.stdout


def test_setup_hides_existing_env_compose_validation_errors(tmp_path: Path) -> None:
    root, bin_dir = project(tmp_path)
    secret = "existing-malformed-password-secret"
    (root / ".env").write_text(
        "FRONTEND_URL=https://existing.example\n"
        "VITE_API_BASE_URL=https://api.existing.example\n"
        f'DB_PASSWORD="unterminated-{secret}\n'
    )
    fake_tools(bin_dir)
    env = environment(
        bin_dir,
        tmp_path,
        FAIL_CONFIG="1",
        COMPOSE_ERROR_SECRET=secret,
    )

    result = run_setup(root, env, [])

    assert result.returncode != 0
    assert "Existing .env is not valid for Docker Compose" in result.stderr
    assert secret not in result.stdout + result.stderr


def test_setup_hides_compose_environment_errors(tmp_path: Path) -> None:
    root, bin_dir = project(tmp_path)
    secret = "resolved-environment-password-secret"
    (root / ".env").write_text(
        'FRONTEND_URL="https://existing.example"\n'
        'VITE_API_BASE_URL="https://api.existing.example"\n'
        f'DB_PASSWORD="{secret}"\n'
    )
    fake_tools(bin_dir)
    env = environment(
        bin_dir,
        tmp_path,
        FAIL_CONFIG_ENVIRONMENT="1",
        COMPOSE_ERROR_SECRET=secret,
    )

    result = run_setup(root, env, [])

    assert result.returncode != 0
    assert "Could not read the resolved Compose environment" in result.stderr
    assert secret not in result.stdout + result.stderr


def test_setup_validates_operator_input(tmp_path: Path) -> None:
    root, bin_dir = project(tmp_path)
    fake_tools(bin_dir)
    answers = [
        "ftp://shop.example",
        *deployment_answers()[:1],
        "shop.example/api",
        *deployment_answers()[1:2],
        "0",
        *deployment_answers()[2:3],
        "port",
        *deployment_answers()[3:5],
        "0",
        *deployment_answers()[5:],
        "",
        *bootstrap_answers()[:1],
        "https://example.test/not-telegram",
        *bootstrap_answers()[1:5],
        "TUORDER",
        "lower",
        *bootstrap_answers()[5:10],
        "short",
        "admin-password-123",
        "different-password",
        "admin-password-123",
        "admin-password-123",
    ]

    result = run_setup(root, environment(bin_dir, tmp_path), answers)

    assert result.returncode == 0, result.stderr
    parsed_env = fake_compose_env(root / ".env")
    assert parsed_env["FRONTEND_URL"] == "https://shop.example"
    assert parsed_env["VITE_API_BASE_URL"] == "https://api.shop.example"
    assert parsed_env["DASHBOARD_PORT"] == "8001"
    assert parsed_env["FRONTEND_PORT"] == "8082"
    assert parsed_env["BOT_OWNER_TELEGRAM_ID"] == "123456789"
    errors = result.stderr
    assert "absolute HTTP(S) URL" in errors
    assert "positive integer" in errors
    assert "https://t.me/" in errors
    assert "cannot start with TU" in errors
    assert "2-8 uppercase letters or digits" in errors
    assert "at least 12 characters" in errors
    assert "Passwords do not match" in errors


def test_setup_rejects_malformed_url_authorities_and_ports(tmp_path: Path) -> None:
    root, bin_dir = project(tmp_path)
    fake_tools(bin_dir)
    invalid_urls = [
        "http://:",
        "https://?x",
        "http:///path",
        "http://#fragment",
        "https://example.test:port",
        "https://example.test:0",
        "https://example.test:65536",
        "https://.",
        "https://example..test",
        "https://-example.test",
        "https://example-.test",
        "https://[1:]",
        "https://[1::2::3]",
        "https://[1:2:3:4:5:6:7:8:9]",
    ]
    frontend_url = "https://shop.example:65535/store?x=1#top"
    answers = [
        *invalid_urls,
        frontend_url,
        *deployment_answers()[1:],
        *bootstrap_answers(),
    ]

    result = run_setup(root, environment(bin_dir, tmp_path), answers)

    assert result.returncode == 0, result.stderr
    assert result.stderr.count("absolute HTTP(S) URL") == len(invalid_urls)
    assert f"Frontend: {frontend_url}" in result.stdout


def test_setup_rejects_unsupported_json_control_characters(tmp_path: Path) -> None:
    root, bin_dir = project(tmp_path)
    fake_tools(bin_dir)
    (root / ".env").write_text(
        "FRONTEND_URL=https://shop.example\n"
        "VITE_API_BASE_URL=https://api.shop.example\n"
    )
    answers = ["Bad\bName", "Bad\fName", *bootstrap_answers()]

    result = run_setup(root, environment(bin_dir, tmp_path), answers)

    assert result.returncode == 0, result.stderr
    assert result.stderr.count("unsupported control characters") == 2
    bootstrap = json.loads((tmp_path / "bootstrap.json").read_text())
    assert bootstrap["settings"]["system_name"] == "Example Shop"


def test_setup_round_trips_compose_literals_without_logging_secrets(
    tmp_path: Path,
) -> None:
    root, bin_dir = project(tmp_path)
    fake_tools(bin_dir)
    answers = deployment_answers()
    answers[4] = "telegram $VALUE # spaced 'single' trailing\\"
    answers[6] = "shop database #1"
    answers[7] = r"shop$user\\double"
    answers[8] = "db $VALUE # adjacent\\\"quote 'single' spaced"
    answers[9] = "payos\tclient"
    env = environment(bin_dir, tmp_path)

    result = run_setup(root, env, answers + bootstrap_answers())

    assert result.returncode == 0, result.stderr
    parsed = fake_compose_env(root / ".env")
    expected = {
        "FRONTEND_URL": answers[0],
        "VITE_API_BASE_URL": answers[1],
        "CORS_ORIGINS": answers[0],
        "DASHBOARD_PORT": answers[2],
        "FRONTEND_PORT": answers[3],
        "TELEGRAM_BOT_TOKEN": answers[4],
        "BOT_OWNER_TELEGRAM_ID": answers[5],
        "DB_NAME": answers[6],
        "DB_USER": answers[7],
        "DB_PASSWORD": answers[8],
        "PAYOS_CLIENT_ID": answers[9],
        "PAYOS_API_KEY": answers[10],
        "PAYOS_CHECKSUM_KEY": answers[11],
    }
    assert {key: parsed[key] for key in expected} == expected
    assert len(parsed["DASHBOARD_SECRET_KEY"]) == 64
    assert set(parsed["DASHBOARD_SECRET_KEY"]) <= set("0123456789abcdef")
    assert set(parsed) == {*expected, "DASHBOARD_SECRET_KEY"}
    rendered = (root / ".env").read_text()
    rerun = run_setup(root, env, bootstrap_answers())
    assert rerun.returncode == 0, rerun.stderr
    assert (root / ".env").read_text() == rendered
    assert f"Frontend: {answers[0]}" in rerun.stdout
    assert f"API docs: {answers[1]}/docs" in rerun.stdout
    output_and_log = (
        result.stdout
        + result.stderr
        + rerun.stdout
        + rerun.stderr
        + Path(env["COMMAND_LOG"]).read_text()
    )
    secrets = answers[4:5] + answers[7:12] + [bootstrap_answers()[-1]]
    assert all(secret not in output_and_log for secret in secrets)
    assert "config --environment" in Path(env["COMMAND_LOG"]).read_text()


def test_setup_creates_atomic_private_env_and_bootstraps_over_stdin(
    tmp_path: Path,
) -> None:
    root, bin_dir = project(tmp_path)
    fake_tools(bin_dir)
    env = environment(bin_dir, tmp_path)
    secrets = deployment_answers()[4:5] + deployment_answers()[8:] + [
        bootstrap_answers()[-1]
    ]

    result = run_setup(root, env, deployment_answers() + bootstrap_answers())

    assert result.returncode == 0, result.stderr
    env_path = root / ".env"
    assert oct(env_path.stat().st_mode & 0o777) == "0o600"
    env_text = env_path.read_text()
    assert "PAY2S" not in env_text
    assert all(secret in env_text for secret in secrets[:-1])
    output = result.stdout + result.stderr
    command_log = Path(env["COMMAND_LOG"]).read_text()
    assert all(secret not in output + command_log for secret in secrets)
    bootstrap = json.loads(Path(env["BOOTSTRAP_STDIN"]).read_text())
    assert bootstrap["admin"]["password"] == "admin-password-123"
    assert bootstrap["settings"]["order_prefix"] == "SHOP"
    assert bootstrap["settings"]["support_line_1"] == 'Support "desk"\\night\tshift'
    assert "scripts/bootstrap_system.py" in command_log
    assert "up -d postgres api" in command_log
    assert "up -d --build bot frontend" in command_log
    assert "https://api.shop.example/api/payos/webhook" in result.stdout
    assert "PayOS merchant dashboard" in result.stdout


def test_setup_does_not_publish_invalid_temporary_env(tmp_path: Path) -> None:
    root, bin_dir = project(tmp_path)
    fake_tools(bin_dir)
    secret = deployment_answers()[8]
    env = environment(
        bin_dir,
        tmp_path,
        FAIL_CONFIG="1",
        COMPOSE_ERROR_SECRET=secret,
    )

    result = run_setup(root, env, deployment_answers())

    assert result.returncode != 0
    assert "Generated environment is not valid for Docker Compose" in result.stderr
    assert secret not in result.stdout + result.stderr
    assert not (root / ".env").exists()
    assert not list(root.glob(".env.tmp.*"))


def test_manage_help_lists_supported_commands(tmp_path: Path) -> None:
    root, _ = operator_project(tmp_path)

    result = subprocess.run(
        ["/bin/bash", "manage.sh", "help"],
        cwd=root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    for command in (
        "start",
        "stop",
        "restart",
        "status",
        "logs",
        "doctor",
        "backup",
        "restore",
        "update",
    ):
        assert command in result.stdout


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["start"], "docker compose up -d"),
        (["stop"], "docker compose stop"),
        (["restart"], "docker compose up -d --build --force-recreate"),
        (["status"], "docker compose ps"),
        (["logs", "api"], "docker compose logs --tail=200 -f api"),
    ],
)
def test_manage_dispatches_lifecycle_commands(
    tmp_path: Path,
    arguments: list[str],
    expected: str,
) -> None:
    root, bin_dir = operator_project(tmp_path)
    (root / ".env").write_text("DB_NAME=test\n")
    executable(
        bin_dir / "docker",
        "#!/usr/bin/env bash\n"
        "printf 'docker %s\\n' \"$*\" >> \"$COMMAND_LOG\"\n",
    )

    result = subprocess.run(
        ["/bin/bash", "manage.sh", *arguments],
        cwd=root,
        env=environment(bin_dir, tmp_path),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert expected in Path(environment(bin_dir, tmp_path)["COMMAND_LOG"]).read_text()


def test_manage_logs_rejects_unknown_service(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    (root / ".env").write_text("DB_NAME=test\n")
    executable(bin_dir / "docker", "#!/usr/bin/env bash\nexit 0\n")

    result = subprocess.run(
        ["/bin/bash", "manage.sh", "logs", "database"],
        cwd=root,
        env=environment(bin_dir, tmp_path),
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "unknown service" in result.stderr


def test_update_refuses_dirty_tracked_worktree(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    (root / ".env").write_text("DB_NAME=test\n")
    executable(bin_dir / "docker", "#!/usr/bin/env bash\nexit 0\n")
    executable(
        bin_dir / "git",
        "#!/usr/bin/env bash\n"
        '[[ "$1 $2" == "diff --quiet" ]] && exit 1\n'
        "exit 0\n",
    )

    result = subprocess.run(
        ["/bin/bash", "manage.sh", "update"],
        cwd=root,
        env=environment(bin_dir, tmp_path),
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "tracked changes" in result.stderr


def test_update_backs_up_before_pull_and_rebuild(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    (root / ".env").write_text("DB_NAME=test\n")
    executable(
        bin_dir / "docker",
        "#!/usr/bin/env bash\n"
        "printf 'docker %s\\n' \"$*\" >> \"$COMMAND_LOG\"\n"
        '[[ "$*" == *"pg_dump"* ]] && printf \'%s\\n\' \'SQL dump\'\n'
        "exit 0\n",
    )
    executable(
        bin_dir / "git",
        "#!/usr/bin/env bash\n"
        "printf 'git %s\\n' \"$*\" >> \"$COMMAND_LOG\"\n"
        '[[ "$*" == "rev-parse HEAD" ]] && printf \'%s\\n\' \'previous-sha\'\n'
        "exit 0\n",
    )
    env = environment(bin_dir, tmp_path)

    result = subprocess.run(
        ["/bin/bash", "manage.sh", "update"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    commands = Path(env["COMMAND_LOG"]).read_text().splitlines()
    backup = next(index for index, line in enumerate(commands) if "pg_dump" in line)
    pull = commands.index("git pull --ff-only")
    rebuild = commands.index("docker compose up -d --build")
    assert backup < pull < rebuild
    assert "Previous commit: previous-sha" in result.stdout
    assert "Backup: backups/pre_update_" in result.stdout


def test_update_readiness_failure_prints_recovery_evidence(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    (root / ".env").write_text("DB_NAME=test\n")
    executable(
        bin_dir / "docker",
        "#!/usr/bin/env bash\n"
        '[[ "$*" == *"pg_dump"* ]] && { printf \'%s\\n\' \'SQL dump\'; exit 0; }\n'
        '[[ "$*" == *"exec -T api python -c"* ]] && exit 1\n'
        "exit 0\n",
    )
    executable(
        bin_dir / "git",
        "#!/usr/bin/env bash\n"
        '[[ "$*" == "rev-parse HEAD" ]] && printf \'%s\\n\' \'previous-sha\'\n'
        "exit 0\n",
    )
    executable(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    result = subprocess.run(
        ["/bin/bash", "manage.sh", "update"],
        cwd=root,
        env=environment(bin_dir, tmp_path),
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "Previous commit: previous-sha" in result.stderr
    assert "Backup: backups/pre_update_" in result.stderr


def test_backup_uses_container_database_environment_atomically(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    backups = root / "backups"
    backups.mkdir()
    predictable = backups / "safe_name.sql.tmp"
    predictable.write_text("do not touch\n")
    executable(
        bin_dir / "docker",
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$COMMAND_LOG\"\n"
        "printf '%s\\n' 'SQL dump'\n",
    )
    env = environment(bin_dir, tmp_path, DB_USER="host-user", DB_NAME="host-db")

    result = subprocess.run(
        ["/bin/bash", "scripts/backup_database.sh", "safe_name"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "backups/safe_name.sql"
    target = backups / "safe_name.sql"
    assert target.read_text() == "SQL dump\n"
    assert target.stat().st_mode & 0o777 == 0o600
    assert predictable.read_text() == "do not touch\n"
    assert not list(backups.glob(".safe_name.sql.tmp.*"))
    command = Path(env["COMMAND_LOG"]).read_text()
    assert 'pg_dump -U "$POSTGRES_USER"' in command
    assert '"$POSTGRES_DB"' in command
    assert "host-user" not in command
    assert "host-db" not in command


def test_backup_removes_partial_dump_on_failure(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    backups = root / "backups"
    backups.mkdir()
    predictable = backups / "failed.sql.tmp"
    predictable.write_text("do not touch\n")
    executable(
        bin_dir / "docker",
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' 'partial dump'\n"
        "exit 1\n",
    )

    result = subprocess.run(
        ["/bin/bash", "scripts/backup_database.sh", "failed"],
        cwd=root,
        env=environment(bin_dir, tmp_path),
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert not (backups / "failed.sql").exists()
    assert predictable.read_text() == "do not touch\n"
    assert not list(backups.glob(".failed.sql.tmp.*"))


def test_backup_rejects_unsafe_name_without_running_docker(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    marker = tmp_path / "docker-ran"
    executable(
        bin_dir / "docker",
        f"#!/usr/bin/env bash\ntouch {marker}\n",
    )

    result = subprocess.run(
        ["/bin/bash", "scripts/backup_database.sh", "../escape"],
        cwd=root,
        env=environment(bin_dir, tmp_path),
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "Invalid backup name" in result.stderr
    assert not marker.exists()


def test_restore_uses_container_database_environment(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    backup = root / "backup.sql"
    backup.write_text("SELECT 1;\n")
    executable(
        bin_dir / "docker",
        "#!/usr/bin/env bash\n"
        "printf 'docker %s\\n' \"$*\" >> \"$COMMAND_LOG\"\n"
        '[[ "$*" == *"psql -v ON_ERROR_STOP=1"* ]] && cat > "$RESTORE_STDIN"\n'
        "exit 0\n",
    )
    restored_sql = tmp_path / "restored.sql"
    env = environment(
        bin_dir,
        tmp_path,
        DB_USER="host-user",
        DB_NAME="host-db",
        RESTORE_STDIN=str(restored_sql),
    )

    result = subprocess.run(
        ["/bin/bash", "scripts/restore_database.sh", str(backup)],
        cwd=root,
        env=env,
        input="RESTORE\n",
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    commands = Path(env["COMMAND_LOG"]).read_text()
    assert "docker compose stop bot api" in commands
    assert "docker compose up -d postgres" in commands
    assert 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' in commands
    assert 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' in commands
    assert "docker compose up -d api bot frontend" in commands
    assert "DROP DATABASE" not in commands
    assert "CREATE DATABASE" not in commands
    assert "host-user" not in commands
    assert "host-db" not in commands
    assert restored_sql.read_text() == "SELECT 1;\n"


def test_restore_requires_exact_confirmation(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    backup = root / "backup.sql"
    backup.write_text("SELECT 1;\n")
    marker = tmp_path / "docker-ran"
    executable(
        bin_dir / "docker",
        f"#!/usr/bin/env bash\ntouch {marker}\n",
    )

    result = subprocess.run(
        ["/bin/bash", "scripts/restore_database.sh", str(backup)],
        cwd=root,
        env=environment(bin_dir, tmp_path),
        input="yes\n",
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Restore cancelled" in result.stdout
    assert not marker.exists()


def test_restore_rejects_directory_without_running_docker(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    backup_directory = root / "backup.sql"
    backup_directory.mkdir()
    marker = tmp_path / "docker-ran"
    executable(bin_dir / "docker", f"#!/usr/bin/env bash\ntouch {marker}\n")

    result = subprocess.run(
        ["/bin/bash", "scripts/restore_database.sh", str(backup_directory)],
        cwd=root,
        env=environment(bin_dir, tmp_path),
        input="RESTORE\n",
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "non-empty backup file" in result.stderr
    assert not marker.exists()


def test_restore_psql_failure_keeps_applications_stopped(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    backup = root / "backup.sql"
    backup.write_text("SELECT broken;\n")
    executable(
        bin_dir / "docker",
        "#!/usr/bin/env bash\n"
        "printf 'docker %s\\n' \"$*\" >> \"$COMMAND_LOG\"\n"
        '[[ "$*" == *"psql -v ON_ERROR_STOP=1"* ]] && { cat > "$RESTORE_STDIN"; exit 1; }\n'
        "exit 0\n",
    )
    restored_sql = tmp_path / "restored.sql"
    env = environment(bin_dir, tmp_path, RESTORE_STDIN=str(restored_sql))

    result = subprocess.run(
        ["/bin/bash", "scripts/restore_database.sh", str(backup)],
        cwd=root,
        env=env,
        input="RESTORE\n",
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    commands = Path(env["COMMAND_LOG"]).read_text()
    assert "docker compose stop bot api" in commands
    assert "docker compose up -d api bot frontend" not in commands
    assert restored_sql.read_text() == "SELECT broken;\n"


def test_doctor_reports_each_fake_check(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    env_file = root / ".env"
    env_file.write_text("DB_NAME=test\n")
    env_file.chmod(0o600)
    fake_doctor_docker(bin_dir)
    executable(
        bin_dir / "df",
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' 'Filesystem 1024-blocks Used Available Capacity Mounted on'\n"
        "printf '%s\\n' '/dev/fake 2000000 1 1999999 1% /'\n",
    )

    result = subprocess.run(
        ["/bin/bash", "manage.sh", "doctor"],
        cwd=root,
        env=environment(
            bin_dir,
            tmp_path,
            RUNNING_SERVICES="postgres\napi\nbot\nfrontend",
        ),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [f"[ok] {label}" for label in DOCTOR_LABELS]


def test_doctor_aggregates_failed_df_and_runs_later_checks(tmp_path: Path) -> None:
    root, bin_dir = operator_project(tmp_path)
    env_file = root / ".env"
    env_file.write_text("DB_NAME=test\n")
    env_file.chmod(0o600)
    fake_doctor_docker(bin_dir)
    executable(bin_dir / "df", "#!/usr/bin/env bash\nexit 1\n")

    result = subprocess.run(
        ["/bin/bash", "manage.sh", "doctor"],
        cwd=root,
        env=environment(
            bin_dir,
            tmp_path,
            RUNNING_SERVICES="postgres\napi\nbot\nfrontend",
        ),
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    expected = [f"[ok] {label}" for label in DOCTOR_LABELS]
    expected[6] = f"[fail] {DOCTOR_LABELS[6]}"
    assert result.stdout.splitlines() == expected


@pytest.mark.parametrize(
    "running_services",
    [
        "postgres\napi\nfrontend",
        "postgres\napi\nbot",
    ],
)
def test_doctor_fails_when_configured_service_is_not_running(
    tmp_path: Path,
    running_services: str,
) -> None:
    root, bin_dir = operator_project(tmp_path)
    env_file = root / ".env"
    env_file.write_text("DB_NAME=test\n")
    env_file.chmod(0o600)
    fake_doctor_docker(bin_dir)
    executable(
        bin_dir / "df",
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' 'Filesystem 1024-blocks Used Available Capacity Mounted on'\n"
        "printf '%s\\n' '/dev/fake 2000000 1 1999999 1% /'\n",
    )

    result = subprocess.run(
        ["/bin/bash", "manage.sh", "doctor"],
        cwd=root,
        env=environment(
            bin_dir,
            tmp_path,
            RUNNING_SERVICES=running_services,
        ),
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    expected = [f"[ok] {label}" for label in DOCTOR_LABELS]
    expected[7] = f"[fail] {DOCTOR_LABELS[7]}"
    assert result.stdout.splitlines() == expected
