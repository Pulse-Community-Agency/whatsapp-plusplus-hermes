# WhatsApp++ for Hermes Agent

Advanced WhatsApp message controls for Hermes Agent: edit bot-sent messages, delete/revoke messages for everyone, react/unreact, and star/unstar messages through the local Baileys WhatsApp bridge.

This repo packages the local Pulse Labs prototype of a Hermes plugin named `whatsapp-plusplus` with a tool named `whatsapp_plusplus`.

## What it is

Hermes Agent can already send WhatsApp messages and returns WhatsApp `message_id` values. WhatsApp++ adds the missing follow-up controls that make Hermes more useful in real chats and group threads:

- edit a Hermes/bot-sent message
- delete/revoke a Hermes/bot-sent message for everyone, when WhatsApp allows it
- react to a message with an emoji
- clear a reaction
- star or unstar a message locally for the connected WhatsApp account

It is especially useful when Hermes is operating through WhatsApp groups and needs to correct, clean up, or acknowledge messages without adding more clutter.

## Who it is for

- Hermes Desktop users running the bundled WhatsApp/Baileys bridge
- teams using Hermes as a WhatsApp bot in group chats
- agencies and operators who want an assistant that can clean up its own messages after corrections
- developers experimenting with safer agent-side message controls

This is not a WhatsApp automation platform by itself. It is a small Hermes plugin plus bridge patch that exposes controls for an already-paired Hermes WhatsApp bridge.

## How it works

There are two pieces:

1. Hermes plugin
   - installs under `~/.hermes/plugins/whatsapp_plusplus/`
   - registers one tool: `whatsapp_plusplus`
   - sends local HTTP requests to the WhatsApp bridge, defaulting to `http://127.0.0.1:3000`

2. Baileys bridge endpoints
   - adds/uses `POST /edit`
   - adds `POST /delete`
   - adds `POST /react`
   - adds `POST /star`

The plugin does not talk to WhatsApp directly. Hermes calls the plugin, the plugin calls the local bridge, and the bridge uses Baileys to operate as the connected WhatsApp bot account.

## Actions exposed to Hermes

Tool: `whatsapp_plusplus`

Arguments:

- `action`: one of `edit`, `delete_for_everyone`, `react`, `unreact`, `star`, `unstar`
- `chat_id`: WhatsApp chat JID, for example `120363...@g.us`
- `message_id`: WhatsApp message key/id returned by Hermes or WhatsApp
- `message`: replacement text for `edit`
- `emoji`: emoji for `react`
- `from_me`: whether the message was sent by the connected bot account; defaults to true
- `participant`: optional participant JID for group messages, especially when `from_me=false`
- `safety_ack`: required exact value `USER_EXPLICITLY_REQUESTED_THIS` for `edit` and `delete_for_everyone`

## Safety model

WhatsApp++ deliberately makes edit/delete harder than react/star.

The plugin refuses to run `edit` or `delete_for_everyone` unless Hermes passes:

```text
safety_ack=USER_EXPLICITLY_REQUESTED_THIS
```

Hermes should only pass that value when the user explicitly asks to edit or delete that exact message in the current conversation.

### Safety & Security Disclaimer

This plugin gives an AI agent real control over visible WhatsApp history from the connected bot account. That is powerful, but it means a misconfigured, compromised, or poorly instructed agent could potentially:

- send something the user did not intend, then edit it after the fact
- delete a message to hide evidence of a mistake or unwanted action
- clean up context in a group thread in a way that changes what other people can see
- react to messages in ways that imply approval or agreement
- star sensitive messages on the bot account for later retrieval

The safety acknowledgement is a guardrail, not a cryptographic permission system. Any agent that has this tool in its available tool list and decides to pass the acknowledgement string can technically attempt the action. Treat this plugin like a moderation/admin tool: only enable it for agents and chats where you trust the model, prompt, runtime, and operators.

Recommended guardrails:

- keep edit/delete disabled or unavailable unless you actually need them
- require explicit user wording such as "edit that message" or "delete that for everyone"
- log every edit/delete action with `chat_id`, `message_id`, timestamp, and requesting user
- prefer corrected follow-up messages over editing history
- never allow autonomous/background jobs to edit or delete without human approval
- use a dedicated bot WhatsApp account, not a personal account
- test in a private chat before using in production groups

Important limits:

- delete-for-everyone can fail due to WhatsApp message age/type/permission limits
- deleting leaves a WhatsApp deleted-message placeholder
- edits change visible chat history and should not be used silently
- reactions are visible to the chat
- starring is local to the connected WhatsApp bot account
- the tool needs a real `chat_id` and `message_id`; do not guess



## Install

### One-line agent prompt: install this version

Paste this to Hermes:

```text
Install Pulse Labs WhatsApp++ for Hermes from https://gitlab.com/pulse-labs/whatsapp-plusplus-hermes as a pip/uv Hermes plugin into the same Python environment Hermes uses, run the package installer with --enable to patch the bundled WhatsApp bridge, restart only the WhatsApp bridge if needed, and verify with py_compile, node --check, hermes plugins list, and safe /delete /react /star endpoint checks.
```

### uv / pip plugin install

Install into the Python environment that runs Hermes. On Hermes Desktop for Windows, that is often:

```bash
HERMES_PY="C:/Users/you/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
```

Install from GitLab with uv:

```bash
uv pip install --python "$HERMES_PY" "git+https://gitlab.com/pulse-labs/whatsapp-plusplus-hermes.git"
```

Or with pip:

```bash
"$HERMES_PY" -m pip install "git+https://gitlab.com/pulse-labs/whatsapp-plusplus-hermes.git"
```

Patch the local WhatsApp bridge, write the tiny Hermes CLI visibility shim, and enable the plugin in Hermes config:

```bash
"$HERMES_PY" -m pulse_labs_whatsapp_plusplus_hermes.installer --enable
```

The plugin is registered as a pip entry point named `whatsapp-plusplus`. The installer also writes a small `~/.hermes/plugins/whatsapp-plusplus` shim so current `hermes plugins list/enable` commands can see it. If it finds the older copied `~/.hermes/plugins/whatsapp_plusplus` directory-plugin, it archives that directory under `~/.hermes/plugin_backups/` to avoid duplicate plugin entries; pass `--keep-legacy-dir` to keep it.

Then restart Hermes Gateway or restart only the WhatsApp bridge so the new bridge endpoints are live. Start a fresh Hermes session after enabling the plugin.

### Source checkout install

Clone the repo:

```bash
git clone https://gitlab.com/pulse-labs/whatsapp-plusplus-hermes.git
cd whatsapp-plusplus-hermes
```

Install/edit locally into Hermes' Python environment:

```bash
uv pip install --python "$HERMES_PY" -e .
"$HERMES_PY" -m pulse_labs_whatsapp_plusplus_hermes.installer --enable
```

### Custom Hermes home or bridge path

```bash
"$HERMES_PY" -m pulse_labs_whatsapp_plusplus_hermes.installer --hermes-home "C:/Users/you/AppData/Local/hermes" --bridge "C:/Users/you/AppData/Local/hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js" --enable
```

### Different bridge URL

The plugin defaults to `http://127.0.0.1:3000`. Override it with:

```bash
export WHATSAPP_PLUSPLUS_BRIDGE_URL=http://127.0.0.1:3000
```

## Rebuild from scratch

### One-line agent prompt: rebuild from scratch

Paste this to Hermes:

```text
Rebuild WhatsApp++ for Hermes from scratch: create a Hermes plugin exposing a whatsapp_plusplus tool with actions edit/delete_for_everyone/react/unreact/star/unstar, require safety_ack=USER_EXPLICITLY_REQUESTED_THIS for edit/delete, patch the local Baileys WhatsApp bridge with /delete, /react, and /star endpoints using Baileys message keys, and verify with py_compile, node --check, hermes plugins list, bridge health, and a disposable WhatsApp smoke test only after I explicitly approve edit/delete tests.
```

## Usage examples

Delete a bot-sent message for everyone:

```json
{
  "action": "delete_for_everyone",
  "chat_id": "120363000000000000@g.us",
  "message_id": "3EB0ABC123",
  "from_me": true,
  "safety_ack": "USER_EXPLICITLY_REQUESTED_THIS"
}
```

React to a message:

```json
{
  "action": "react",
  "chat_id": "120363000000000000@g.us",
  "message_id": "3EB0ABC123",
  "emoji": "✅",
  "from_me": true
}
```

Star a message locally:

```json
{
  "action": "star",
  "chat_id": "120363000000000000@g.us",
  "message_id": "3EB0ABC123",
  "from_me": true
}
```

## Verification checklist

After install:

```bash
"$HERMES_PY" -m py_compile -q src/pulse_labs_whatsapp_plusplus_hermes/*.py  # source checkout only
"$HERMES_PY" -m pulse_labs_whatsapp_plusplus_hermes.installer --help
node --check ~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js
hermes plugins list --plain --no-bundled | grep whatsapp-plusplus
```

Bridge endpoint checks should return HTTP 400 for missing required fields, not 404:

```bash
curl -i -X POST http://127.0.0.1:3000/delete -H 'Content-Type: application/json' -d '{}'
curl -i -X POST http://127.0.0.1:3000/react  -H 'Content-Type: application/json' -d '{}'
curl -i -X POST http://127.0.0.1:3000/star   -H 'Content-Type: application/json' -d '{}'
```

## Bridge endpoint details

`POST /delete`

```json
{ "chatId": "...", "messageId": "...", "fromMe": true, "participant": "optional" }
```

Calls Baileys:

```js
sock.sendMessage(chatId, { delete: key })
```

`POST /react`

```json
{ "chatId": "...", "messageId": "...", "emoji": "✅", "fromMe": true, "participant": "optional" }
```

Calls Baileys:

```js
sock.sendMessage(chatId, { react: { text: emoji || '', key } })
```

`POST /star`

```json
{ "chatId": "...", "messageId": "...", "star": true, "fromMe": true }
```

Calls Baileys:

```js
sock.chatModify({ star: { messages: [{ id: messageId, fromMe }], star } }, chatId)
```

## Repo layout

```text
src/pulse_labs_whatsapp_plusplus_hermes/  pip-installable Hermes plugin package + installer
plugin/whatsapp_plusplus/                  directory-plugin copy for manual installs/reference
scripts/install.py                         source-checkout wrapper around the package installer
pyproject.toml                             uv/pip package metadata and Hermes entry point
README.md                                  public docs
LICENSE                                    MIT license
```

## License

MIT License. See `LICENSE`.
