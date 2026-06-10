#!/usr/bin/env python3
"""Install WhatsApp++ for Hermes Agent.

This installer:
1. copies plugin/whatsapp_plusplus into the active Hermes profile plugins dir
2. patches the bundled Baileys WhatsApp bridge with /delete, /react, and /star endpoints

It is intentionally conservative and idempotent: if markers already exist, it leaves them alone.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


PLUGIN_NAME = "whatsapp_plusplus"

HELPER = """\nfunction buildMessageKey({ chatId, messageId, fromMe = true, participant = undefined }) {\n  const key = {\n    id: messageId,\n    fromMe: Boolean(fromMe),\n    remoteJid: chatId,\n  };\n  if (participant) {\n    key.participant = normalizeWhatsAppId(participant);\n  }\n  return key;\n}\n"""

ENDPOINTS = """\n// Delete/revoke a message for everyone (when WhatsApp allows it)\napp.post('/delete', async (req, res) => {\n  if (!sock || connectionState !== 'connected') {\n    return res.status(503).json({ error: 'Not connected to WhatsApp' });\n  }\n\n  const { chatId, messageId, fromMe = true, participant } = req.body;\n  if (!chatId || !messageId) {\n    return res.status(400).json({ error: 'chatId and messageId are required' });\n  }\n\n  try {\n    const key = buildMessageKey({ chatId, messageId, fromMe, participant });\n    await sendWithTimeout(chatId, { delete: key });\n    res.json({ success: true, messageId, action: 'delete', key });\n  } catch (err) {\n    res.status(500).json({ error: err.message });\n  }\n});\n\n// React or remove a reaction from a message\napp.post('/react', async (req, res) => {\n  if (!sock || connectionState !== 'connected') {\n    return res.status(503).json({ error: 'Not connected to WhatsApp' });\n  }\n\n  const { chatId, messageId, emoji = '', fromMe = true, participant } = req.body;\n  if (!chatId || !messageId) {\n    return res.status(400).json({ error: 'chatId and messageId are required' });\n  }\n\n  try {\n    const key = buildMessageKey({ chatId, messageId, fromMe, participant });\n    await sendWithTimeout(chatId, { react: { text: String(emoji || ''), key } });\n    res.json({ success: true, messageId, action: emoji ? 'react' : 'unreact', emoji: String(emoji || ''), key });\n  } catch (err) {\n    res.status(500).json({ error: err.message });\n  }\n});\n\n// Star or unstar a message locally for the WhatsApp account\napp.post('/star', async (req, res) => {\n  if (!sock || connectionState !== 'connected') {\n    return res.status(503).json({ error: 'Not connected to WhatsApp' });\n  }\n\n  const { chatId, messageId, star = true, fromMe = true } = req.body;\n  if (!chatId || !messageId) {\n    return res.status(400).json({ error: 'chatId and messageId are required' });\n  }\n\n  try {\n    const fromMeBool = Boolean(fromMe);\n    await sock.chatModify({\n      star: {\n        messages: [{ id: messageId, fromMe: fromMeBool }],\n        star: Boolean(star),\n      },\n    }, chatId);\n    res.json({ success: true, messageId, action: star ? 'star' : 'unstar', fromMe: fromMeBool });\n  } catch (err) {\n    res.status(500).json({ error: err.message });\n  }\n});\n"""


def default_hermes_home() -> Path:
    if os.environ.get("HERMES_HOME"):
        return Path(os.environ["HERMES_HOME"]).expanduser()
    home = Path.home()
    local = home / "AppData" / "Local" / "hermes"
    if local.exists():
        return local
    return home / ".hermes"


def copy_plugin(repo_root: Path, hermes_home: Path) -> Path:
    src = repo_root / "plugin" / PLUGIN_NAME
    if not src.exists():
        raise FileNotFoundError(f"Plugin source not found: {src}")
    dst = hermes_home / "plugins" / PLUGIN_NAME
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name == "__pycache__":
            continue
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    return dst


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Install WhatsApp++ for Hermes Agent")
    parser.add_argument("--hermes-home", type=Path, default=default_hermes_home())
    parser.add_argument("--bridge", type=Path, default=None, help="Path to scripts/whatsapp-bridge/bridge.js")
    parser.add_argument("--plugin-only", action="store_true", help="Copy plugin only; do not patch bridge")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    hermes_home = args.hermes_home.expanduser().resolve()
    bridge = args.bridge or (hermes_home / "hermes-agent" / "scripts" / "whatsapp-bridge" / "bridge.js")

    plugin_dir = copy_plugin(repo_root, hermes_home)
    print(f"Installed plugin: {plugin_dir}")

    if not args.plugin_only:
        if not bridge.exists():
            raise FileNotFoundError(f"Bridge not found: {bridge}")
        changed = patch_bridge(bridge)
        print(f"Patched bridge: {bridge}" if changed else f"Bridge already patched: {bridge}")

    print("Next: restart Hermes Gateway or restart only the WhatsApp bridge so changes load.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
