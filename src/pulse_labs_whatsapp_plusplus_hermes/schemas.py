"""Tool schema for the local WhatsApp++ plugin."""

WHATSAPP_PLUSPLUS = {
    "name": "whatsapp_plusplus",
    "description": (
        "Perform advanced WhatsApp message controls through the local Hermes WhatsApp bridge: "
        "edit a Hermes/bot-sent message, delete/revoke a message for everyone, react/unreact, "
        "and star/unstar messages. Use edit and delete_for_everyone ONLY when the user explicitly "
        "asks for that exact operation in the current conversation. Requires the target WhatsApp chat_id "
        "and message_id returned by WhatsApp/Hermes. For group messages not sent by the bot, set from_me=false "
        "and include participant when known."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["edit", "delete_for_everyone", "react", "unreact", "star", "unstar"],
                "description": "The WhatsApp control action to perform.",
            },
            "chat_id": {
                "type": "string",
                "description": "WhatsApp chat JID, e.g. 120363...@g.us for a group or ...@s.whatsapp.net for a DM.",
            },
            "message_id": {
                "type": "string",
                "description": "WhatsApp message ID/key id to operate on, e.g. the message_id returned by send_message.",
            },
            "message": {
                "type": "string",
                "description": "Replacement text for action=edit. Ignored for other actions.",
            },
            "emoji": {
                "type": "string",
                "description": "Emoji reaction for action=react. Use action=unreact to clear reaction.",
            },
            "from_me": {
                "type": "boolean",
                "description": "Whether the target message was sent by the Hermes/bot WhatsApp account. Defaults to true.",
            },
            "participant": {
                "type": "string",
                "description": "Optional participant JID for group messages, especially when from_me=false.",
            },
            "safety_ack": {
                "type": "string",
                "description": (
                    "Required exact value USER_EXPLICITLY_REQUESTED_THIS for edit and delete_for_everyone. "
                    "Do not provide it unless the user explicitly asked to edit/delete that message."
                ),
            },
        },
        "required": ["action", "chat_id", "message_id"],
    },
}
