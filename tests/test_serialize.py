from d0key import FOURCC, D0Key, dumps


def test_d0si_exact_bytes():
    key = D0Key(FOURCC.D0SI, (b"abc",))
    assert key.to_bytes() == b"d0si\x03\x00\x00\x00abc"


def test_d0pk_exact_bytes():
    key = D0Key(FOURCC.D0PK, (b"ab", b"cde"))
    assert key.to_bytes() == b"d0pk\x02\x00\x00\x00ab\x03\x00\x00\x00cde"


def test_extra_is_appended():
    key = D0Key(FOURCC.D0SI, (b"abc",), extra=b"tail")
    assert key.to_bytes() == b"d0si\x03\x00\x00\x00abctail"


def test_empty_lumps():
    key = D0Key(FOURCC.D0PK, (b"", b""))
    assert key.to_bytes() == b"d0pk\x00\x00\x00\x00\x00\x00\x00\x00"


def test_length_prefix_is_little_endian():
    key = D0Key(FOURCC.D0SI, (b"x" * 256,))
    assert key.to_bytes().startswith(b"d0si\x00\x01\x00\x00")


def test_returns_bytes():
    assert type(D0Key(FOURCC.D0SI, (b"x",)).to_bytes()) is bytes


def test_dumps_matches_to_bytes():
    key = D0Key(FOURCC.D0PK, (b"ab", b"cde"), extra=b"!")
    assert dumps(key) == key.to_bytes()
