import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _service_block(compose: str, service: str) -> str:
    match = re.search(
        rf"(?ms)^  {service}:\n(.*?)(?=^  [a-z][a-z0-9_-]*:\n|^volumes:\n|\Z)",
        compose,
    )
    assert match is not None
    return match.group(1)


def test_api_and_bot_share_declared_named_delivery_volume():
    compose = (ROOT / "docker-compose.yml").read_text()

    assert "\nvolumes:\n  delivery_data:\n" in compose
    assert compose.rstrip().endswith("volumes:\n  delivery_data:")
    assert "./data/delivery_data" not in compose
    for service in ("api", "bot"):
        assert "- delivery_data:/app/delivery_data" in _service_block(compose, service)


def test_runtime_images_own_delivery_mountpoint_before_switching_user():
    for dockerfile in ("Dockerfile.api", "Dockerfile.bot"):
        instructions = (ROOT / dockerfile).read_text().replace("\\\n", " ")
        root_instructions, separator, _ = instructions.partition("\nUSER appuser\n")

        assert separator, f"{dockerfile} must switch to appuser"
        mountpoint = root_instructions.find("/app/delivery_data")
        ownership = root_instructions.find("chown -R appuser:appuser /app")
        assert 0 <= mountpoint < ownership
