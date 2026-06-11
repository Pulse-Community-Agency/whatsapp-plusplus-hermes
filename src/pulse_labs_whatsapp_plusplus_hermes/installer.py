#!/usr/bin/env python3
"""Install/activate Pulse Labs WhatsApp++ for Hermes Agent.

When installed as a pip/uv package, the Hermes plugin is exposed via the
``hermes_agent.plugins`` entry point. This installer handles the non-Python
part: patching the bundled Baileys WhatsApp bridge with /delete, /react, and
/star endpoints. It can optionally add the plugin to ``plugins.enabled``.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


PLUGIN_NAME = "whatsapp-plusplus"
LEGACY_PLUGIN_NAME = "whatsapp_plusplus"
PACKAGE_VERSION = "0.4.2"
SHIM_MARKER = "Pulse Labs WhatsApp++ pip shim"
DEFAULT_PACKAGE_SPEC = "wpp-hermes"

HELPER = """
function buildMessageKey({ chatId, messageId, fromMe = true, participant = undefined }) {
  const key = {
    id: messageId,
    fromMe: Boolean(fromMe),
    remoteJid: chatId,
  };
  if (participant) {
    key.participant = normalizeWhatsAppId(participant);
  }
  return key;
}
"""

ENDPOINTS = """
// Delete/revoke a message for everyone (when WhatsApp allows it)
app.post('/delete', async (req, res) => {
  if (!sock || connectionState !== 'connected') {
    return res.status(503).json({ error: 'Not connected to WhatsApp' });
  }

  const { chatId, messageId, fromMe = true, participant } = req.body;
  if (!chatId || !messageId) {
    return res.status(400).json({ error: 'chatId and messageId are required' });
  }

  try {
    const key = buildMessageKey({ chatId, messageId, fromMe, participant });
    await sendWithTimeout(chatId, { delete: key });
    res.json({ success: true, messageId, action: 'delete', key });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// React or remove a reaction from a message
app.post('/react', async (req, res) => {
  if (!sock || connectionState !== 'connected') {
    return res.status(503).json({ error: 'Not connected to WhatsApp' });
  }

  const { chatId, messageId, emoji = '', fromMe = true, participant } = req.body;
  if (!chatId || !messageId) {
    return res.status(400).json({ error: 'chatId and messageId are required' });
  }

  try {
    const key = buildMessageKey({ chatId, messageId, fromMe, participant });
    await sendWithTimeout(chatId, { react: { text: String(emoji || ''), key } });
    res.json({ success: true, messageId, action: emoji ? 'react' : 'unreact', emoji: String(emoji || ''), key });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Star or unstar a message locally for the WhatsApp account
app.post('/star', async (req, res) => {
  if (!sock || connectionState !== 'connected') {
    return res.status(503).json({ error: 'Not connected to WhatsApp' });
  }

  const { chatId, messageId, star = true, fromMe = true } = req.body;
  if (!chatId || !messageId) {
    return res.status(400).json({ error: 'chatId and messageId are required' });
  }

  try {
    const fromMeBool = Boolean(fromMe);
    await sock.chatModify({
      star: {
        messages: [{ id: messageId, fromMe: fromMeBool }],
        star: Boolean(star),
      },
    }, chatId);
    res.json({ success: true, messageId, action: star ? 'star' : 'unstar', fromMe: fromMeBool });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});
"""


def default_hermes_home() -> Path:
    if os.environ.get("HERMES_HOME"):
        return Path(os.environ["HERMES_HOME"]).expanduser()
    home = Path.home()
    candidates = [
        home / "AppData" / "Local" / "hermes",  # Windows Hermes Desktop
        home / "Library" / "Application Support" / "hermes",  # macOS app-style installs
        home / ".hermes",  # Hermes CLI / Linux / fallback
    ]

    # Prefer a candidate that looks like a real Hermes runtime home. On macOS it
    # is possible to have an app-support directory present while Hermes Desktop's
    # active runtime lives in ~/.hermes; choosing the first merely-existing
    # directory would make the clean `uvx wpp-hermes install` command target the
    # wrong profile.
    for candidate in candidates:
        if (
            (candidate / "hermes-agent" / "venv" / "Scripts" / "python.exe").exists()
            or (candidate / "hermes-agent" / "venv" / "bin" / "python").exists()
            or (candidate / "hermes-agent" / "scripts" / "whatsapp-bridge" / "bridge.js").exists()
            or (candidate / "config.yaml").exists()
        ):
            return candidate

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return home / ".hermes"


def default_config_path(hermes_home: Path) -> Path:
    return hermes_home / "config.yaml"


def default_hermes_python(hermes_home: Path) -> Path:
    windows_python = hermes_home / "hermes-agent" / "venv" / "Scripts" / "python.exe"
    if windows_python.exists():
        return windows_python
    return hermes_home / "hermes-agent" / "venv" / "bin" / "python"


def bridge_patch_status(bridge: Path) -> dict[str, bool]:
    if not bridge.exists():
        return {"exists": False, "helper": False, "delete": False, "react": False, "star": False}
    text = bridge.read_text(encoding="utf-8", errors="ignore")
    return {
        "exists": True,
        "helper": "function buildMessageKey(" in text,
        "delete": "app.post('/delete'" in text,
        "react": "app.post('/react'" in text,
        "star": "app.post('/star'" in text,
    }


def is_plugin_enabled(config_path: Path) -> bool:
    if not config_path.exists():
        return False
    try:
        import yaml

        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(loaded, dict):
        return False
    plugins = loaded.get("plugins")
    if not isinstance(plugins, dict):
        return False
    enabled = plugins.get("enabled")
    return isinstance(enabled, list) and PLUGIN_NAME in enabled


def entry_point_installed(hermes_python: Path | None = None) -> bool:
    if hermes_python is not None:
        if not hermes_python.exists():
            return False
        code = (
            "import importlib.metadata as md; "
            "eps=md.entry_points().select(group='hermes_agent.plugins'); "
            "raise SystemExit(0 if any(ep.name=='whatsapp-plusplus' and ep.value=='pulse_labs_whatsapp_plusplus_hermes' for ep in eps) else 1)"
        )
        try:
            return subprocess.run([str(hermes_python), "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        except Exception:
            return False
    try:
        entries = metadata.entry_points().select(group="hermes_agent.plugins")
    except Exception:
        return False
    return any(ep.name == PLUGIN_NAME and ep.value == "pulse_labs_whatsapp_plusplus_hermes" for ep in entries)


def run_node_check(bridge: Path) -> tuple[bool | None, str]:
    node = shutil.which("node")
    if not node:
        return None, "node not found; skipped bridge syntax check"
    if not bridge.exists():
        return False, "bridge.js not found"
    result = subprocess.run([node, "--check", str(bridge)], capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output or "node --check passed"


def collect_status(
    hermes_home: Path | None = None,
    bridge: Path | None = None,
    config: Path | None = None,
    hermes_python: Path | None = None,
) -> dict[str, Any]:
    home = (hermes_home or default_hermes_home()).expanduser().resolve()
    py = (hermes_python or default_hermes_python(home)).expanduser()
    br = (bridge or (home / "hermes-agent" / "scripts" / "whatsapp-bridge" / "bridge.js")).expanduser()
    cfg = (config or default_config_path(home)).expanduser()
    patch = bridge_patch_status(br)
    node_ok, node_message = run_node_check(br) if patch["exists"] else (False, "bridge.js not found")
    return {
        "version": PACKAGE_VERSION,
        "hermes_home": home,
        "hermes_home_exists": home.exists(),
        "hermes_python": py,
        "hermes_python_exists": py.exists(),
        "bridge": br,
        "bridge_patch": patch,
        "config": cfg,
        "config_exists": cfg.exists(),
        "plugin_enabled": is_plugin_enabled(cfg),
        "shim_dir": home / "plugins" / PLUGIN_NAME,
        "shim_exists": (home / "plugins" / PLUGIN_NAME / "__init__.py").exists(),
        "entry_point_installed": entry_point_installed(py),
        "uv": shutil.which("uv"),
        "node_check": node_ok,
        "node_message": node_message,
    }


def print_status(status: dict[str, Any]) -> None:
    patch = status["bridge_patch"]
    print(f"WhatsApp++ for Hermes v{status['version']}")
    print(f"Hermes home:        {status['hermes_home']} {'✓' if status['hermes_home_exists'] else '✗'}")
    print(f"Hermes Python:      {status['hermes_python']} {'✓' if status['hermes_python_exists'] else '✗'}")
    print(f"uv on PATH:         {status['uv'] or 'not found'} {'✓' if status['uv'] else '✗'}")
    print(f"Config:             {status['config']} {'✓' if status['config_exists'] else '✗'}")
    print(f"Plugin enabled:     {'yes ✓' if status['plugin_enabled'] else 'no ✗'}")
    print(f"Shim:               {status['shim_dir']} {'✓' if status['shim_exists'] else '✗'}")
    print(f"Pip entry point:    {'installed ✓' if status['entry_point_installed'] else 'not visible ✗'}")
    print(f"Bridge:             {status['bridge']} {'✓' if patch['exists'] else '✗'}")
    print(
        "Bridge endpoints:   "
        f"helper={'✓' if patch['helper'] else '✗'} "
        f"delete={'✓' if patch['delete'] else '✗'} "
        f"react={'✓' if patch['react'] else '✗'} "
        f"star={'✓' if patch['star'] else '✗'}"
    )
    node_ok = status["node_check"]
    node_icon = "✓" if node_ok is True else ("-" if node_ok is None else "✗")
    print(f"node --check:       {node_icon} {status['node_message']}")


def doctor_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show detected Hermes/WhatsApp++ install paths and status")
    parser.add_argument("--hermes-home", type=Path, default=None, help="Hermes home to inspect")
    parser.add_argument("--bridge", type=Path, default=None, help="Path to scripts/whatsapp-bridge/bridge.js")
    parser.add_argument("--config", type=Path, default=None, help="Path to Hermes config.yaml")
    parser.add_argument("--hermes-python", type=Path, default=None, help="Path to Hermes' Python executable")
    args = parser.parse_args(argv)
    status = collect_status(args.hermes_home, args.bridge, args.config, args.hermes_python)
    print_status(status)
    if not status["uv"]:
        print("\nuv was not found. Install uv first, for example: https://docs.astral.sh/uv/getting-started/installation/")
    if not status["hermes_python_exists"]:
        print("\nHermes Python was not found. If this is Hermes Desktop, pass --hermes-home or --hermes-python explicitly.")
    return 0


def verify_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a WhatsApp++ install without mutating files")
    parser.add_argument("--hermes-home", type=Path, default=None, help="Hermes home to inspect")
    parser.add_argument("--bridge", type=Path, default=None, help="Path to scripts/whatsapp-bridge/bridge.js")
    parser.add_argument("--config", type=Path, default=None, help="Path to Hermes config.yaml")
    parser.add_argument("--hermes-python", type=Path, default=None, help="Path to Hermes' Python executable")
    args = parser.parse_args(argv)
    status = collect_status(args.hermes_home, args.bridge, args.config, args.hermes_python)
    print_status(status)
    patch = status["bridge_patch"]
    required = {
        "Hermes Python exists": status["hermes_python_exists"],
        "uv available": bool(status["uv"]),
        "plugin enabled": status["plugin_enabled"],
        "shim exists": status["shim_exists"],
        "pip entry point installed": status["entry_point_installed"],
        "bridge patched": patch["exists"] and patch["helper"] and patch["delete"] and patch["react"] and patch["star"],
        "bridge syntax ok": status["node_check"] is not False,
    }
    failed = [name for name, ok in required.items() if not ok]
    if failed:
        print("\nVerify failed:")
        for name in failed:
            print(f"  - {name}")
        print("\nRun `wpp-hermes doctor` for paths, or reinstall with `uvx wpp-hermes install`.")
        return 1
    print("\nVerify passed: WhatsApp++ appears installed and patched.")
    return 0


def install_into_hermes_python(hermes_python: Path, package_spec: str) -> None:
    """Install this pip package into the Python environment that runs Hermes."""
    # Do not call resolve() here. macOS venv/bin/python is often a symlink to
    # the base framework interpreter; resolving it makes `uv pip install
    # --python ...` target the base Python instead of the Hermes venv.
    python_path = hermes_python.expanduser().absolute()
    if not python_path.exists():
        raise FileNotFoundError(
            f"Hermes Python not found: {python_path}\n\n"
            "WhatsApp++ must be installed into the same Python environment that runs Hermes.\n"
            "If Hermes Desktop is installed somewhere custom, pass:\n"
            "  wpp-hermes install --hermes-home <path-to-hermes-home>\n"
            "or:\n"
            "  wpp-hermes install --hermes-python <path-to-python>\n"
        )
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError(
            "uv was not found on PATH. Install uv, then rerun `uvx wpp-hermes install`.\n"
            "Install instructions: https://docs.astral.sh/uv/getting-started/installation/\n"
            "Hermes Desktop normally bundles uv, but raw CLI/server environments may need it installed separately."
        )
    subprocess.run([uv, "pip", "install", "--python", str(python_path), package_spec], check=True)


def patch_bridge(bridge: Path) -> bool:
    text = bridge.read_text(encoding="utf-8")
    changed = False

    if "function buildMessageKey(" not in text:
        marker = "function normalizeWhatsAppId(value)"
        if marker not in text:
            raise RuntimeError("Could not find normalizeWhatsAppId marker for helper insertion")
        text = text.replace(marker, HELPER + "\n" + marker, 1)
        changed = True

    if "app.post('/delete'" not in text:
        marker = "// MIME type map and media type inference for /send-media"
        if marker not in text:
            raise RuntimeError("Could not find /send-media marker for endpoint insertion")
        text = text.replace(marker, ENDPOINTS + "\n" + marker, 1)
        changed = True

    if changed:
        backup = bridge.with_suffix(bridge.suffix + ".whatsapp-plusplus.bak")
        if not backup.exists():
            shutil.copy2(bridge, backup)
        bridge.write_text(text, encoding="utf-8", newline="")
    return changed



def write_cli_shim(hermes_home: Path) -> Path:
    """Write a tiny user-plugin shim so ``hermes plugins list/enable`` can see us.

    Hermes' runtime discovers pip entry points directly, but the current
    ``hermes plugins`` CLI discovery path only scans directory plugins. The
    shim makes the pip-installed plugin visible to that CLI while still loading
    the package's canonical register() implementation.
    """
    plugin_dir = hermes_home / "plugins" / PLUGIN_NAME
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = plugin_dir / "plugin.yaml"
    init_file = plugin_dir / "__init__.py"
    manifest_text = f"""name: {PLUGIN_NAME}
version: {PACKAGE_VERSION}
description: Pulse Labs WhatsApp++ pip-installed Hermes plugin shim.
author: Pulse Labs
kind: standalone
provides_tools:
  - whatsapp_plusplus
"""
    init_text = f'''"""{SHIM_MARKER}."""
from pulse_labs_whatsapp_plusplus_hermes import register

__all__ = ["register"]
'''
    for path, content in ((manifest, manifest_text), (init_file, init_text)):
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing == content:
                continue
            if path.name == "__init__.py" and SHIM_MARKER not in existing:
                raise RuntimeError(f"Refusing to overwrite non-WhatsApp++ shim: {path}")
        path.write_text(content, encoding="utf-8")
    return plugin_dir



def archive_legacy_directory(hermes_home: Path) -> Path | None:
    """Move the old copied directory-plugin aside during package migration."""
    legacy = hermes_home / "plugins" / LEGACY_PLUGIN_NAME
    if not legacy.exists():
        return None
    manifest = legacy / "plugin.yaml"
    init_file = legacy / "__init__.py"
    fingerprint = ""
    for path in (manifest, init_file):
        if path.exists():
            fingerprint += path.read_text(encoding="utf-8", errors="ignore")[:4000]
    if "whatsapp-plusplus" not in fingerprint and "WhatsApp++" not in fingerprint:
        raise RuntimeError(f"Refusing to archive unrecognized legacy plugin directory: {legacy}")
    backup_dir = hermes_home / "plugin_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    base = backup_dir / f"{LEGACY_PLUGIN_NAME}.legacy.bak"
    target = base
    i = 1
    while target.exists():
        target = backup_dir / f"{LEGACY_PLUGIN_NAME}.legacy.bak.{i}"
        i += 1
    shutil.move(str(legacy), str(target))
    return target

def enable_plugin(config_path: Path) -> bool:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyYAML is required for --enable") from exc

    data: dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    plugins = data.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        plugins = {}
        data["plugins"] = plugins
    enabled = plugins.setdefault("enabled", [])
    if not isinstance(enabled, list):
        enabled = []
        plugins["enabled"] = enabled
    disabled = plugins.get("disabled")
    if isinstance(disabled, list):
        disabled[:] = [x for x in disabled if x not in {PLUGIN_NAME, LEGACY_PLUGIN_NAME}]
    # Prefer the packaged key over the legacy directory-plugin key to avoid
    # loading both copies after migrating an existing local install.
    enabled[:] = [x for x in enabled if x != LEGACY_PLUGIN_NAME]
    if PLUGIN_NAME in enabled:
        return False
    enabled.append(PLUGIN_NAME)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Patch Hermes WhatsApp bridge for Pulse Labs WhatsApp++")
    parser.add_argument("--hermes-home", type=Path, default=default_hermes_home())
    parser.add_argument("--bridge", type=Path, default=None, help="Path to scripts/whatsapp-bridge/bridge.js")
    parser.add_argument("--config", type=Path, default=None, help="Path to Hermes config.yaml")
    parser.add_argument("--bootstrap", action="store_true", help="One-command install: install this package into Hermes Python, patch the bridge, write the shim, and enable the plugin")
    parser.add_argument("--install-into-hermes", action="store_true", help="Run uv pip install into Hermes Desktop's Python before configuring the plugin")
    parser.add_argument("--hermes-python", type=Path, default=None, help="Path to the Python executable that runs Hermes Desktop")
    parser.add_argument("--package-spec", default=DEFAULT_PACKAGE_SPEC, help="Package spec to install when using --bootstrap or --install-into-hermes")
    parser.add_argument("--enable", action="store_true", help="Add whatsapp-plusplus to plugins.enabled")
    parser.add_argument("--no-patch", action="store_true", help="Only enable/write shim; do not patch bridge.js")
    parser.add_argument("--no-shim", action="store_true", help="Do not write the user-plugin CLI visibility shim")
    parser.add_argument("--keep-legacy-dir", action="store_true", help="Do not archive an old ~/.hermes/plugins/whatsapp_plusplus directory")
    args = parser.parse_args(argv)

    hermes_home = args.hermes_home.expanduser().resolve()
    if args.bootstrap:
        args.install_into_hermes = True
        args.enable = True

    bridge = args.bridge or (hermes_home / "hermes-agent" / "scripts" / "whatsapp-bridge" / "bridge.js")
    config = args.config or default_config_path(hermes_home)
    hermes_python = args.hermes_python or default_hermes_python(hermes_home)

    print(f"Hermes home:   {hermes_home}")
    print(f"Hermes Python: {hermes_python}")
    print(f"Bridge:        {bridge}")
    print(f"Config:        {config}")

    if args.install_into_hermes:
        install_into_hermes_python(hermes_python, args.package_spec)
        print(f"Installed package into Hermes Python: {hermes_python}")

    if not args.no_patch:
        if not bridge.exists():
            raise FileNotFoundError(f"Bridge not found: {bridge}")
        changed = patch_bridge(bridge)
        print(f"Patched bridge: {bridge}" if changed else f"Bridge already patched: {bridge}")

    if not args.no_shim:
        shim = write_cli_shim(hermes_home)
        print(f"Wrote Hermes CLI visibility shim: {shim}")

    if not args.keep_legacy_dir:
        archived = archive_legacy_directory(hermes_home)
        if archived is not None:
            print(f"Archived legacy directory plugin: {archived}")

    if args.enable:
        changed = enable_plugin(config)
        print(f"Enabled plugin in {config}" if changed else f"Plugin already enabled in {config}")
    else:
        print("Plugin entry point is installed. Enable it with: hermes plugins enable whatsapp-plusplus")

    print("Next: restart Hermes Gateway or start a fresh Hermes session so plugin/bridge changes load.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
