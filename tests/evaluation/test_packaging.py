"""Packaging metadata guards (A6a)."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_readme_reference_exists() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    readme = project["readme"]
    assert isinstance(readme, str)
    assert (ROOT / readme).is_file(), f"pyproject readme {readme!r} is missing"


def test_readme_is_non_trivial() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert len(text) > 200
    assert "TraceFix" in text
