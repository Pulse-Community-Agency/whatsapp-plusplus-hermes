"""Command-line interface for WhatsApp++ for Hermes Agent."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import installer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wpp-hermes",
        description="Install, verify, and manage WhatsApp++ for Hermes Agent.",
    )
    parser.add_argument("--version", action="version", version=f"wpp-hermes {installer.PACKAGE_VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    for name, help_text in (
        ("install", "Install WhatsApp++ into Hermes, patch the WhatsApp bridge, write the plugin shim, and enable it."),
        ("patch-bridge", "Patch only the bundled WhatsApp bridge endpoints."),
        ("enable", "Write the Hermes plugin shim and enable the plugin without patching the bridge."),
        ("doctor", "Show detected Hermes/WhatsApp++ paths and installation status."),
        ("verify", "Verify an existing WhatsApp++ install without mutating files."),
        ("installer-help", "Show the low-level installer flags."),
    ):
        sub = subparsers.add_parser(name, help=help_text, add_help=False)
        sub.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    return parser


def install_help() -> str:
    return f"""usage: wpp-hermes install [options]

Install WhatsApp++ into Hermes, patch the bundled WhatsApp/Baileys bridge,
write the Hermes CLI visibility shim, and enable the plugin.

The clean public install command is:

  uvx wpp-hermes install

Common options:
  --hermes-home PATH      Hermes home to install into.
                          Windows Desktop usually: C:/Users/<you>/AppData/Local/hermes
                          macOS app-style installs: ~/Library/Application Support/hermes
                          macOS/Linux CLI usually: ~/.hermes
  --hermes-python PATH    Python executable used by Hermes. Use this if auto-detection fails.
  --bridge PATH           Path to scripts/whatsapp-bridge/bridge.js.
  --config PATH           Path to Hermes config.yaml.
  --package-spec SPEC     Package spec installed into Hermes Python.
                          Default: {installer.DEFAULT_PACKAGE_SPEC}
  --keep-legacy-dir       Do not archive an old ~/.hermes/plugins/whatsapp_plusplus directory.
  --no-patch              Install/enable without patching bridge.js.
  --no-shim               Do not write ~/.hermes/plugins/whatsapp-plusplus shim.

After install, restart Hermes Gateway/Desktop or start a fresh Hermes session.

Diagnostics:
  wpp-hermes doctor       Show detected paths and status.
  wpp-hermes verify       Fail if plugin/shim/config/bridge checks do not pass.
"""


def _strip_separator(args: Sequence[str]) -> list[str]:
    values = list(args)
    if values and values[0] == "--":
        return values[1:]
    return values


def _wants_help(args: Sequence[str]) -> bool:
    return any(arg in {"-h", "--help"} for arg in args)


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
    if raw_args[0] in {"--version", "-V"}:
        print(f"wpp-hermes {installer.PACKAGE_VERSION}")
        return 0

    command = raw_args[0]
    rest = _strip_separator(raw_args[1:])

    if command == "install":
        if _wants_help(rest):
            print(install_help())
            return 0
        return installer.main(["--bootstrap", *rest])
    if command == "patch-bridge":
        return installer.main(rest)
    if command == "enable":
        return installer.main(["--no-patch", "--enable", *rest])
    if command == "doctor":
        return installer.doctor_main(rest)
    if command == "verify":
        return installer.verify_main(rest)
    if command == "installer-help":
        return installer.main(["--help", *rest])

    print(f"error: unknown command: {command}", file=sys.stderr)
    print("\nRun 'wpp-hermes --help' for usage.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
