"""Handlers for the local WhatsApp++ plugin."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict


_REQUIRED_ACK = "USER_EXPLICITLY_REQUESTED_THIS"


def _bridge_base_url() -> str:
    return os.getenv("WHATSAPP_PLUSPLUS_BRIDGE_URL", "http://127.0.0.1:3000").rstrip("/")


def _post(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{_bridge_base_url()}{endpoint}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            if not text:
                return {"success": True}
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"success": True, "raw": text}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {"error": text or exc.reason}
        data.setdefault("success", False)
        data.setdefault("status", exc.code)
        return data
    except Exception as exc:  # noqa: BLE001 - tool handlers must not raise
        return {"success": False, "error": str(exc)}


def _base_payload(args: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "chatId": str(args.get("chat_id") or "").strip(),
        "messageId": str(args.get("message_id") or "").strip(),
    }
    if "from_me" in args and args.get("from_me") is not None:
        payload["fromMe"] = bool(args.get("from_me"))
    if args.get("participant"):
        payload["participant"] = str(args["participant"]).strip()
    return payload


def whatsapp_plusplus(args: Dict[str, Any], **kwargs: Any) -> str:
    """Perform advanced WhatsApp message controls via the local bridge."""
    action = str(args.get("action") or "").strip()
    chat_id = str(args.get("chat_id") or "").strip()
    message_id = str(args.get("message_id") or "").strip()

    if not action or not chat_id or not message_id:
        return json.dumps({
            "success": False,
            "error": "action, chat_id, and message_id are required",
        })

    if action in {"edit", "delete_for_everyone"} and args.get("safety_ack") != _REQUIRED_ACK:
        return json.dumps({
            "success": False,
            "error": (
                "Refusing to edit/delete without explicit current-user request. "
                f"Pass safety_ack={_REQUIRED_ACK!r} only when the user asked for this exact operation."
            ),
        })

    payload = _base_payload(args)

    if action == "edit":
        message = str(args.get("message") or "")
        if not message.strip():
            return json.dumps({"success": False, "error": "message is required for edit"})
        payload["message"] = message
        result = _post("/edit", payload)
    elif action == "delete_for_everyone":
        result = _post("/delete", payload)
    elif action == "react":
        emoji = str(args.get("emoji") or "").strip()
        if not emoji:
            return json.dumps({"success": False, "error": "emoji is required for react"})
        payload["emoji"] = emoji
        result = _post("/react", payload)
    elif action == "unreact":
        payload["emoji"] = ""
        result = _post("/react", payload)
    elif action == "star":
        payload["star"] = True
        result = _post("/star", payload)
    elif action == "unstar":
        payload["star"] = False
        result = _post("/star", payload)
    else:
        return json.dumps({"success": False, "error": f"Unsupported action: {action}"})

    result.setdefault("success", bool(result.get("success")))
    result.setdefault("action", action)
    result.setdefault("chat_id", chat_id)
    result.setdefault("message_id", message_id)
    return json.dumps(result, ensure_ascii=False)
