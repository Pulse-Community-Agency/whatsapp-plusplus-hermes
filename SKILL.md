---
name: whatsapp-plusplus-hermes
description: Install or rebuild the Pulse Labs WhatsApp++ Hermes plugin for advanced WhatsApp edit/delete/react/star controls.
license: MIT
tags:
  - hermes
  - whatsapp
  - baileys
  - messaging
  - plugin
---

# WhatsApp++ for Hermes Agent

Use this skill when the user wants to install, understand, or rebuild the Pulse Labs WhatsApp++ plugin for Hermes Agent.

WhatsApp++ adds a Hermes tool named `whatsapp_plusplus` for advanced WhatsApp message controls through the local Baileys bridge:

- edit a Hermes/bot-sent message
- delete/revoke a message for everyone when WhatsApp allows it
- react or unreact
- star or unstar a message locally for the connected WhatsApp account

## Install the Pulse Labs version

1. Clone the public repo:

```bash
git clone https://gitlab.com/pulse-labs/whatsapp-plusplus-hermes.git
cd whatsapp-plusplus-hermes
```

2. Run the installer:

```bash
python scripts/install.py
```

3. Restart Hermes Gateway or restart only the WhatsApp bridge so the new plugin and endpoints load.

4. Verify:

```bash
python -m py_compile ~/.hermes/plugins/whatsapp_plusplus/*.py
node --check ~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js
hermes plugins list
```

Endpoint checks should return HTTP 400 for missing fields, not HTTP 404:

```bash
curl -i -X POST http://127.0.0.1:3000/delete -H 'Content-Type: application/json' -d '{}'
curl -i -X POST http://127.0.0.1:3000/react  -H 'Content-Type: application/json' -d '{}'
curl -i -X POST http://127.0.0.1:3000/star   -H 'Content-Type: application/json' -d '{}'
```

## One-line prompt to install

Install Pulse Labs WhatsApp++ for Hermes from https://gitlab.com/pulse-labs/whatsapp-plusplus-hermes, copy the plugin into my active Hermes profile, patch the bundled WhatsApp bridge with the repo installer, restart only the WhatsApp bridge if needed, and verify with py_compile, node --check, hermes plugins list, and safe /delete /react /star endpoint checks.

## One-line prompt to rebuild from scratch

Rebuild WhatsApp++ for Hermes from scratch: create a Hermes plugin exposing a whatsapp_plusplus tool with actions edit/delete_for_everyone/react/unreact/star/unstar, require safety_ack=USER_EXPLICITLY_REQUESTED_THIS for edit/delete, patch the local Baileys WhatsApp bridge with /delete, /react, and /star endpoints using Baileys message keys, and verify with py_compile, node --check, hermes plugins list, bridge health, and a disposable WhatsApp smoke test only after I explicitly approve edit/delete tests.

## Safety

Edit and delete-for-everyone are history-changing actions. Only use them when the user explicitly asks for that exact operation in the current conversation. The plugin requires `safety_ack=USER_EXPLICITLY_REQUESTED_THIS` for edit/delete, but this is a guardrail, not a cryptographic permission system. A rogue, compromised, or poorly instructed agent with tool access could still attempt to pass the acknowledgement string.

Prefer corrected follow-up messages over editing history. Never allow autonomous/background jobs to edit or delete without human approval. Use a dedicated bot WhatsApp account rather than a personal account.

## Bridge endpoints

The local Baileys bridge should expose:

- `POST /edit` with `{ chatId, messageId, message }`
- `POST /delete` with `{ chatId, messageId, fromMe?, participant? }`
- `POST /react` with `{ chatId, messageId, emoji, fromMe?, participant? }`
- `POST /star` with `{ chatId, messageId, star?, fromMe? }`

The Hermes plugin calls these endpoints at `WHATSAPP_PLUSPLUS_BRIDGE_URL` or `http://127.0.0.1:3000` by default.
