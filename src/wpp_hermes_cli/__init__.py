"""Import-stable console entry point for the ``wpp-hermes`` command.

Hermes-launched shells may put Hermes' own venv on ``PYTHONPATH``. If an older
copy of ``pulse_labs_whatsapp_plusplus_hermes`` is installed there, a uvx console
script can accidentally import that old package instead of the package inside the
uvx tool environment. This tiny wrapper is imported under a unique module name,
then prepends its own site-packages directory before delegating to the real CLI.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path


def _prefer_own_site_packages() -> None:
    package_dir = Path(__file__).resolve().parent
    site_packages = str(package_dir.parent)
    try:
        sys.path.remove(site_packages)
    except ValueError:
        pass
    sys.path.insert(0, site_packages)


def main(argv: Sequence[str] | None = None) -> int:
    _prefer_own_site_packages()
    from pulse_labs_whatsapp_plusplus_hermes.cli import main as real_main

    return real_main(argv)


def installer_main(argv: Sequence[str] | None = None) -> int:
    _prefer_own_site_packages()
    from pulse_labs_whatsapp_plusplus_hermes.installer import main as real_main

    return real_main(argv)


__all__ = ["installer_main", "main"]
