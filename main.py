from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from realtime_config import call_accept, response_create
import os
from dotenv import load_dotenv
from openai import OpenAI
import asyncio
import websockets
import json
import httpx
from function_manager import FunctionManager


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



REALTIME_INCOMING_CALL = "realtime.call.incoming"


# Manejadores de eventos WebSocket
async def handle_websocket_message(message_data: dict, ws, function_manager: FunctionManager ) -> None:
    """Maneja diferentes tipos de mensajes del WebSocket"""
    message_type = message_data.get("type", "")
    
    
    # Manejo específico por tipo de mensaje
    if message_type == "session.created":
        print("✅ Session created successfully")
        
    elif message_type == "response.created":
        print("🎯 Response created")
        
    elif message_type == "response.done":
        print("✅ Response completed")

        output_items = message_data.get("response", {}).get("output", [])
        has_function_calls = False

        if output_items:
            for item in output_items:
                if item.get("type") == "function_call":
                    has_function_calls = True
                    function_name = item.get("name")
                    call_id = item.get("call_id")
                    arguments = item.get("arguments", "{}")

                    print(f"🔧 Function call detected: {function_name}")
                    print(f"📋 Arguments: {arguments}")

                    try:
                        # Ejecutar la función
                        result = await function_manager.execute_function(function_name, arguments)
                        print(f"✅ Function result: {result}")

                        # Enviar el resultado de vuelta al modelo
                        function_output_event = {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps(result)
                            }
                        }

                        await ws.send(json.dumps(function_output_event))
                        print(f"📤 Sent function output for call_id: {call_id}")

                    except Exception as e:
                        print(f"❌ Error executing function {function_name}: {e}")

                        # Enviar error al modelo
                        error_output = {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({"error": str(e)})
                            }
                        }
                        await ws.send(json.dumps(error_output))

            # Solicitar respuesta una sola vez después de procesar todas las funciones
            if has_function_calls:
                await ws.send(json.dumps({"type": "response.create"}))
                print("📤 Sent response.create after all function outputs")

    elif message_type == "conversation.item.created":
        print("💬 Conversation item created")
        
    elif message_type == "input_audio_buffer.speech_started":
        print("🎤 User started speaking")
        
    elif message_type == "input_audio_buffer.speech_stopped":
        print("🔇 User stopped speaking")
        
    elif message_type == "response.audio.delta":
        # Audio chunks del asistente
        print("🔊 Receiving audio chunk")
        
    elif message_type == "response.audio_transcript.delta":
        # Transcripción del audio del asistente
        transcript = message_data.get("delta", "")
        if transcript:
            print(f"🗣️ Assistant: {transcript}")
            
    elif message_type == "conversation.item.input_audio_transcription.completed":
        # Transcripción completada del usuario
        transcript = message_data.get("transcript", "")
        print(f"👤 User said: {transcript}")

    elif message_type == "response.function_call_arguments.delta":
        pass

    elif message_type == "response.function_call_arguments.done":
        print("✅ Function call arguments completed")


        
    elif message_type == "error":
        error = message_data.get("error", {})
        print(f"❌ WebSocket error: {error}")
        
    else:
        print(f"📨 Unhandled message type: {message_type}")

# Tarea WebSocket mejorada
async def websocket_task(uri: str) -> None:
    """Conecta al WebSocket de OpenAI Realtime API con manejo de eventos mejorado"""
    try:
        function_manager = FunctionManager()
        async with websockets.connect(
            uri,
            additional_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "origin": "https://api.openai.com"
            }
        ) as ws:
            print(f"🔌 WS OPEN: {uri}")
            
            # Enviar el saludo inicial
            await ws.send(json.dumps(response_create))
            print("📤 Sent initial greeting command")
            
            # Escuchar mensajes
            async for message in ws:
                try:
                    text = message if isinstance(message, str) else message.decode()
                    message_data = json.loads(text)
                    
                    # Manejo específico de eventos
                    await handle_websocket_message(message_data, ws, function_manager)
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️ Failed to parse JSON message: {text}")
                except Exception as e:
                    print(f"⚠️ Error handling message: {e}")
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"🔌 WebSocket connection closed: {e.code} - {e.reason}")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")


async def connect_with_delay(sip_wss_url: str, delay: int = 0) -> None:
    """Conecta al WebSocket con un delay opcional"""
    try:
        await asyncio.sleep(delay)
        await websocket_task(sip_wss_url)
    except Exception as e:
        print(f"Error connecting web socket: {e}")


# Endpoint principal para webhooks
@app.post("/webhook")
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

            print(f"webhook received: {event_type}")
            
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
        
        # # Otros tipos de eventos
        return Response(status_code=200)
        
    except Exception as e:
        error_msg = str(getattr(e, "message", str(e)))
        print(f"Error processing webhook: {error_msg}")
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
    #run: uvicorn main:app --reload --host 0.0.0.0 --port 5001