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


def fake_compose_env(path: Path) -> dict[str, str]:
    parsed = {}
    for line in path.read_text().splitlines():
        key, value = line.split("=", 1)
        assert value.startswith("'"), "missing opening single quote"
        decoded = []
        index = 1
        while True:
            assert index < len(value), "unterminated single-quoted value"
            if value[index] == "'":
                assert index == len(value) - 1, "garbage after closing quote"
                break
            if value[index] == "\\":
                assert index + 1 < len(value), "unterminated escape"
                assert value[index + 1] in {"\\", "'"}, "unsupported escape"
                decoded.append(value[index + 1])
                index += 2
            else:
                decoded.append(value[index])
                index += 1
        parsed[key] = "".join(decoded)
    return parsed


@pytest.mark.parametrize(
    "value",
    [
        "plain",
        "'unterminated",
        "'value'garbage",
        "'unsupported\\q'",
        "'trailing\\'",
    ],
)
def test_fake_compose_env_rejects_invalid_single_quoted_values(
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
    answers[4] = "telegram $VALUE # spaced \"double\" trailing\\"
    answers[6] = "shop database #1"
    answers[7] = r"shop$user\\double"
    answers[8] = "db $VALUE # adjacent\\'quote \"double\""
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
