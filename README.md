# d0key

Python library and command line tool for reading, writing and tagging
`d0_blind_id` key files (the `d0pk` public key and `d0si` ID files used by
Xonotic).

It only parses and writes the container format. It does no cryptographic
validation.

| Part          | Purpose                                                                |
|:--------------|:-----------------------------------------------------------------------|
| `d0key`       | Parse and write key files. Files round-trip byte-for-byte.             |
| `d0key.d0tag` | Store key/value metadata in the trailing bytes of a key file.          |
| `d0hickey`    | Command line tool: inspect keys, create dummy keys, add/remove tags.   |

`d0tag` is this project's own format. It is not part of `d0_blind_id`.

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [File formats](#file-formats)
- [Library usage](#library-usage)
- [Command line](#command-line)
- [Shell completion](#shell-completion)
- [Errors](#errors)

## Installation

d0key requires Python 3.13 or newer and has no runtime dependencies. It is not
published on PyPI, so it is installed from Git (which must be available on your
`PATH`).

### Command line tool

Install `d0hickey` into its own isolated environment:

```bash
pipx install git+https://github.com/coolDudeRude/d0key.git
```

or, with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/coolDudeRude/d0key.git
```

Either puts `d0hickey` on your `PATH`. For tab completion, install with the
`completion` extra instead, see [Shell completion](#shell-completion).

### As a dependency of your project

With uv:

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
d0hickey --help
```

Prefix the commands with `uv run` if you installed from a checkout and have not
activated `.venv`. `python -m d0key` is equivalent to `d0hickey`.

## Quick start

```python
import d0key
from d0key import d0tag

with open("key.d0si", "rb") as f:
    key = d0key.load(f)

print(key.magic, key.nlumps, key.lumpsizes)

# Attach metadata and write a copy
tagged = d0tag.attach(key, d0tag.D0Tag.from_dict({"name": "alice"}))
with open("tagged.d0si", "wb") as f:
    d0key.dump(tagged, f)
```

The same from the command line:

```bash
d0hickey tag key.d0si name=alice -o tagged.d0si
d0hickey inspect tagged.d0si
```

## File formats

### Key files

A key file is a 4-byte magic (`d0pk`, `d0si`, ...) followed by length-prefixed
"lumps": each lump is a little-endian `u32` size followed by that many bytes.
Any bytes after the last lump are preserved as `extra`, so files round-trip
byte-for-byte.

| Magic  | Lumps |
|:-------|:-----:|
| `d0si` |   1   |
| `d0pk` |   2   |

The other magics (`d0sk`, `d0pi`, `d0iq`, `d0ir`, `d0er`, `d0ic`) are
recognized, but no lump layout is defined for them yet, so parsing them raises
`D0UnsupportedTypeError`.

> **Note:** `d0si` files contain a private key. Handle them accordingly.
> `d0hickey inspect` only prints lump sizes, never their contents.

### d0tag

A d0tag is an ordered list of key/value string pairs stored in the `extra`
bytes after the last lump. All integers are little-endian.

| Offset | Size | Field                                |
|-------:|-----:|:-------------------------------------|
|      0 |    4 | magic `d0tg`                         |
|      4 |    1 | version (currently `1`)              |
|      5 |    2 | entry count (`u16`)                  |
|      7 |  ... | entries, back to back                |

Version 1 entries:

| Size | Field                |
|-----:|:---------------------|
|    2 | key size (`u16`)     |
|    2 | value size (`u16`)   |
|  *n* | key (UTF-8)          |
|  *m* | value (UTF-8)        |

Rules:

- Keys and values are UTF-8 and must never be empty.
- Keys must be unique.
- Each key and value is at most 65535 bytes, and a tag has at most 65535
  entries.
- Entry order is preserved.
- An empty tag would still cost 7 bytes, so to remove all tags drop the trailer
  instead (`d0hickey untag` does this).

Other d0tag versions can be added behind the same API. Reading and writing pick
the codec from the version byte.

## Library usage

### Keys

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

A parsed `D0Key` has three fields: `magic` (a `FOURCC`), `lumps` (a tuple of
`bytes`) and `extra` (any trailing bytes after the last lump). It also has the
helpers `nlumps` and `lumpsizes`.

Keys are immutable. To change one, build a new one with
`dataclasses.replace`:

```python
import dataclasses
from d0key import D0Key, FOURCC

key = D0Key(FOURCC.D0SI, (b"<blob>",), extra=b"foo")
new_key = dataclasses.replace(key, extra=b"bar")
```

| Function                | Description                                    |
|:------------------------|:-----------------------------------------------|
| `loads(data)`           | Parse a key from `bytes`.                      |
| `dumps(key)`            | Serialize a key to `bytes`.                    |
| `load(fp)` / `dump(key, fp)` | Same, for binary file objects.            |

### Tags

`d0tag` lives in its own submodule and is not imported by `import d0key`:

```python
import d0key
from d0key import d0tag

key = d0key.loads(raw)

# Write, this replaces whatever the trailer held before
tag = d0tag.D0Tag.from_dict({"name": "alice", "server": "example.org"})
tagged = d0tag.attach(key, tag)
raw = d0key.dumps(tagged)

# Read
tag = d0tag.from_key(d0key.loads(raw))   # None if the key has no trailer
if tag is not None:
    print(tag.get("name"))               # "alice", or None / a default
    print(tag.to_dict())                 # {"name": "alice", "server": "example.org"}
    print(tag.entries)                   # (("name", "alice"), ("server", ...))
    print(tag.version)                   # 1
```

`from_key` raises `D0TagFormatError` if the trailer is not a valid d0tag. If the
trailer might hold something else, check first with
`key.extra.startswith(d0tag.MAGIC)`. To add entries to an existing tag, merge
them yourself before calling `attach`:

```python
entries = dict(d0tag.from_key(key).entries) if key.extra else {}
entries["role"] = "admin"
key = d0tag.attach(key, d0tag.D0Tag.from_dict(entries))
```

| Name                         | Description                                          |
|:-----------------------------|:-----------------------------------------------------|
| `D0Tag(entries, version)`    | Immutable tag. Validates keys, values and version.   |
| `D0Tag.from_dict(d)`         | Build a tag from a `dict` of `str` to `str`.         |
| `tag.to_dict()`              | The entries as a `dict`.                             |
| `tag.get(key, default=None)` | Look up one value.                                   |
| `loads(data)`                | Parse a tag from `bytes` (starting at the magic).    |
| `dumps(tag, version=None)`   | Serialize a tag, optionally as another version.      |
| `from_key(key)`              | The tag in `key.extra`, or `None` if there is none.  |
| `attach(key, tag)`           | A new key whose trailer is `tag`.                    |
| `MAGIC`, `LATEST`            | The `b"d0tg"` magic and the newest version number.   |

## Command line

```text
d0hickey inspect FILE
d0hickey dummy OUTPUT [-s SIZE] [-r] [-t KEY=VALUE]... [-f]
d0hickey tag FILE KEY=VALUE... (-o OUTPUT | --in-place) [-f]
d0hickey untag FILE [KEY...] (-o OUTPUT | --in-place) [-f]
d0hickey completion [--shell {bash,zsh,fish,tcsh}]
```

| Command      | Description                                                         |
|:-------------|:--------------------------------------------------------------------|
| `inspect`    | Show the type, lump sizes and any d0tag of a key file.              |
| `dummy`      | Create a dummy `d0si` key for testing the container format.         |
| `tag`        | Add entries to the d0tag of a key file.                             |
| `untag`      | Remove the whole d0tag, or only the given keys.                     |
| `completion` | Print the shell completion script.                                  |

Examples:

```bash
# Make a test key with two tags and look at it
d0hickey dummy test.d0si -t name=alice -t server=example.org
d0hickey inspect test.d0si
```

```text
file:    test.d0si
type:    D0SI
lumps:   1
    lump 0: 255 bytes
d0tag v1, 2 entries
    name = 'alice'
    server = 'example.org'
```

```bash
d0hickey tag test.d0si role=admin -o tagged.d0si   # write a new file
d0hickey tag test.d0si role=admin --in-place       # modify test.d0si (saves test.d0si.bak)
d0hickey untag tagged.d0si role --in-place         # remove one key (saves tagged.d0si.bak)
d0hickey untag test.d0si -o clean.d0si             # remove the whole tag
```

Behavior worth knowing:

- `dummy` fills the lump with a fixed, reproducible pattern (default size 255
  bytes), or with random bytes using `-r`. The result is not a usable
  cryptographic key.
- `tag` merges into an existing d0tag. Existing keys given again are
  overwritten.
- `tag` and `untag` need a destination: `-o OUTPUT` or `--in-place`.
- `-o` refuses to overwrite an existing file unless `-f` is given.
- `--in-place` first saves the original as `FILE.bak`, and refuses to run if
  that backup already exists.
- If the trailer holds bytes that are not a d0tag, `tag` and `untag` need `-f` to
  replace or remove them, and `untag KEY...` cannot work on them at all.
- `untag` with no `KEY` removes the whole tag. Removing the last key does the
  same.

## Shell completion

`d0hickey` uses [argcomplete](https://github.com/kislyuk/argcomplete) to
generate its completion script. It is an optional extra, so install with
`completion` enabled:

```bash
pipx install "d0key[completion] @ git+https://github.com/coolDudeRude/d0key.git"
```

or with uv:

```bash
uv tool install "d0key[completion] @ git+https://github.com/coolDudeRude/d0key.git"
```

Add this to your shell config, `~/.bashrc` in the case of bash:

```bash
if command -v d0hickey >/dev/null; then
 eval "$(d0hickey completion 2>/dev/null)"
fi
```

Open a new terminal, then try `d0hickey <TAB><TAB>`. Subcommands, options and
file names are completed.

Other shells: `d0hickey completion --shell zsh` (or `fish`, `tcsh`) prints the
script for that shell, see the argcomplete documentation for how to load it.

Without the extra, `d0hickey completion` exits with an error saying that
argcomplete is missing, and everything else works as usual. In a development
checkout, `uv sync --extra completion` installs it.

## Errors

Errors from the key format inherit from `D0KeyError`:

- `D0FormatError`: the data is malformed (also a `ValueError`, has an
  `.offset` attribute)
- `D0UnsupportedTypeError`: known magic, but no lump layout defined yet

Errors from d0tag are kept separate and inherit from `D0TagError`, since d0tag
is an extension and not part of the key format:

- `D0TagFormatError`: the blob is not a valid d0tag (also a `ValueError`, has an
  `.offset` attribute)
- `D0TagUnsupportedVersionError`: valid `d0tg` header, but an unknown version
  (has a `.version` attribute)

To catch everything from both:

```python
try:
    key = d0key.loads(raw)
    tag = d0tag.from_key(key)
except (d0key.D0KeyError, d0tag.D0TagError) as e:
    print(f"bad key file: {e}")
```

Building objects with invalid contents raises `ValueError`: a `D0Key` with the
wrong number of lumps, or a `D0Tag` with an empty key, an empty value or
duplicate keys. Passing the wrong type (for example a text-mode file, or a
non-`str` tag value) raises `TypeError`. Encoding a tag whose entries do not fit
the version's size limits raises `ValueError`.


## License

MIT. See [LICENSE](LICENSE).
