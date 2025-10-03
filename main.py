from fastapi import FastAPI, Request, Response, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from realtime_config import choose_random_assistant, response_create
import os
from dotenv import load_dotenv
from openai import OpenAI
import asyncio
import websockets
import json
import httpx
import threading
from function_manager import FunctionManager
from typing import Dict


load_dotenv()

app = FastAPI()

# Montar carpeta de archivos estáticos
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuración
PORT = int(os.getenv("PORT", 5001))
WEBHOOK_SECRET = os.getenv("OPENAI_WEBHOOK_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY - Required for both Demo Web and Twilio")

# Cliente OpenAI (solo si hay webhook secret configurado)
client = None
if WEBHOOK_SECRET:
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        webhook_secret=WEBHOOK_SECRET
    )
    print("✅ Webhook validation enabled (Twilio mode)")
else:
    print("⚠️  Webhook secret not configured - Demo Web only (Twilio webhooks disabled)")



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
async def websocket_task_async(call_id: str) -> None:
    """Conecta al WebSocket de OpenAI Realtime API"""
    uri = f"wss://api.openai.com/v1/realtime?call_id={call_id}"
    
    try:
        function_manager = FunctionManager()
        
        async with websockets.connect(
            uri,
            additional_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as ws:
            print(f"🔌 WS OPEN: {uri}")
            
            await ws.send(json.dumps(response_create))
            print("📤 Sent initial greeting command")
            
            async for message in ws:
                try:
                    text = message if isinstance(message, str) else message.decode()
                    message_data = json.loads(text)
                    
                    await handle_websocket_message(message_data, ws, function_manager)
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️ Failed to parse JSON message: {text}")
                except Exception as e:
                    print(f"⚠️ Error handling message: {e}")
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"🔌 WebSocket connection closed: {e.code} - {e.reason}")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")



# Endpoint principal para webhooks
@app.post("/webhook")
async def webhook(request: Request):
    """Maneja los webhooks de OpenAI"""
    
    # Verificar que el webhook secret está configurado
    if not WEBHOOK_SECRET or not client:
        return JSONResponse(
            status_code=503,
            content={
                "error": "Webhook endpoint not available",
                "message": "OPENAI_WEBHOOK_SECRET not configured. This endpoint is only for Twilio integration."
            }
        )
    
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

            sip_headers = getattr(getattr(event, "data", None), "sip_headers", None)

            print(f"sip_headers: {sip_headers}")

            print(f"webhook received: {event_type}")
            
            if not call_id:
                raise HTTPException(status_code=400, detail="Missing call_id")
            
            print(f"Incoming call: {call_id}")
            
            # Aceptar la llamada
            async with httpx.AsyncClient() as http_client:
                call_accept = choose_random_assistant()
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
            threading.Thread(
                target=lambda: asyncio.run(websocket_task_async(call_id)),
                daemon=True,
                name=f"ws_thread_{call_id}"
            ).start()
            
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


@app.get("/", response_class=HTMLResponse)
async def root():
    """Sirve la página principal del demo"""
    static_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    
    if not os.path.exists(static_path):
        return HTMLResponse(
            content="<h1>Error: index.html no encontrado</h1><p>Asegúrate de que existe la carpeta 'static' con el archivo 'index.html'</p>",
            status_code=404
        )
    
    # Leer y servir el HTML
    with open(static_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    return HTMLResponse(content=html_content)


@app.get("/api/config")
async def get_config():
    """Endpoint para obtener configuración del cliente (sin exponer secrets sensibles)"""
    return {
        "has_api_key": bool(OPENAI_API_KEY),
        "has_webhook_secret": bool(WEBHOOK_SECRET),
        "port": PORT,
        "modes": {
            "demo_web": bool(OPENAI_API_KEY),
            "twilio_webhooks": bool(WEBHOOK_SECRET and OPENAI_API_KEY)
        }
    }


@app.post("/api/session")
async def create_session():
    """
    Crea una sesión ephemeral de OpenAI Realtime API para WebRTC
    Esto permite que el cliente se conecte directamente con OpenAI de forma segura
    """
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    
    try:
        # Obtener configuración del asistente
        assistant_config = choose_random_assistant()
        
        # Crear sesión ephemeral con OpenAI
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                "https://api.openai.com/v1/realtime/sessions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-realtime-2025-08-28",
                    "voice": assistant_config["audio"]["output"]["voice"],
                    "instructions": assistant_config["instructions"],
                    "modalities": ["text", "audio"],
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 700
                    },
                    "temperature": 0.9,
                    "max_response_output_tokens": 4096,
                    "tools": assistant_config["tools"]
                }
            )
            
            if response.status_code != 200:
                error_text = response.text
                print(f"❌ Error creando sesión: {response.status_code} {error_text}")
                raise HTTPException(status_code=500, detail=f"Failed to create session: {error_text}")
            
            session_data = response.json()
            print(f"✅ Sesión ephemeral creada para WebRTC con voz {assistant_config['audio']['output']['voice']}")
            
            return session_data
            
    except Exception as e:
        print(f"❌ Error en /api/session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/realtime")
async def websocket_proxy(websocket: WebSocket):
    """
    WebSocket proxy que conecta el navegador con OpenAI Realtime API
    Maneja la autenticación de forma segura en el servidor
    """
    await websocket.accept()
    print("🔌 Cliente conectado al WebSocket proxy")
    
    openai_ws = None
    
    try:
        # Conectar a OpenAI Realtime API
        uri = "wss://api.openai.com/v1/realtime?model=gpt-realtime-2025-08-28"
        
        async with websockets.connect(
            uri,
            extra_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            print("✅ Conectado a OpenAI Realtime API")
            
            # Obtener configuración completa del asistente
            assistant_config = choose_random_assistant()
            print(f"👤 Asistente seleccionado: {assistant_config.get('type', 'realtime')} con voz {assistant_config['audio']['output']['voice']}")
            
            # Enviar configuración inicial con toda la personalidad
            session_config = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],  # OpenAI requiere ambos
                    "instructions": assistant_config["instructions"],  # Prompt completo con personalidad
                    "voice": assistant_config["audio"]["output"]["voice"],  # Voz aleatoria (ash o shimmer)
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 700
                    },
                    "temperature": 0.9,
                    "max_response_output_tokens": 4096,
                    "tools": assistant_config["tools"]  # Funciones disponibles
                }
            }
            await openai_ws.send(json.dumps(session_config))
            print("📤 Configuración de sesión enviada")
            
            # Inicializar el manejador de funciones
            function_manager = FunctionManager()
            
            # Crear tareas para manejar mensajes en ambas direcciones
            async def forward_to_openai():
                """Reenvía mensajes del cliente al servidor OpenAI"""
                try:
                    while True:
                        data = await websocket.receive_text()
                        await openai_ws.send(data)
                except WebSocketDisconnect:
                    print("🔌 Cliente desconectado")
                except Exception as e:
                    print(f"❌ Error reenviando a OpenAI: {e}")
            
            async def forward_to_client():
                """Reenvía mensajes de OpenAI al cliente y ejecuta funciones"""
                try:
                    async for message in openai_ws:
                        # Parsear mensaje para detectar llamadas a funciones
                        try:
                            message_data = json.loads(message)
                            
                            # Detectar y ejecutar function calls
                            if message_data.get("type") == "response.done":
                                output_items = message_data.get("response", {}).get("output", [])
                                
                                for item in output_items:
                                    if item.get("type") == "function_call":
                                        function_name = item.get("name")
                                        call_id = item.get("call_id")
                                        arguments = item.get("arguments", "{}")
                                        
                                        print(f"🔧 Ejecutando función: {function_name}")
                                        
                                        try:
                                            # Ejecutar la función
                                            result = await function_manager.execute_function(function_name, arguments)
                                            print(f"✅ Resultado: {result}")
                                            
                                            # Enviar resultado a OpenAI
                                            function_output = {
                                                "type": "conversation.item.create",
                                                "item": {
                                                    "type": "function_call_output",
                                                    "call_id": call_id,
                                                    "output": json.dumps(result)
                                                }
                                            }
                                            await openai_ws.send(json.dumps(function_output))
                                            
                                            # Solicitar nueva respuesta
                                            await openai_ws.send(json.dumps({"type": "response.create"}))
                                            
                                        except Exception as e:
                                            print(f"❌ Error ejecutando función {function_name}: {e}")
                        except:
                            pass  # No es JSON o no necesita procesamiento especial
                        
                        # Reenviar mensaje al cliente
                        await websocket.send_text(message)
                        
                except websockets.exceptions.ConnectionClosed:
                    print("🔌 OpenAI desconectado")
                except Exception as e:
                    print(f"❌ Error reenviando a cliente: {e}")
            
            # Ejecutar ambas tareas simultáneamente
            await asyncio.gather(
                forward_to_openai(),
                forward_to_client()
            )
            
    except websockets.exceptions.InvalidStatusCode as e:
        error_msg = f"Error de autenticación con OpenAI: {e}"
        print(f"❌ {error_msg}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "error": {"message": error_msg}
        }))
    except Exception as e:
        error_msg = f"Error en WebSocket proxy: {str(e)}"
        print(f"❌ {error_msg}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": {"message": error_msg}
            }))
        except:
            pass
    finally:
        print("🔌 WebSocket proxy cerrado")


if __name__ == "__main__":
    import uvicorn
    print(f"Listening on http://localhost:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
    #run: uvicorn main:app --reload --host 0.0.0.0 --port 5001