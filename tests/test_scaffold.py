"""T001: project scaffold tests.

Covers the acceptance criteria for the scaffold task: a uv-managed
``pyproject.toml`` (Python 3.11+, required runtime/dev deps, ruff+pytest
config), the ``src`` and ``tests`` packages, and a ``.gitignore`` that
ignores secrets and caches.
"""

import tomllib
from pathlib import Path

import src

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _load_pyproject() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def test_src_and_tests_are_packages():
    assert src is not None
    assert (ROOT / "src" / "__init__.py").is_file()
    assert (ROOT / "tests" / "__init__.py").is_file()


def test_pyproject_declares_python_and_dependencies():
    data = _load_pyproject()
    project = data["project"]

    assert "3.11" in project["requires-python"]

    runtime = {dep.split()[0].split(">=")[0].lower() for dep in project["dependencies"]}
    for expected in ("pandas", "streamlit", "openpyxl"):
        assert expected in runtime, f"{expected} missing from runtime deps"

    dev = data["dependency-groups"]["dev"]
    dev_names = {dep.split()[0].split(">=")[0].lower() for dep in dev}
    assert "pytest" in dev_names
    assert "ruff" in dev_names


def test_pyproject_has_ruff_and_pytest_config():
    data = _load_pyproject()
    assert "ini_options" in data["tool"]["pytest"]
    assert "ruff" in data["tool"]


def test_gitignore_ignores_secrets_and_caches():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    entries = {line.strip() for line in gitignore if line.strip() and not line.startswith("#")}
    for expected in (".env", ".venv/", "__pycache__/", "*.pyc"):
        assert expected in entries, f"{expected} missing from .gitignore"
