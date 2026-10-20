from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_no_secrets.py"
NVIDIA_LABEL = "NVIDIA API key (nvapi-...)"


def _labels(line: str) -> list[str]:
    spec = importlib.util.spec_from_file_location("check_no_secrets", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [label for pattern, label in module.PATTERNS if pattern.search(line)]


# Key-shaped strings are built at runtime so this file never contains a literal
# that the secret scanner itself would flag.
def _fake_nvidia_key(body: str) -> str:
    return "nvapi" + "-" + body


@pytest.mark.parametrize(
    "body",
    ["A1b2" * 10, "ab_-" * 10, "x" * 20],
)
def test_nvidia_key_shaped_values_are_detected(body):
    line = f"NVIDIA_API_KEY={_fake_nvidia_key(body)}"

    assert NVIDIA_LABEL in _labels(line)


@pytest.mark.parametrize(
    "line",
    [
        "NVIDIA_API_KEY=",
        "NVIDIA_API_KEY=" + "nvapi" + "-your-key-here",
        "NVIDIA_API_KEY=nvidia-fake-key-not-real",
        "NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1",
        "NVIDIA_EMBEDDING_MODEL=nvidia/llama-nemotron-embed-vl-1b-v2",
    ],
)
def test_placeholders_and_normal_config_are_not_flagged(line):
    assert NVIDIA_LABEL not in _labels(line)


def test_existing_groq_pattern_still_works():
    line = "GROQ_API_KEY=" + "gsk" + "_" + "a" * 24

    assert "Groq API key (gsk_...)" in _labels(line)