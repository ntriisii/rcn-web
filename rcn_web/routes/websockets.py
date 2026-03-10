from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pentest_utils.web.websockets import WSConnectionManager, ProxyWebSocket
from rcn_core.core_ws import create_agent_websocket_router

router = APIRouter()

# Include the core agent websocket router
agent_ws_router = create_agent_websocket_router(prefix="/ws", tags=["agent-websocket"])
router.include_router(agent_ws_router)


@router.websocket("/connect-ws/")
@router.websocket("/{target_name}/connect-ws/")
async def websocket_connect(websocket: WebSocket, target_name: Optional[str] = None):
    # If target_name is provided in the URL, use it to distinguish connections
    conn_id = f"emacs-conn-{target_name}" if target_name else "emacs-conn"

    conn = WSConnectionManager()
    await conn.ws_connect("emacs-proxy", conn_id, websocket)

    try:
        update_ws_obj: "ProxyWebSocket" = conn.get_ws()

        while True:
            data = await websocket.receive_json()
            update_ws_obj.put_data(data)

    except WebSocketDisconnect:
        print("------------------------")
        print("The freaking socket disconnected")
        print("------------------------")
