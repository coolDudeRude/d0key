# d0key

Python library for reading and writing `d0_blind_id` key files
(the `d0pk` public key and `d0si` ID files used by Xonotic).

It only parses and writes the container format. It does no cryptographic
validation.

## Format

A key file is a 4-byte magic (`d0pk`, `d0si`, ...) followed by length-prefixed
"lumps": each lump is a little-endian `u32` size followed by that many bytes.
Any bytes after the last lump are preserved as `extra`, so files round-trip
byte-for-byte.

| Magic  | Lumps |
|:-------|:-----:|
| `d0si` |   1   |
| `d0pk` |   2   |

Other magics are recognized but not yet supported.

## Installation

d0key requires Python 3.13 or newer and has no runtime dependencies. It is not
published on PyPI, so it is installed from Git (which must be available on your
`PATH`).

### As a dependency of your project

With [uv](https://docs.astral.sh/uv/):

```bash
uv add git+https://github.com/coolDudeRude/d0key.git
```

With pip, inside an activated virtual environment:

```bash
pip install git+https://github.com/coolDudeRude/d0key.git
```

### From a local checkout (development)

```bash
git clone https://github.com/coolDudeRude/d0key.git
cd d0key
uv sync
```

`uv sync` creates `.venv`, installs d0key in editable mode together with the
development dependencies (pytest, pytest-cov), so source changes take effect
immediately.

### Verify

```bash
python -c "import d0key; print(d0key.FOURCC.D0PK)"
```

Prefix the command with `uv run` if you installed from a checkout and have not
activated `.venv`.

## Usage

```python
import d0key

with open("key.d0pk", "rb") as f:
    key = d0key.load(f)

print(key.magic, key.nlumps, key.lumpsizes)

with open("copy.d0pk", "wb") as f:
    d0key.dump(key, f)

# bytes-based API
with open("key.d0pk", "rb") as f:
    raw = f.read()
key = d0key.loads(raw)
raw = d0key.dumps(key)
```

Files must be opened in binary mode (`"rb"` / `"wb"`).

A parsed `D0Key` has three fields: `magic`, `lumps` (a tuple of `bytes`) and
`extra` (any trailing bytes after the last lump).

Keys are immutable. To change one, build a new one with
`dataclasses.replace`:

```python
import dataclasses
from d0key import D0Key, FOURCC

key = D0Key(FOURCC.D0SI, (b"<blob>",), extra=b"foo")
new_key = dataclasses.replace(key, extra=b"bar")
```

## Errors

All errors raised for bad data inherit from `D0KeyError`:

- `D0FormatError`: the data is malformed (also a `ValueError`, has an
  `.offset` attribute)
- `D0UnsupportedTypeError`: known magic, but no lump layout defined yet

Passing the wrong type (for example a text-mode file) raises `TypeError`.

## Development

```bash
uv sync
uv run pytest
```

## License

MIT. See [LICENSE](LICENSE).
