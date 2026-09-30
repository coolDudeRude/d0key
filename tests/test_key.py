import dataclasses

import pytest

from d0key import FOURCC, LUMPS, D0Key, D0UnsupportedTypeError

UNSUPPORTED = [m for m in FOURCC if m not in LUMPS]


# Valid Construction
def test_valid_d0si():
    key = D0Key(FOURCC.D0SI, (b"abc",))
    assert key.magic is FOURCC.D0SI
    assert key.lumps == (b"abc",)
    assert key.nlumps == 1
    assert key.extra == b""


def test_valid_d0pk():
    key = D0Key(FOURCC.D0PK, (b"abc", b"cde"), extra=b"tail")
    assert key.magic is FOURCC.D0PK
    assert key.lumps == (b"abc", b"cde")
    assert key.nlumps == 2
    assert key.extra == b"tail"


def test_empty_lumps_are_allowed():
    key = D0Key(FOURCC.D0PK, (b"", b""))
    assert key.lumpsizes == [0, 0]


# wrong lump count
@pytest.mark.parametrize("magic", list(LUMPS))
def test_too_few_lumps(magic):
    lumps = (b"x",) * (LUMPS[magic] - 1)
    with pytest.raises(ValueError, match="needs"):
        D0Key(magic, lumps)


@pytest.mark.parametrize("magic", list(LUMPS))
def test_too_many_lumps(magic):
    lumps = (b"x",) * (LUMPS[magic] + 1)
    with pytest.raises(ValueError, match="needs"):
        D0Key(magic, lumps)


# Unsupported magic
@pytest.mark.parametrize("magic", UNSUPPORTED)
def test_unsupported_magic(magic):
    with pytest.raises(D0UnsupportedTypeError):
        D0Key(magic, (b"x",))


# Wrong types, misuse of api, raise TypeError
@pytest.mark.parametrize("magic", [b"d0si", "d0si", None, 1])
def test_magic_must_be_fourcc(magic):
    with pytest.raises(TypeError, match="magic"):
        D0Key(magic, (b"x",))


@pytest.mark.parametrize("lumps", [[b"x"], b"x", None, {b"x"}])
def test_lumps_must_be_tuple(lumps):
    with pytest.raises(TypeError, match="tuple"):
        D0Key(FOURCC.D0SI, lumps)


@pytest.mark.parametrize("bad", ["text", bytearray(b"x"), None, 5])
def test_each_lump_must_be_bytes(bad):
    with pytest.raises(TypeError, match="lump 0"):
        D0Key(FOURCC.D0SI, (bad,))


def test_error_names_the_bad_lump_index():
    with pytest.raises(TypeError, match="lump 1"):
        D0Key(FOURCC.D0PK, (b"ok", 5))


@pytest.mark.parametrize("extra", ["", None, bytearray(b"x"), 0])
def test_extra_must_be_bytes(extra):
    with pytest.raises(TypeError, match="extra"):
        D0Key(FOURCC.D0SI, (b"x",), extra=extra)


# immutablility
def test_frozen():
    key = D0Key(FOURCC.D0SI, (b"x",))
    with pytest.raises(dataclasses.FrozenInstanceError):
        key.extra = b"changed"


# properties
def test_nlumps_and_lumpsizes():
    key = D0Key(FOURCC.D0PK, (b"ab", b"cde"))
    assert key.nlumps == 2
    assert key.lumpsizes == [2, 3]


# equality
def test_equality():
    a = D0Key(FOURCC.D0SI, (b"abc",))
    b = D0Key(FOURCC.D0SI, (b"abc",))
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1


@pytest.mark.parametrize(
    "other",
    [
        D0Key(FOURCC.D0SI, (b"xyz",)),  # different lump
        D0Key(FOURCC.D0SI, (b"abc",), extra=b"!"),  # different extra
        D0Key(FOURCC.D0PK, (b"abc", b"")),  # different magic
    ],
)
def test_inequality(other):
    assert D0Key(FOURCC.D0SI, (b"abc",)) != other
