import enum
import struct
from dataclasses import dataclass
from typing import BinaryIO

__version__ = "0.1.0"


# FourCCs headers
class FOURCC(enum.Enum):
    D0PK = b"d0pk"
    D0SK = b"d0sk"
    D0PI = b"d0pi"
    D0SI = b"d0si"
    D0IQ = b"d0iq"
    D0IR = b"d0ir"
    D0ER = b"d0er"
    D0IC = b"d0ic"


LUMPS = {
    FOURCC.D0SI: 1,
    FOURCC.D0PK: 2,
}


class D0KeyError(Exception):
    """Base class for all errors from this module."""


class D0FormatError(D0KeyError, ValueError):
    """The data is not a valid d0 key file."""

    def __init__(self, message: str, offset: int | None = None):
        if offset is not None:
            message = f"{message} (at byte offset {offset})"
        super().__init__(message)
        self.offset = offset


class D0UnsupportedTypeError(D0KeyError):
    """Recognized d0 file type, but no lump layout is defined for it."""


@dataclass(frozen=True)
class D0Key:
    """A parsed d0_blind_id key file, magic, lumps and any trailing bytes."""

    magic: FOURCC
    lumps: tuple[bytes, ...]
    extra: bytes = b""

    def __post_init__(self):
        if not isinstance(self.magic, FOURCC):
            raise TypeError(f"magic must be FOURCC, got {type(self.magic).__name__}")
        if not isinstance(self.lumps, tuple):
            raise TypeError(f"lumps must be a tuple, got {type(self.lumps).__name__}")
        for i, lump in enumerate(self.lumps):
            if not isinstance(lump, bytes):
                raise TypeError(f"lump {i} must be bytes, got {type(lump).__name__}")
        if not isinstance(self.extra, bytes):
            raise TypeError(f"extra must be bytes, got {type(self.extra).__name__}")

        expected = LUMPS.get(self.magic)
        if expected is None:
            raise D0UnsupportedTypeError(f"no lump layout for {self.magic.name}")
        if len(self.lumps) != expected:
            raise ValueError(
                f"{self.magic.name} needs {expected} lumps, got {len(self.lumps)}"
            )

    @property
    def nlumps(self) -> int:
        return len(self.lumps)

    @property
    def lumpsizes(self) -> list[int]:
        return [len(lump) for lump in self.lumps]

    @classmethod
    def from_bytes(cls, data: bytes) -> "D0Key":
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError(f"expected a bytes-like object, got {type(data).__name__}")

        data = bytes(data)
        if len(data) < 4:
            raise D0FormatError("file too small to contain a header", offset=0)

        try:
            magic = FOURCC(data[:4])
        except ValueError:
            raise D0FormatError(f"unknown header {data[:4]!r}", offset=0) from None

        if magic not in LUMPS:
            raise D0UnsupportedTypeError(f"no lump layout for {magic.name}")

        pos = 4

        lumps = []
        for i in range(LUMPS[magic]):
            if pos + 4 > len(data):
                raise D0FormatError(f"truncated before size of lump {i}", offset=pos)

            (size,) = struct.unpack_from("<I", data, pos)
            pos += 4

            if pos + size > len(data):
                raise D0FormatError(
                    f"lump {i} claims {size} bytes but only {len(data) - pos} remain",
                    offset=pos,
                )
            lumps.append(data[pos : pos + size])
            pos += size

        return cls(magic, tuple(lumps), extra=data[pos:])

    def to_bytes(self) -> bytes:
        parts = [self.magic.value]
        for lump in self.lumps:
            parts.append(struct.pack("<I", len(lump)))
            parts.append(lump)
        parts.append(self.extra)
        return b"".join(parts)


def loads(data: bytes) -> D0Key:
    return D0Key.from_bytes(data)


def dumps(key: D0Key) -> bytes:
    return key.to_bytes()


def load(fp: BinaryIO) -> D0Key:
    return loads(fp.read())


def dump(key: D0Key, fp: BinaryIO) -> None:
    fp.write(dumps(key))
