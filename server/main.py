from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
from server.logger import guardar_evento

app = FastAPI() #Crea la instacia de la aplicación para uvicorn

@app.websocket("/ws/events") # Cuando los agentes se conecten a esta ruta, se ejecutará esta función 
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Agente conectado: " + websocket.client.host) # Imprime la IP del agente que se ha conectado
    try:
        while True:
            data = await websocket.receive_text()
            evento = json.loads(data)

            guardar_evento(evento)

    except WebSocketDisconnect:
        print("Agente desconectado: " + websocket.client.host)