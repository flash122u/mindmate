"""测试 Web 接口 — 端到端通信."""

import sys
sys.path.insert(0, '..')

import asyncio
from mindmate.bus.events import MessageBus, InboundMessage
from mindmate.web.app import create_app


class TestWebApp:
    def test_create_app(self):
        """验证 FastAPI 应用可创建."""
        bus = MessageBus()
        app = create_app(bus)
        assert app.title == "MindMate"

    def test_push_to_clients_hook(self):
        """验证 push_to_clients 挂载到 bus 上."""
        bus = MessageBus()
        app = create_app(bus)
        assert hasattr(bus, "push_to_clients")

    def test_inbound_outbound_flow(self):
        """验证消息总线进出流程."""
        bus = MessageBus()

        async def test():
            # 发布入站消息
            await bus.publish_inbound(
                InboundMessage("web", "user", "default", "hello")
            )
            # 消费
            msg = await bus.consume_inbound()
            assert msg.content == "hello"

            # 发布出站
            from mindmate.bus.events import OutboundMessage
            await bus.publish_outbound(
                OutboundMessage("web", "default", "hi there")
            )
            resp = await bus.consume_outbound()
            assert resp.content == "hi there"

        asyncio.run(test())

    def test_main_outbound_consumer(self):
        """验证 outbound consumer 可运行."""
        bus = MessageBus()
        push_called = False

        async def mock_push(content, metadata=None):
            nonlocal push_called
            push_called = True

        bus.push_to_clients = mock_push

        async def test():
            # 启动 consumer 后台任务
            async def consumer():
                msg = await bus.consume_outbound()
                await bus.push_to_clients(msg.content, msg.metadata)

            task = asyncio.create_task(consumer())
            await asyncio.sleep(0.05)
            from mindmate.bus.events import OutboundMessage
            await bus.publish_outbound(
                OutboundMessage("web", "default", "test")
            )
            await asyncio.wait_for(task, timeout=1.0)
            assert push_called

        asyncio.run(test())
