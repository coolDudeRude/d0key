import pytest

from d0key import (
    FOURCC,
    LUMPS,
    D0FormatError,
    D0Key,
    D0KeyError,
    D0UnsupportedTypeError,
    loads,
)

UNSUPPORTED = [m for m in FOURCC if m not in LUMPS]


def le(n: int) -> bytes:
    return n.to_bytes(4, "little")


# Good data
def test_parse_d0si():
    key = loads(b"d0si" + b"\x03\x00\x00\x00" + b"abc")
    assert key.magic is FOURCC.D0SI
    assert key.lumps == (b"abc",)
    assert key.extra == b""


def test_parse_d0pk():
    raw = b"d0pk" + le(2) + b"ab" + le(3) + b"cde"
    key = loads(raw)
    assert key.magic is FOURCC.D0PK
    assert key.lumps == (b"ab", b"cde")
    assert key.extra == b""


def test_zero_length_lump():
    key = loads(b"d0si" + le(0))
    assert key.lumps == (b"",)
    assert key.extra == b""


def test_zero_length_lumps_in_d0pk():
    key = loads(b"d0pk" + le(0) + le(0))
    assert key.lumps == (b"", b"")


def test_trailing_bytes_go_to_extra():
    key = loads(b"d0si" + le(3) + b"abc" + b"tail")
    assert key.lumps == (b"abc",)
    assert key.extra == b"tail"


def test_no_trailing_bytes_gives_empty_extra():
    assert loads(b"d0si" + le(1) + b"a").extra == b""


def test_size_equal_to_remaining_is_valid():
    assert loads(b"d0si" + le(5) + b"12345").lumps == (b"12345",)


def test_length_prefix_is_little_endian():
    key = loads(b"d0si" + b"\x00\x01\x00\x00" + b"x" * 256)
    assert len(key.lumps[0]) == 256


def test_from_bytes_and_loads_agree():
    raw = b"d0si" + le(3) + b"abc"
    assert D0Key.from_bytes(raw) == loads(raw)


@pytest.mark.parametrize("wrap", [bytearray, memoryview])
def test_bytes_like_input_is_accepted_and_normalized(wrap):
    raw = b"d0pk" + le(2) + b"ab" + le(3) + b"cde" + b"tail"
    key = loads(wrap(raw))
    assert key == loads(raw)
    # Everything stored must be real `bytes`, not bytearray/memoryview.
    assert all(type(lump) is bytes for lump in key.lumps)
    assert type(key.extra) is bytes


# Bad data -> D0FormatError
@pytest.mark.parametrize("data", [b"", b"d", b"d0", b"d0s"])
def test_too_small_for_header(data):
    with pytest.raises(D0FormatError, match="too small") as exc:
        loads(data)
    assert exc.value.offset == 0


@pytest.mark.parametrize(
    "data",
    [
        b"xxxx" + le(0),
        b"D0SI" + le(0),  # magic is case-sensitive
        b"\x00\x00\x00\x00" + le(0),
    ],
)
def test_unknown_magic(data):
    with pytest.raises(D0FormatError, match="unknown header") as exc:
        loads(data)
    assert exc.value.offset == 0


def test_exactly_four_bytes_is_truncated_before_first_size():
    with pytest.raises(D0FormatError, match="lump 0") as exc:
        loads(b"d0si")
    assert exc.value.offset == 4


@pytest.mark.parametrize("partial", [b"\x01", b"\x01\x00", b"\x01\x00\x00"])
def test_partial_size_field(partial):
    with pytest.raises(D0FormatError, match="lump 0") as exc:
        loads(b"d0si" + partial)
    assert exc.value.offset == 4


def test_d0pk_missing_second_size_field():
    # header(4) + size(4) + 1 byte of lump 0 = 9 bytes, then nothing.
    with pytest.raises(D0FormatError, match="lump 1") as exc:
        loads(b"d0pk" + le(1) + b"a")
    assert exc.value.offset == 9


def test_d0pk_partial_second_size_field():
    with pytest.raises(D0FormatError, match="lump 1") as exc:
        loads(b"d0pk" + le(1) + b"a" + b"\x01\x00")
    assert exc.value.offset == 9


def test_lump_claims_more_than_remaining():
    with pytest.raises(D0FormatError, match="claims 4 bytes but only 3") as exc:
        loads(b"d0si" + le(4) + b"abc")
    assert exc.value.offset == 8


def test_size_one_more_than_remaining_is_an_error():
    with pytest.raises(D0FormatError, match="claims 6 bytes but only 5"):
        loads(b"d0si" + le(6) + b"12345")


def test_huge_size():
    with pytest.raises(D0FormatError, match="claims 4294967295") as exc:
        loads(b"d0si" + b"\xff\xff\xff\xff" + b"abc")
    assert exc.value.offset == 8


def test_second_lump_too_big():
    # header(4) + size(4) + lump(1) + size(4) = offset 13
    with pytest.raises(D0FormatError, match="lump 1") as exc:
        loads(b"d0pk" + le(1) + b"a" + le(5) + b"abc")
    assert exc.value.offset == 13


# Recognized but unsupported types
@pytest.mark.parametrize("magic", UNSUPPORTED)
def test_unsupported_type(magic):
    with pytest.raises(D0UnsupportedTypeError):
        loads(magic.value + b"\x00" * 16)


# Wrong argument type -> TypeError
@pytest.mark.parametrize("bad", ["d0si", None, 5, [b"d0si"]])
def test_non_bytes_input_raises_typeerror(bad):
    with pytest.raises(TypeError):
        loads(bad)


# The exception classes themselves
def test_format_error_hierarchy():
    assert issubclass(D0FormatError, D0KeyError)
    assert issubclass(D0FormatError, ValueError)


def test_unsupported_error_hierarchy():
    assert issubclass(D0UnsupportedTypeError, D0KeyError)


def test_format_error_with_offset():
    err = D0FormatError("boom", offset=7)
    assert err.offset == 7
    assert "byte offset 7" in str(err)


def test_format_error_without_offset():
    err = D0FormatError("boom")
    assert err.offset is None
    assert str(err) == "boom"


def test_one_except_catches_everything_from_this_module():
    for bad in (b"", b"xxxx", b"d0si", b"d0ic" + b"\x00" * 8):
        with pytest.raises(D0KeyError):
            loads(bad)
