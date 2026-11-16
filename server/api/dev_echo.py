from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# REMOVE LATER! This route will be deleted when the real terminal route exists
@router.websocket("/api/dev/echo")
async def dev_echo(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            await websocket.send_bytes(text.encode("utf-8"))
    except WebSocketDisconnect:
        pass