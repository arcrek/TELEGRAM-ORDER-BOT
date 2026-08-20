import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "check_public_tree.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
FORBIDDEN_ARTIFACTS = (
    (".env", ".env*"),
    (".env.local", ".env*"),
    (".env.production", ".env*"),
    (".env.example.local", ".env*"),
    ("database.db", "*.db"),
    ("database.sqlite", "*.sqlite"),
    ("backup.sql", "*.sql"),
    ("backup.dump", "*.dump"),
    ("certificate.pem", "*.pem"),
    ("private.key", "*.key"),
    ("backups/archive.txt", "backups/*"),
    ("data/inventory.txt", "data/*"),
    (".claude/settings.json", ".claude/*"),
)


def public_project(tmp_path: Path, docker_exit: int = 0) -> tuple[Path, dict[str, str]]:
    assert GUARD.is_file(), "public-tree guard is missing"
    root = tmp_path / "public"
    scripts = root / "scripts"
    bin_dir = tmp_path / "bin"
    scripts.mkdir(parents=True)
    bin_dir.mkdir()
    shutil.copy2(GUARD, scripts / GUARD.name)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)

    docker = bin_dir / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\" > \"$DOCKER_LOG\"\n"
        "exit \"${DOCKER_EXIT:-0}\"\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    return root, {
        **os.environ,
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "DOCKER_LOG": str(tmp_path / "docker.log"),
        "DOCKER_EXIT": str(docker_exit),
    }


def run_guard(root: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", "scripts/check_public_tree.sh"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )


@pytest.mark.parametrize(("relative_path", "pattern"), FORBIDDEN_ARTIFACTS)
def test_guard_rejects_each_tracked_private_artifact(
    tmp_path: Path,
    relative_path: str,
    pattern: str,
) -> None:
    root, env = public_project(tmp_path)
    artifact = root / relative_path
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("private\n")
    subprocess.run(["git", "add", "-f", "--", relative_path], cwd=root, check=True)

    result = run_guard(root, env)

    assert result.returncode != 0
    assert f"Tracked private artifact matches: {pattern}" in result.stderr
    assert not Path(env["DOCKER_LOG"]).exists()


def test_guard_allows_tracked_env_example(tmp_path: Path) -> None:
    root, env = public_project(tmp_path)
    (root / ".env.example").write_text("SAFE_PLACEHOLDER=\n")
    subprocess.run(["git", "add", "--", ".env.example"], cwd=root, check=True)

    result = run_guard(root, env)

    assert result.returncode == 0, result.stderr
    assert Path(env["DOCKER_LOG"]).exists()


def test_guard_runs_exact_pinned_redacted_gitleaks_scan(tmp_path: Path) -> None:
    root, env = public_project(tmp_path)

    result = run_guard(root, env)

    assert result.returncode == 0, result.stderr
    assert Path(env["DOCKER_LOG"]).read_text().splitlines() == [
        "run",
        "--rm",
        "-v",
        f"{root}:/repo",
        "zricethezav/gitleaks:v8.30.1",
        "dir",
        "/repo",
        "--redact",
        "--no-banner",
    ]


def test_guard_propagates_gitleaks_failure(tmp_path: Path) -> None:
    root, env = public_project(tmp_path, docker_exit=42)

    result = run_guard(root, env)

    assert result.returncode == 42


def test_guard_propagates_git_failure_without_scanning(tmp_path: Path) -> None:
    root, env = public_project(tmp_path)
    git = Path(env["PATH"].split(":", 1)[0]) / "git"
    git.write_text("#!/usr/bin/env bash\nexit 5\n")
    git.chmod(git.stat().st_mode | stat.S_IXUSR)

    result = run_guard(root, env)

    assert result.returncode == 5
    assert not Path(env["DOCKER_LOG"]).exists()


def test_frontend_ci_audits_production_dependencies_before_tests() -> None:
    assert (
        "      - run: npm ci\n"
        "      - run: npm audit --omit=dev --audit-level=moderate\n"
        "      - run: npm test -- --run\n"
    ) in CI_WORKFLOW.read_text()
