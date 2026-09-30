import tomllib
from pathlib import Path

from packaging.version import Version

import d0key


def test_version_matches_pyproject():
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert Version(d0key.__version__) == Version(declared)
