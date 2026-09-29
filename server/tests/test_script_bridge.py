import asyncio

from api.script_bridge import ScriptBridge


def test_revocation_tolerates_handler_already_closing():
    async def check():
        closing, release = asyncio.Event(), asyncio.Event()

        async def endpoint(ws):
            await ws.accept()
            await ws.close()

        bridge = ScriptBridge()
        bridge.bind("a", "fixture", "raw", endpoint)
        scope = {
            "type": "websocket",
            "path": "/raw/attempts/a",
            "root_path": "",
            "headers": [(b"authorization", b"Bearer fixture")],
            "query_string": b"",
        }

        async def receive():
            return {"type": "websocket.connect"}

        async def send(message):
            if message["type"] == "websocket.close":
                closing.set()
                await release.wait()

        task = asyncio.create_task(bridge.app(scope, receive, send))
        try:
            await asyncio.wait_for(closing.wait(), 1)
            await bridge.revoke()
            assert bridge.access is None
        finally:
            release.set()
            await task
        assert not bridge.connections

    asyncio.run(check())
