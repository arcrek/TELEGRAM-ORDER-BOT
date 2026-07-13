import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PATH = "/usr/bin:/bin"


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


def fake_tools(bin_dir: Path) -> None:
    executable(bin_dir / "git", "#!/usr/bin/env bash\nexit 0\n")
    executable(
        bin_dir / "docker",
        """#!/usr/bin/env bash
printf '%s\n' "$*" >> "$COMMAND_LOG"
if [[ "$*" == *"scripts/bootstrap_system.py"* ]]; then
  cat > "$BOOTSTRAP_STDIN"
fi
if [[ "${FAIL_CONFIG:-0}" == 1 && "$*" == *" config -q" ]]; then
  exit 1
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
        ["/usr/bin/bash", "setup.sh"],
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
        ["/usr/bin/bash", "setup.sh"],
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

    result = run_setup(root, environment(bin_dir, tmp_path), [])

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
    env_text = (root / ".env").read_text()
    assert "FRONTEND_URL=https://shop.example\n" in env_text
    assert "VITE_API_BASE_URL=https://api.shop.example\n" in env_text
    assert "DASHBOARD_PORT=8001\n" in env_text
    assert "FRONTEND_PORT=8082\n" in env_text
    assert "BOT_OWNER_TELEGRAM_ID=123456789\n" in env_text
    errors = result.stderr
    assert "absolute HTTP(S) URL" in errors
    assert "positive integer" in errors
    assert "https://t.me/" in errors
    assert "cannot start with TU" in errors
    assert "2-8 uppercase letters or digits" in errors
    assert "at least 12 characters" in errors
    assert "Passwords do not match" in errors


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
    env = environment(bin_dir, tmp_path, FAIL_CONFIG="1")

    result = run_setup(root, env, deployment_answers())

    assert result.returncode != 0
    assert not (root / ".env").exists()
    assert not list(root.glob(".env.tmp.*"))
