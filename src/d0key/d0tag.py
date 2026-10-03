import struct
from collections.abc import Callable
from dataclasses import dataclass, replace

from . import D0Key

MAGIC = b"d0tg"
LATEST = 1


class D0TagError(Exception):
    """Base class for all errors from d0tag."""


class D0TagFormatError(D0TagError, ValueError):
    """The data is not a valid d0tag blob."""

    def __init__(self, message: str, offset: int | None = None) -> None:
        if offset is not None:
            message = f"{message} (at byte offset {offset})"
        super().__init__(message)
        self.offset = offset


class D0TagUnsupportedVersionError(D0TagError):
    """Valid d0tg header, but the version is unknown to this library."""

    def __init__(self, version: int) -> None:
        super().__init__(f"unsupported d0tag version {version}")
        self.version = version


Entries = tuple[tuple[str, str], ...]


# Version 1 decoder / encoder


def _decode_v1(data: bytes, pos: int) -> tuple[Entries, int]:
    if pos + 2 > len(data):
        raise D0TagFormatError("truncated before entry count", offset=pos)

    (count,) = struct.unpack_from("<H", data, pos)
    pos += 2

    entries = []
    seen: set[str] = set()
    for i in range(count):
        if pos + 4 > len(data):
            raise D0TagFormatError(f"truncated before header of entry {i}", offset=pos)
        ksize, vsize = struct.unpack_from("<HH", data, pos)
        pos += 4
        if pos + ksize + vsize > len(data):
            raise D0TagFormatError(f"entry {i} overruns data", offset=pos)

        if ksize == 0:
            raise D0TagFormatError(f"entry {i} has an empty key", offset=pos)
        if vsize == 0:
            raise D0TagFormatError(f"entry {i} has an empty value", offset=pos)

        try:
            key = data[pos : pos + ksize].decode("utf-8")
            value = data[pos + ksize : pos + ksize + vsize].decode("utf-8")
        except UnicodeDecodeError as e:
            raise D0TagFormatError(f"entry {i} is not valid UTF-8", offset=pos) from e

        if key in seen:
            raise D0TagFormatError(f"entry {i} has duplicate key {key!r}", offset=pos)
        seen.add(key)

        pos += ksize + vsize
        entries.append((key, value))
    return tuple(entries), pos


def _encode_v1(entries: Entries) -> bytes:
    if len(entries) > 0xFFFF:
        raise ValueError("too many entries for d0tag v1")
    parts = [struct.pack("<H", len(entries))]
    for key, value in entries:
        k, v = key.encode("utf-8"), value.encode("utf-8")

        if len(k) > 0xFFFF:
            raise ValueError(f"entry {key!r} too large for d0tag v1")

        if len(v) > 0xFFFF:
            raise ValueError(f"entry {key!r} value too large for d0tag v1")

        parts.append(struct.pack("<HH", len(k), len(v)) + k + v)
    return b"".join(parts)


@dataclass(frozen=True)
class _Codec:
    decode: Callable[[bytes, int], tuple[Entries, int]]
    encode: Callable[[Entries], bytes]


_CODECS: dict[int, _Codec] = {
    1: _Codec(_decode_v1, _encode_v1),
}


@dataclass(frozen=True)
class D0Tag:
    entries: Entries = ()
    version: int = LATEST

    def __post_init__(self):
        if self.version not in _CODECS:
            raise D0TagUnsupportedVersionError(self.version)

        seen: set[str] = set()
        for key, value in self.entries:
            if not key:
                raise ValueError("empty key")
            if not isinstance(value, str):
                raise TypeError(f"value for {key!r} must be str")
            if not value:
                raise ValueError(f"empty value for {key!r}")

            if key in seen:
                raise ValueError(f"duplicate key {key!r}")
            seen.add(key)

    @classmethod
    def from_dict(cls, d: dict[str, str], version: int = LATEST) -> "D0Tag":
        return cls(tuple(d.items()), version)

    def to_dict(self) -> dict[str, str]:
        return dict(self.entries)

    def get(self, key: str, default: str | None = None) -> str | None:
        for k, v in self.entries:
            if k == key:
                return v
        return default

    @classmethod
    def from_bytes(cls, data: bytes) -> "D0Tag":
        data = bytes(data)
        if len(data) < 5:
            raise D0TagFormatError("too small for d0tag header", offset=0)

        if data[:4] != MAGIC:
            raise D0TagFormatError(f"bad d0tag magic {data[:4]!r}", offset=0)
        version = data[4]
        codec = _CODECS.get(version)

        if codec is None:
            raise D0TagUnsupportedVersionError(version)
        entries, end = codec.decode(data, 5)

        if end != len(data):
            raise D0TagFormatError(
                f"{len(data) - end} unexpected trailing bytes", offset=end
            )

        return cls(entries, version)

    def to_bytes(self, version: int | None = None) -> bytes:
        v = self.version if version is None else version
        codec = _CODECS.get(v)

        if codec is None:
            raise D0TagUnsupportedVersionError(v)

        return MAGIC + bytes([v]) + codec.encode(self.entries)


def loads(data: bytes) -> D0Tag:
    return D0Tag.from_bytes(data)


def dumps(tag: D0Tag, version: int | None = None) -> bytes:
    return tag.to_bytes(version)


def from_key(key: D0Key) -> D0Tag | None:
    return loads(key.extra) if key.extra else None


def attach(key: D0Key, tag: D0Tag) -> D0Key:
    return replace(key, extra=dumps(tag))
