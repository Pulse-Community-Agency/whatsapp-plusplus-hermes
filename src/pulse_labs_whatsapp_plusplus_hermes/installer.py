#!/usr/bin/env python3
"""Install/activate Pulse Labs WhatsApp++ for Hermes Agent.

When installed as a pip/uv package, the Hermes plugin is exposed via the
``hermes_agent.plugins`` entry point. This installer handles the non-Python
part: patching the bundled Baileys WhatsApp bridge with /delete, /react, and
/star endpoints. It can optionally add the plugin to ``plugins.enabled``.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Any

PLUGIN_NAME = "whatsapp-plusplus"
LEGACY_PLUGIN_NAME = "whatsapp_plusplus"
SHIM_MARKER = "Pulse Labs WhatsApp++ pip shim"

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
    local = home / "AppData" / "Local" / "hermes"
    if local.exists():
        return local
    return home / ".hermes"


def default_config_path(hermes_home: Path) -> Path:
    return hermes_home / "config.yaml"


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
version: 0.2.0
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
    parser.add_argument("--enable", action="store_true", help="Add whatsapp-plusplus to plugins.enabled")
    parser.add_argument("--no-patch", action="store_true", help="Only enable/write shim; do not patch bridge.js")
    parser.add_argument("--no-shim", action="store_true", help="Do not write the user-plugin CLI visibility shim")
    args = parser.parse_args(argv)

    hermes_home = args.hermes_home.expanduser().resolve()
    bridge = args.bridge or (hermes_home / "hermes-agent" / "scripts" / "whatsapp-bridge" / "bridge.js")
    config = args.config or default_config_path(hermes_home)

    if not args.no_patch:
        if not bridge.exists():
            raise FileNotFoundError(f"Bridge not found: {bridge}")
        changed = patch_bridge(bridge)
        print(f"Patched bridge: {bridge}" if changed else f"Bridge already patched: {bridge}")

    if not args.no_shim:
        shim = write_cli_shim(hermes_home)
        print(f"Wrote Hermes CLI visibility shim: {shim}")

    if args.enable:
        changed = enable_plugin(config)
        print(f"Enabled plugin in {config}" if changed else f"Plugin already enabled in {config}")
    else:
        print("Plugin entry point is installed. Enable it with: hermes plugins enable whatsapp-plusplus")

    print("Next: restart Hermes Gateway or start a fresh Hermes session so plugin/bridge changes load.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
