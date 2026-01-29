from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pentest_utils.web.websockets import WSConnectionManager, ProxyWebSocket

router = APIRouter()

@router.websocket("/connect-ws/")
async def websocket_connect(websocket: WebSocket):
  
  conn = WSConnectionManager()
  await conn.ws_connect("emacs-proxy", 'emacs-conn', websocket)

  try:
    update_ws_obj: "ProxyWebSocket" = conn.get_ws()
    
    while True:
      data = await websocket.receive_json()
      update_ws_obj.put_data(data)
      
  except WebSocketDisconnect:
    print("------------------------")
    print("The freaking socket disconnected")
    print("------------------------")
