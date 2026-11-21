"""Les apps Streamlit (y compris celles venues des dépôts fusionnés) compilent."""

import py_compile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APPS = sorted(p for p in (ROOT / "apps").rglob("*.py") if "node_modules" not in p.parts)


@pytest.mark.parametrize("path", APPS, ids=lambda p: str(p.relative_to(ROOT)))
def test_app_compiles(path):
    py_compile.compile(str(path), doraise=True)
