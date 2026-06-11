"""Command-line interface for WhatsApp++ for Hermes Agent."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import installer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wpp-hermes",
        description="Install and manage WhatsApp++ for Hermes Agent.",
    )
    subparsers = parser.add_subparsers(dest="command")

    install = subparsers.add_parser(
        "install",
        help="Install WhatsApp++ into Hermes, patch the WhatsApp bridge, write the plugin shim, and enable it.",
        add_help=False,
    )
    install.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    patch_bridge = subparsers.add_parser(
        "patch-bridge",
        help="Patch only the bundled WhatsApp bridge endpoints.",
        add_help=False,
    )
    patch_bridge.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    enable = subparsers.add_parser(
        "enable",
        help="Write the Hermes plugin shim and enable the plugin without patching the bridge.",
        add_help=False,
    )
    enable.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    installer_help = subparsers.add_parser(
        "installer-help",
        help="Show the low-level installer flags.",
        add_help=False,
    )
    installer_help.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    return parser


def _strip_separator(args: Sequence[str]) -> list[str]:
    values = list(args)
    if values and values[0] == "--":
        return values[1:]
    return values


def main(argv: Sequence[str] | None = None) -> int:
    """Run the public CLI.

    The low-level installer still accepts the historical flag-only interface
    through ``wpp-hermes-install`` and ``whatsapp-plusplus-hermes-install``.
    This wrapper provides the cleaner PyPI/uvx UX, e.g.:

    ``uvx wpp-hermes install``
    """
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if not raw_args:
        build_parser().print_help()
        return 0

    if raw_args[0] in {"-h", "--help"}:
        build_parser().print_help()
        return 0

    command = raw_args[0]
    rest = _strip_separator(raw_args[1:])

    if command == "install":
        return installer.main(["--bootstrap", *rest])
    if command == "patch-bridge":
        return installer.main(rest)
    if command == "enable":
        return installer.main(["--no-patch", "--enable", *rest])
    if command == "installer-help":
        return installer.main(["--help", *rest])

    print(f"error: unknown command: {command}", file=sys.stderr)
    print("\nRun 'wpp-hermes --help' for usage.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
