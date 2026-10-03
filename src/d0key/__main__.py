"""Command line tool for d0_blind_id key files."""

# PYTHON_ARGCOMPLETE_OK
import argparse
import os
import sys
from pathlib import Path

try:
    import argcomplete
except ImportError:
    argcomplete = None

import d0key
from d0key import d0tag

PREVIEW_BYTES = 64


def parse_kv(text: str) -> tuple[str, str]:
    key, sep, value = text.partition("=")
    if not sep or not key or not value:
        raise argparse.ArgumentTypeError(
            f"expected KEY=VALUE with both parts non-empty, got {text!r}"
        )
    return key, value


def positive_int(text: str) -> int:
    n = int(text)
    if n < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return n


def write_bytes(path: Path, data: bytes, overwrite: bool) -> None:
    with open(path, "wb" if overwrite else "xb") as f:
        f.write(data)


def cmd_inspect(args: argparse.Namespace) -> int:
    key = d0key.loads(args.file.read_bytes())

    print(f"file:    {args.file}")
    print(f"type:    {key.magic.name}")
    print(f"lumps:   {key.nlumps}")
    # Only sizes are shown, the lumps hold the private key itself!
    for i, size in enumerate(key.lumpsizes):
        print(f"    lump {i}: {size} bytes")

    if not key.extra:
        print("trailer: none")
        return 0

    if not key.extra.startswith(d0tag.MAGIC):
        print(f"trailer: {len(key.extra)} bytes, not a d0tag")
        print(f"    starts with: {key.extra[:PREVIEW_BYTES]!r}")
        return 0

    try:
        tag = d0tag.loads(key.extra)
    except d0tag.D0TagError as e:
        print(f"invalid d0tag: {e}")
        return 1

    print(f"d0tag v{tag.version}, {len(tag.entries)} entries")
    for k, v in tag.entries:
        print(f"    {k} = {v!r}")
    return 0


def save_key(
    args: argparse.Namespace, original: bytes, key: d0key.D0Key, verb: str
) -> None:
    """Write `key` to --output, or over args.file (keep FILE.bak) for --in-place."""
    if args.in_place:
        backup = args.file.with_name(args.file.name + ".bak")
        write_bytes(backup, original, overwrite=False)  # refuse if backup exists
        write_bytes(args.file, d0key.dumps(key), overwrite=True)
        print(f"{verb} {args.file} (backup: {backup})")
    else:
        write_bytes(args.output, d0key.dumps(key), args.force)
        print(f"wrote {args.output}")


def cmd_dummy(args: argparse.Namespace) -> int:
    if args.random:
        blob = os.urandom(args.size)
    else:
        blob = bytes(i % 256 for i in range(args.size))  # reproducible

    key = d0key.D0Key(d0key.FOURCC.D0SI, (blob,))

    if args.tag:
        key = d0tag.attach(key, d0tag.D0Tag.from_dict(dict(args.tag)))

    write_bytes(args.output, d0key.dumps(key), args.force)
    print(f"wrote {args.output} (D0SI, {args.size}-byte lump)")
    return 0


def cmd_tag(args: argparse.Namespace) -> int:
    original = args.file.read_bytes()
    key = d0key.loads(original)

    entries: dict[str, str] = {}
    if key.extra:
        if key.extra.startswith(d0tag.MAGIC):
            entries.update(d0tag.loads(key.extra).entries)  # merge into existing tag
        elif not args.force:
            raise ValueError(
                f"trailer holds {len(key.extra)} bytes that are not a d0tag, "
                "use --force to replace them"
            )
    entries.update(args.entries)

    tagged = d0tag.attach(key, d0tag.D0Tag.from_dict(entries))

    save_key(args, original, tagged, "tagged")
    return 0


def cmd_untag(args: argparse.Namespace) -> int:
    original = args.file.read_bytes()
    key = d0key.loads(original)

    if not key.extra:
        raise ValueError("nothing to remove, the key has no trailer")

    remaining: dict[str, str] = {}
    try:
        tag = d0tag.loads(key.extra)
    except d0tag.D0TagError as e:
        if args.keys:
            raise ValueError(
                f"cannot remove keys, the trailer is not a valid d0tag ({e})"
            ) from e
        if not args.force:
            raise ValueError(
                f"trailer holds {len(key.extra)} bytes that are not a valid d0tag, "
                "use --force to remove them"
            ) from e
    else:
        if args.keys:
            remaining = dict(tag.entries)
            missing = [k for k in args.keys if k not in remaining]
            if missing:
                raise ValueError(f"no such key: {', '.join(map(repr, missing))}")
            for k in args.keys:
                del remaining[k]

        # with no KEY argument the whole tag goes, so remaining stays empty

    # an empty tag would still cost 7 bytes, so drop the trailer entirely  instead
    extra = d0tag.dumps(d0tag.D0Tag.from_dict(remaining)) if remaining else b""
    stripped = d0key.D0Key(key.magic, key.lumps, extra=extra)
    save_key(args, original, stripped, "untagged")
    return 0


def cmd_completion(args: argparse.Namespace) -> int:
    if argcomplete is None:
        raise ValueError(
            "shell completion needs argcomplete, install d0key[completion]"
        )
    print(argcomplete.shellcode(["d0hickey"], shell=args.shell))
    return 0


def add_destination(s: argparse.ArgumentParser, force_help: str) -> None:
    """Add the -e/--in-place/-f options shared by the commands that write a key."""
    dest = s.add_mutually_exclusive_group(required=True)
    dest.add_argument("-o", "--output", type=Path, help="write the result here")
    dest.add_argument(
        "--in-place",
        action="store_true",
        help="modity FILE, saving the original as FILE.bak first",
    )
    s.add_argument("-f", "--force", action="store_true", help=force_help)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Inspect and tag d0_blind_id key files.")

    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("inspect", help="show the layout and any d0tag of a key file")
    s.add_argument("file", type=Path)
    s.set_defaults(func=cmd_inspect)

    s = sub.add_parser("dummy", help="create a dummy d0si key for testing")
    s.add_argument("output", type=Path)
    s.add_argument(
        "-s",
        "--size",
        type=positive_int,
        default=255,
        help="size of the lump in bytes (default: 255)",
    )
    s.add_argument(
        "-r",
        "--random",
        action="store_true",
        help="fill with random bytes instead of a fixed pattern",
    )
    s.add_argument(
        "-t",
        "--tag",
        type=parse_kv,
        action="append",
        metavar="KEY=VALUE",
        help="attach a d0tag entry (repeatable)",
    )
    s.add_argument(
        "-f", "--force", action="store_true", help="overwrite OUTPUT if it exists"
    )
    s.set_defaults(func=cmd_dummy)

    s = sub.add_parser("tag", help="add entries to the d0tag of a key file")
    s.add_argument("file", type=Path)
    s.add_argument("entries", type=parse_kv, nargs="+", metavar="KEY=VALUE")
    add_destination(s, "overwrite OUTPUT, or replace a trailer that is not a d0tag")
    s.set_defaults(func=cmd_tag)

    s = sub.add_parser(
        "untag", help="remove the d0tag, or some of its keys, from a key file"
    )
    s.add_argument("file", type=Path)
    s.add_argument(
        "keys",
        nargs="*",
        metavar="KEY",
        help="remove only these keys (default: remove the whole tag)",
    )
    add_destination(
        s, "overwrite OUTPUT, or remove a trailer that is not a valid d0tag"
    )
    s.set_defaults(func=cmd_untag)

    s = sub.add_parser("completion", help="print the shell completion script")
    s.add_argument("--shell", choices=["bash", "zsh", "fish", "tcsh"], default="bash")
    s.set_defaults(func=cmd_completion)

    if argcomplete:
        argcomplete.autocomplete(p)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (d0key.D0KeyError, d0tag.D0TagError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
