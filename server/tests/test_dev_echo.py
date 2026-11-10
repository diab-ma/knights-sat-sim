from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

def test_dev_echo():
    with client.websocket_connect("/api/dev/echo") as ws:
        ws.send_text("hello")
        data = ws.receive_bytes()
        assert data == b"hello"