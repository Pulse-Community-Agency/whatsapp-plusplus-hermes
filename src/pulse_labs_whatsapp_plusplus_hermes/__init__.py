"""Pulse Labs WhatsApp++ Hermes plugin entry point."""

from . import schemas, tools


def register(ctx):
    ctx.register_tool(
        name="whatsapp_plusplus",
        toolset="messaging",
        schema=schemas.WHATSAPP_PLUSPLUS,
        handler=tools.whatsapp_plusplus,
    )
