from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def d0pk_path() -> Path:
    return DATA_DIR / "xonotic_key_0.d0pk"


@pytest.fixture
def d0pk_bytes(d0pk_path) -> bytes:
    return d0pk_path.read_bytes()
