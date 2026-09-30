import hashlib
import io

import pytest

from d0key import FOURCC, D0Key, dump, dumps, load, loads


def test_fixture_matches_checksum(d0pk_path):
    expected = d0pk_path.with_name(d0pk_path.name + ".sha256").read_text().split()[0]
    assert hashlib.sha256(d0pk_path.read_bytes()).hexdigest() == expected


def test_read_real_file(d0pk_path):
    with open(d0pk_path, "rb") as f:
        key = load(f)

    assert key.magic is FOURCC.D0PK
    assert key.nlumps == 2
    assert all(size > 0 for size in key.lumpsizes)


def test_real_file_roundtrip_bytes(d0pk_bytes):
    assert dumps(loads(d0pk_bytes)) == d0pk_bytes


def test_write_read_file(d0pk_path, d0pk_bytes, tmp_path):
    key = loads(d0pk_bytes)
    out = tmp_path / "out.d0pk"
    with open(out, "wb") as f:
        dump(key, f)

    assert out.read_bytes() == d0pk_bytes

    with open(out, "rb") as f:
        assert load(f) == key


def test_load_bytesio(d0pk_bytes):
    assert load(io.BytesIO(d0pk_bytes)) == loads(d0pk_bytes)


def test_load_text_mode_raises_typeerror(d0pk_path):
    with open(d0pk_path, "r", errors="ignore") as f:
        with pytest.raises(TypeError):
            load(f)
