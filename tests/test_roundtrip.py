import random

import pytest

from d0key import FOURCC, LUMPS, D0Key, D0KeyError, dumps, loads


def le(n: int) -> bytes:
    return n.to_bytes(4, "little")


RAW_SAMPLES = [
    b"d0si" + le(3) + b"abc",
    b"d0si" + le(0),
    b"d0si" + le(3) + b"abc" + b"trailing",
    b"d0pk" + le(2) + b"ab" + le(3) + b"cde",
    b"d0pk" + le(0) + le(0),
    b"d0pk" + le(1) + b"a" + le(1) + b"b" + b"\x00\xff" * 10,
]


@pytest.mark.parametrize("raw", RAW_SAMPLES)
def test_bytes_to_key_to_bytes(raw):
    assert dumps(loads(raw)) == raw


@pytest.mark.parametrize(
    "key",
    [
        D0Key(FOURCC.D0SI, (b"abc",)),
        D0Key(FOURCC.D0SI, (b"",), extra=b"tail"),
        D0Key(FOURCC.D0PK, (b"ab", b"cde")),
        D0Key(FOURCC.D0PK, (b"", b""), extra=b"\x00\x01"),
    ],
)
def test_key_to_bytes_to_key(key):
    assert loads(dumps(key)) == key


def test_method_style_roundtrip():
    raw = RAW_SAMPLES[3]
    assert D0Key.from_bytes(raw).to_bytes() == raw


def test_trailing_bytes_survive_roundtrip():
    raw = b"d0si" + le(1) + b"a" + b"unknown trailing data"
    assert loads(raw).extra == b"unknown trailing data"
    assert dumps(loads(raw)) == raw


# Randomized tests
def _random_key(rng: random.Random) -> D0Key:
    magic = rng.choice(list(LUMPS))
    lumps = tuple(
        rng.randbytes(rng.choice([0, 1, 2, 255, 256, 1000]))
        for _ in range(LUMPS[magic])
    )
    return D0Key(magic, lumps, extra=rng.randbytes(rng.choice([0, 1, 50])))


def test_random_valid_keys_roundtrip():
    rng = random.Random(1234)
    for _ in range(500):
        key = _random_key(rng)
        assert loads(dumps(key)) == key


def test_random_garbage_only_raises_our_errors():
    """Whatever bytes come in, the parser must return a key or raise D0KeyError,
    never IndexError, struct.error, MemoryError, etc."""
    rng = random.Random(5678)
    magics = [m.value for m in FOURCC] + [b"xxxx"]
    for _ in range(2000):
        data = rng.choice(magics) + rng.randbytes(rng.randrange(0, 40))
        if rng.random() < 0.1:
            data = data[: rng.randrange(0, len(data) + 1)]  # random truncation
        try:
            key = loads(data)
        except D0KeyError:
            continue
        # If it parsed, it must serialize back to exactly the same bytes.
        assert dumps(key) == data
