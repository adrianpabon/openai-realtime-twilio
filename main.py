from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
from openai import OpenAI
import asyncio
import websockets
import json
import httpx

load_dotenv()

app = FastAPI()

# Configuración
PORT = int(os.getenv("PORT", 5001))
WEBHOOK_SECRET = os.getenv("OPENAI_WEBHOOK_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not WEBHOOK_SECRET or not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_WEBHOOK_SECRET or OPENAI_API_KEY")

# Cliente OpenAI
client = OpenAI(
    api_key=OPENAI_API_KEY,
    webhook_secret=WEBHOOK_SECRET
)

# Configuración de la llamada
call_accept = {
    "instructions": "You are a support agent. Speak in English unless asked otherwise.",
    "type": "realtime",
    "model": "gpt-realtime",
    "audio": {
        "output": {"voice": "alloy"}
    }
}

WELCOME_GREETING = "Thank you for calling, how can I help you?"

response_create = {
    "type": "response.create",
    "response": {
        "instructions": f"Say to the user: {WELCOME_GREETING}"
    }
}

REALTIME_INCOMING_CALL = "realtime.call.incoming"


# Tarea WebSocket
async def websocket_task(uri: str) -> None:
    """Conecta al WebSocket de OpenAI Realtime API"""
    try:
        async with websockets.connect(
            uri,
            extra_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "origin": "https://api.openai.com"
            }
        ) as ws:
            print(f"WS OPEN: {uri}")
            
            # Enviar el saludo inicial
            await ws.send(json.dumps(response_create))
            
            # Escuchar mensajes
            async for message in ws:
                text = message if isinstance(message, str) else message.decode()
                print(f"Received from WebSocket: {text}")
                
    except Exception as e:
        print(f"WebSocket error: {e}")


async def connect_with_delay(sip_wss_url: str, delay: int = 0) -> None:
    """Conecta al WebSocket con un delay opcional"""
    try:
        await asyncio.sleep(delay)
        await websocket_task(sip_wss_url)
    except Exception as e:
        print(f"Error connecting web socket: {e}")


# Endpoint principal para webhooks
@app.post("/")
async def webhook(request: Request):
    """Maneja los webhooks de OpenAI"""
    try:
        # Leer el body raw
        body = await request.body()
        headers = dict(request.headers)
        
        # Verificar y decodificar el webhook
        event = client.webhooks.unwrap(
            body.decode("utf-8"),
            headers,
        )
        
        event_type = getattr(event, "type", None)
        
        # Manejar llamada entrante
        if event_type == REALTIME_INCOMING_CALL:
            call_id = getattr(getattr(event, "data", None), "call_id", None)
            
            if not call_id:
                raise HTTPException(status_code=400, detail="Missing call_id")
            
            print(f"Incoming call: {call_id}")
            
            # Aceptar la llamada
            async with httpx.AsyncClient() as http_client:
                accept_url = f"https://api.openai.com/v1/realtime/calls/{call_id}/accept"
                
                resp = await http_client.post(
                    accept_url,
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=call_accept
                )
                
                if not resp.is_success:
                    error_text = resp.text
                    print(f"ACCEPT failed: {resp.status_code} {error_text}")
                    raise HTTPException(status_code=500, detail="Accept failed")
            
            # Conectar WebSocket después de un pequeño delay
            wss_url = f"wss://api.openai.com/v1/realtime?call_id={call_id}"
            asyncio.create_task(connect_with_delay(wss_url, 0))
            
            # Responder al webhook
            return Response(
                status_code=200,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
            )
        
        # Otros tipos de eventos
        return Response(status_code=200)
        
    except Exception as e:
        error_msg = str(getattr(e, "message", str(e)))
        
        # Verificar si es error de firma inválida
        if "InvalidWebhookSignatureError" in str(type(e).__name__) or \
           "invalid" in error_msg.lower():
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid signature"}
            )
        
        print(f"Server error: {error_msg}")
        return JSONResponse(
            status_code=500,
            content={"error": "Server error"}
        )


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    print(f"Listening on http://localhost:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
    #run: uvicorn main:app --reload --host 0.0.0.0 --port 8000