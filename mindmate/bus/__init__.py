"""消息总线模块."""

from .events import InboundMessage, MessageBus, OutboundMessage

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
