from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
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
from database import obtener_cita_por_id, listar_todas_citas
from call_recorder import call_recorder


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

    # 🔴 GRABACIÓN: Procesar audio y conversación
    await call_recorder.process_audio_chunk(message_data)
    await call_recorder.log_conversation(message_data)

    # DEBUG: Log todos los tipos de mensajes relacionados con audio
    if "audio" in message_type:
        print(f"🎵 DEBUG Audio Event: {message_type}")
    
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
        audio_data = message_data.get("delta", "")
        print(f"🔊 Receiving audio chunk - Size: {len(audio_data) if audio_data else 0} bytes")
        
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
        
        # 🔴 INICIAR GRABACIÓN
        call_recorder.start_recording(call_id)
        
        async with websockets.connect(
            uri,
            additional_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "origin": "https://api.openai.com"
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
    finally:
        # 🔴 GUARDAR GRABACIÓN AL FINALIZAR
        try:
            recording_result = await call_recorder.save_recording()
            print(f"💾 Grabación guardada: {recording_result}")
        except Exception as e:
            print(f"⚠️ Error guardando grabación: {e}")



# Endpoint principal para webhooks
@app.post("/webhook/call")
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


@app.get("/debug/files")
async def debug_files():
    """Debug endpoint para verificar archivos"""
    current_dir = os.path.dirname(__file__)
    html_path = os.path.join(current_dir, "recordings_viewer.html")
    
    return {
        "current_directory": current_dir,
        "html_path": html_path,
        "html_exists": os.path.exists(html_path),
        "files_in_directory": os.listdir(current_dir) if os.path.exists(current_dir) else "No existe"
    }


@app.get("/recordings-viewer")
async def recordings_viewer():
    """Sirve la interfaz web para ver grabaciones"""
    try:
        html_path = os.path.join(os.path.dirname(__file__), "recordings_viewer.html")
        if os.path.exists(html_path):
            return FileResponse(html_path)
        else:
            return HTMLResponse("<h1>Error: recordings_viewer.html no encontrado</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(f"<h1>Error: {str(e)}</h1>", status_code=500)


@app.get("/viewer")
async def viewer_alternative():
    """Endpoint alternativo para la interfaz web"""
    try:
        html_path = os.path.join(os.path.dirname(__file__), "recordings_viewer.html")
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: Archivo recordings_viewer.html no encontrado</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(f"<h1>Error: {str(e)}</h1>", status_code=500)


@app.get("/recordings")
async def list_recordings():
    """Lista todas las grabaciones disponibles"""
    try:
        recordings = call_recorder.get_recordings_list()
        return {
            "status": "success",
            "total_recordings": len(recordings),
            "recordings": recordings
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/recordings/{recording_id}/conversation")
async def get_recording_conversation(recording_id: str):
    """Obtiene la conversación de una grabación específica"""
    try:
        conversation_file = f"recordings/{recording_id}_conversation.json"
        
        if not os.path.exists(conversation_file):
            return {
                "status": "error",
                "message": "Grabación no encontrada"
            }
        
        with open(conversation_file, 'r', encoding='utf-8') as f:
            conversation_data = json.load(f)
        
        return {
            "status": "success",
            "conversation": conversation_data
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/recordings/{recording_id}/summary")
async def get_recording_summary(recording_id: str):
    """Obtiene el resumen de una grabación específica"""
    try:
        summary_file = f"recordings/{recording_id}_summary.txt"
        
        if not os.path.exists(summary_file):
            return {
                "status": "error",
                "message": "Resumen no encontrado"
            }
        
        with open(summary_file, 'r', encoding='utf-8') as f:
            summary_content = f.read()
        
        return {
            "status": "success",
            "summary": summary_content
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/recordings/{recording_id}/audio")
async def get_recording_audio(recording_id: str):
    """Sirve el archivo de audio WAV de una grabación específica"""
    try:
        audio_file = f"recordings/{recording_id}_audio.wav"

        if not os.path.exists(audio_file):
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "message": "Audio no encontrado"
                }
            )

        return FileResponse(
            audio_file,
            media_type="audio/wav",
            filename=f"{recording_id}_audio.wav"
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e)
            }
        )


@app.delete("/recordings/{recording_id}")
async def delete_recording(recording_id: str):
    """Elimina una grabación específica"""
    try:
        files_to_delete = [
            f"recordings/{recording_id}_conversation.json",
            f"recordings/{recording_id}_summary.txt",
            f"recordings/{recording_id}_audio.wav"
        ]

        deleted_files = []

        for file_path in files_to_delete:
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_files.append(os.path.basename(file_path))

        if deleted_files:
            return {
                "status": "success",
                "message": f"Grabación eliminada: {recording_id}",
                "deleted_files": deleted_files
            }
        else:
            return {
                "status": "error",
                "message": "No se encontraron archivos para eliminar"
            }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/citas/{cita_id}", response_class=HTMLResponse)
async def ver_cita(cita_id: int):
    """Endpoint público para ver una cita específica"""
    cita = obtener_cita_por_id(cita_id)

    if not cita:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Cita no encontrada</title>
                <style>
                    body { font-family: Arial, sans-serif; padding: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
                    .container { background: white; padding: 40px; border-radius: 10px; max-width: 600px; margin: 0 auto; box-shadow: 0 10px 40px rgba(0,0,0,0.2); }
                    h1 { color: #e74c3c; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>❌ Cita no encontrada</h1>
                    <p>No se encontró una cita con el ID proporcionado.</p>
                </div>
            </body>
            </html>
            """,
            status_code=404
        )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Confirmación de Cita - ID {cita['id']}</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}

            .card {{
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 600px;
                width: 100%;
                overflow: hidden;
                animation: slideIn 0.5s ease-out;
            }}

            @keyframes slideIn {{
                from {{
                    opacity: 0;
                    transform: translateY(-20px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}

            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}

            .header h1 {{
                font-size: 28px;
                margin-bottom: 10px;
            }}

            .checkmark {{
                font-size: 60px;
                animation: bounce 1s ease;
            }}

            @keyframes bounce {{
                0%, 20%, 50%, 80%, 100% {{ transform: translateY(0); }}
                40% {{ transform: translateY(-20px); }}
                60% {{ transform: translateY(-10px); }}
            }}

            .content {{
                padding: 40px;
            }}

            .info-section {{
                margin-bottom: 25px;
            }}

            .info-section h2 {{
                color: #667eea;
                font-size: 18px;
                margin-bottom: 15px;
                border-bottom: 2px solid #667eea;
                padding-bottom: 8px;
            }}

            .info-row {{
                display: flex;
                justify-content: space-between;
                padding: 12px 0;
                border-bottom: 1px solid #f0f0f0;
            }}

            .info-row:last-child {{
                border-bottom: none;
            }}

            .label {{
                font-weight: 600;
                color: #555;
            }}

            .value {{
                color: #333;
                text-align: right;
            }}

            .cita-id {{
                background: #667eea;
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                display: inline-block;
                font-weight: bold;
                margin-bottom: 20px;
            }}

            .alert {{
                background: #e3f2fd;
                border-left: 4px solid #2196F3;
                padding: 15px;
                margin-top: 25px;
                border-radius: 5px;
            }}

            .alert h3 {{
                color: #1976D2;
                margin-bottom: 8px;
                font-size: 16px;
            }}

            .alert p {{
                color: #555;
                line-height: 1.6;
            }}

            .footer {{
                background: #f8f9fa;
                padding: 20px;
                text-align: center;
                color: #777;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <div class="checkmark">✅</div>
                <h1>Cita Confirmada</h1>
                <p>Tu cita ha sido agendada exitosamente</p>
            </div>

            <div class="content">
                <div class="cita-id">ID de Cita: #{cita['id']}</div>

                <div class="info-section">
                    <h2>📋 Información del Paciente</h2>
                    <div class="info-row">
                        <span class="label">Nombre:</span>
                        <span class="value">{cita['paciente']['nombre']} {cita['paciente']['apellido']}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Identificación:</span>
                        <span class="value">{cita['paciente']['identificacion']}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Correo:</span>
                        <span class="value">{cita['paciente']['correo']}</span>
                    </div>
                </div>

                <div class="info-section">
                    <h2>📅 Detalles de la Cita</h2>
                    <div class="info-row">
                        <span class="label">Fecha y Hora:</span>
                        <span class="value">{cita['fecha_cita']}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Ciudad:</span>
                        <span class="value">{cita['ciudad']}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Dirección:</span>
                        <span class="value">{cita['direccion']}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Fecha de Creación:</span>
                        <span class="value">{cita['fecha_creacion']}</span>
                    </div>
                </div>

                <div class="alert">
                    <h3>ℹ️ Importante</h3>
                    <p>Por favor, llega 15 minutos antes de tu cita. Trae tu documento de identidad y cualquier examen previo que tengas.</p>
                </div>
            </div>

            <div class="footer">
                <p>Si necesitas cancelar o reprogramar, contacta a nuestro centro.</p>
                <p><strong>Laboratorio Clínico</strong></p>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


@app.get("/citas", response_class=HTMLResponse)
async def listar_citas_html():
    """Endpoint público para ver todas las citas"""
    citas = listar_todas_citas()

    filas_html = ""
    if citas:
        for cita in citas:
            filas_html += f"""
            <tr onclick="window.location.href='/citas/{cita['id']}'" style="cursor: pointer;">
                <td>{cita['id']}</td>
                <td>{cita['paciente_nombre']}</td>
                <td>{cita['identificacion']}</td>
                <td>{cita['fecha_cita']}</td>
                <td>{cita['ciudad']}</td>
                <td><span class="badge">Confirmada</span></td>
            </tr>
            """
    else:
        filas_html = """
        <tr>
            <td colspan="6" style="text-align: center; color: #777;">No hay citas registradas</td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Panel de Citas Médicas</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 40px 20px;
            }}

            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}

            .header {{
                background: white;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                margin-bottom: 30px;
                text-align: center;
            }}

            .header h1 {{
                color: #667eea;
                font-size: 32px;
                margin-bottom: 10px;
            }}

            .header p {{
                color: #777;
                font-size: 16px;
            }}

            .stats {{
                display: flex;
                gap: 20px;
                margin-bottom: 30px;
                flex-wrap: wrap;
            }}

            .stat-card {{
                flex: 1;
                min-width: 200px;
                background: white;
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
                text-align: center;
            }}

            .stat-number {{
                font-size: 36px;
                font-weight: bold;
                color: #667eea;
                margin-bottom: 10px;
            }}

            .stat-label {{
                color: #777;
                font-size: 14px;
            }}

            .table-container {{
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                overflow: hidden;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
            }}

            thead {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}

            thead th {{
                padding: 20px;
                text-align: left;
                font-weight: 600;
            }}

            tbody tr {{
                border-bottom: 1px solid #f0f0f0;
                transition: background-color 0.3s;
            }}

            tbody tr:hover {{
                background-color: #f8f9ff;
            }}

            tbody td {{
                padding: 18px 20px;
                color: #333;
            }}

            .badge {{
                background: #4CAF50;
                color: white;
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
            }}

            @media (max-width: 768px) {{
                .stats {{
                    flex-direction: column;
                }}

                table {{
                    font-size: 14px;
                }}

                thead th, tbody td {{
                    padding: 12px 10px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📅 Panel de Citas Médicas</h1>
                <p>Gestión y visualización de citas programadas</p>
            </div>

            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{len(citas)}</div>
                    <div class="stat-label">Total de Citas</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([c for c in citas if c['ciudad']])}</div>
                    <div class="stat-label">Citas Confirmadas</div>
                </div>
            </div>

            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Paciente</th>
                            <th>Identificación</th>
                            <th>Fecha</th>
                            <th>Ciudad</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)



########################################################

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import httpx
from datetime import datetime
import json
import os
from dotenv import load_dotenv
from openai import OpenAI
import sys
import pathlib

# Agregar el directorio padre al path para importar módulos
parent_dir = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from function_manager import FunctionManager
from functions import tools, available_functions
from conversation_cache import conversation_cache
import locale

# Configuración de EvolutionAPI


EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")  
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_NAME = os.getenv("INSTANCE_NAME")

# Configuración de OpenAI
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
function_manager = FunctionManager()

# Configurar locale en español
try:
    locale.setlocale(locale.LC_TIME, 'es_CO.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'Spanish_Colombia.1252')
        except locale.Error:
            print("⚠️ Warning: Spanish locale not available, using default locale")
            pass

# Funciones de database que necesitan db_path
DATABASE_FUNCTIONS = {
    'listar_usuarios', 'obtener_usuario', 'crear_usuario', 'actualizar_usuario',
    'eliminar_usuario', 'obtener_examenes_medicos', 'crear_examen_medico',
    'actualizar_examen_medico', 'eliminar_examen_medico', 'obtener_cita_examen_medico',
    'crear_cita_examen_medico', 'verificar_disponibilidad_citas', 'obtener_citas_activas_usuario',
    'crear_cita', 'obtener_cita_por_id', 'listar_todas_citas', 'eliminar_cita'
}


class WebhookPayload(BaseModel):
    event: str
    instance: str
    data: Dict[str, Any]
    destination: Optional[str] = None
    date_time: Optional[str] = None
    sender: Optional[str] = None
    server_url: Optional[str] = None
    apikey: Optional[str] = None

async def get_last_messages(remote_jid: str, limit: int = 5) -> List[Dict]:
    """
    Obtiene los últimos N mensajes de un chat específico
    """
    url = f"{EVOLUTION_API_URL}/chat/findMessages/{INSTANCE_NAME}"
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    payload = {
        "where": {
            "key": {
                "remoteJid": remote_jid
            }
        },
        "offset": limit
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # La estructura es: data.messages.records
            if isinstance(data, dict):
                messages_data = data.get("messages", {})
                if isinstance(messages_data, dict):
                    records = messages_data.get("records", [])
                    
                    print(f"✓ Se obtuvieron {len(records)} mensajes")
                    print(f"   Total en DB: {messages_data.get('total', 0)}")
                    print(f"   Página actual: {messages_data.get('currentPage', 1)}/{messages_data.get('pages', 1)}")
                    
                    return records
            
            print("⚠️ Estructura de respuesta inesperada")
            return []
            
    except Exception as e:
        print(f"Error obteniendo mensajes: {e}")
        import traceback
        traceback.print_exc()
        return []

# Store local como backup
class MessageStore:
    """Almacena mensajes en memoria para crear historial"""
    def __init__(self, max_messages_per_chat: int = 50):
        self.messages: Dict[str, List[Dict]] = {}
        self.max_messages = max_messages_per_chat
    
    def add_message(self, remote_jid: str, message_data: Dict):
        if remote_jid not in self.messages:
            self.messages[remote_jid] = []
        
        self.messages[remote_jid].append(message_data)
        
        # Mantener solo los últimos N mensajes
        if len(self.messages[remote_jid]) > self.max_messages:
            self.messages[remote_jid] = self.messages[remote_jid][-self.max_messages:]
    
    def get_messages(self, remote_jid: str, limit: int = 5) -> List[Dict]:
        messages = self.messages.get(remote_jid, [])
        return messages[-limit:] if messages else []

message_store = MessageStore(max_messages_per_chat=50)

def get_text_assistant_prompt() -> str:
    """
    Genera el system prompt para el asistente de mensajes de texto de WhatsApp
    Basado en el prompt de realtime_config.py pero adaptado para texto
    """
    from datetime import datetime, timezone, timedelta
    
    current_datetime_colombia = datetime.now(timezone(timedelta(hours=-5))).strftime("%A %Y-%m-%d %H:%M:%S")
    
    return f"""# Rol y Objetivo
Eres Juliana, la asistente virtual de Pasteur Laboratorios Clínicos, especializada en brindar soporte por WhatsApp a pacientes. Tu misión es ayudar a los usuarios a consultar resultados de exámenes médicos, agendar citas a domicilio, proporcionar información sobre nuestros servicios de laboratorio clínico y responder dudas generales sobre la empresa y los procedimientos.

# Personalidad y Tono
## Personalidad
- Profesional pero muy humana y cercana
- Empática, cálida y genuinamente interesada en ayudar
- Paciente y atenta a las necesidades del usuario
- Conversacional y amigable por WhatsApp
- Usa un lenguaje claro y profesional

## Tono Natural Profesional con Calidez Colombiana
- Habla como una profesional de laboratorio colombiana - cálida, clara, confiable
- Usa expresiones naturales: "perfecto", "claro", "con gusto", "listo"
- Expresiones colombianas naturales pero profesionales
- Cordial y cercana en saludos
- Natural y profesional al explicar

# Contexto de la Empresa

## Información General
- Nombre: Pasteur Laboratorios Clínicos
- Tipo: Empresa privada colombiana especializada en diagnóstico clínico
- Fundación: 1948 en Barranquilla, por el bacteriólogo Humberto Abello Lobo
- Trayectoria: Más de 75 años de experiencia en el sector salud
- Especialidades: Diagnóstico clínico, citología, genética y biología molecular
- Reconocimiento: Uno de los laboratorios más avanzados tecnológicamente de América Latina
- Innovación: Pioneros en Colombia y el Caribe en sistemas robóticos de análisis clínico
- Tecnología: Sistema Aptio Automation de Siemens (capacidad de 4.500 exámenes/hora con alta precisión)

## Información Detallada del Laboratorio
PARA cualquier pregunta sobre:
- Historia detallada de la empresa
- Tecnología y equipamiento específico
- Paquetes de servicios disponibles
- Ubicaciones de sedes y horarios específicos
- Servicios ofrecidos en detalle
- Políticas y procedimientos

USA la herramienta `search_info_about_the_lab` para obtener información actualizada y precisa.

# Idioma
- TODAS las conversaciones deben ser en ESPAÑOL
- Usa español colombiano estándar, claro y profesional
- Si el usuario habla en otro idioma, responde amablemente en español que solo brindas atención en este idioma

# Herramientas (Tools)

## 1. listar_usuarios
**Cuándo usarla:**
- Cuando un usuario te diga su nombre o cuando necesites buscar a alguien
- Es útil para hacer match con nombres cuando necesites identificar al usuario
- Úsala cuando el usuario quiera consultar sus exámenes o citas

**Cómo usarla:**
- SIEMPRE pide al usuario su nombre COMPLETO antes de usar esta función
- Ejemplo: "Para ayudarte mejor, ¿me puedes decir tu nombre completo por favor?"
- Una vez obtengas la lista, busca el nombre que tenga MAYOR SIMILITUD con lo que el usuario escribió
- Ten en cuenta variaciones: Christian/Cristian, José/Jose, María/Maria, etc.
- PRESTA ESPECIAL ATENCIÓN al `user_id` de cada usuario, lo necesitarás para otras funciones

**Parámetros:** Ninguno (trae todos los usuarios)

## 2. obtener_usuario
**Cuándo usarla:**
- Cuando ya tienes el número de identificación (cédula) específico de un usuario
- Generalmente NO la usarás porque `listar_usuarios` es más práctica
- Útil solo si el usuario te proporciona directamente su número de cédula

**Parámetros requeridos:**
- `identificacion`: Número de cédula del usuario (entero)

## 3. obtener_examenes_medicos
**Cuándo usarla:**
- Cuando el usuario pregunta por sus exámenes disponibles
- Cuando necesitas saber QUÉ exámenes tiene un usuario antes de enviarlos por correo
- Para verificar si un examen específico ya está disponible o aún no

**Cómo usarla:**
- REQUIERE el `user_id` (NO la cédula), obtenlo primero con `listar_usuarios`
- Retorna lista de exámenes con resúmenes y nombres de archivos PDF
- Presta atención a los nombres de archivos, los necesitarás para enviar correos

**Parámetros requeridos:**
- `id_usuario`: ID interno del usuario (obtener primero con listar_usuarios)

## 4. obtener_cita_examen_medico
**Cuándo usarla:**
- Cuando el usuario pregunta por sus citas programadas
- Para verificar fechas, direcciones y ciudades de citas existentes
- Para confirmar información de citas agendadas

**Cómo usarla:**
- REQUIERE el `user_id` (NO la cédula), obtenlo primero con `listar_usuarios`
- Retorna información completa: fecha, ciudad, dirección, examen asociado

**Parámetros requeridos:**
- `id_usuario`: ID interno del usuario (obtener primero con listar_usuarios)

## 5. send_email_with_file
**Cuándo usarla:**
- Cuando el usuario solicita que le envíes sus exámenes por correo
- SOLO después de haber consultado qué exámenes tiene disponibles con `obtener_examenes_medicos`
- ASEGÚRATE de que los archivos que vas a enviar existen en la lista de exámenes del usuario

**Cómo usarla:**
- Obtén el correo del usuario con `listar_usuarios` u `obtener_usuario`
- Verifica primero los exámenes disponibles del usuario
- Escribe un correo PROFESIONAL y BIEN ESTRUCTURADO
- El asunto debe ser claro y descriptivo
- El cuerpo debe incluir: saludo formal, contexto del envío, lista de exámenes adjuntos, despedida profesional

**Estructura del correo electrónico:**
```
Asunto: Resultados de Exámenes - Pasteur Laboratorios Clínicos

Estimado/a [Nombre del paciente]:

Reciba un cordial saludo de parte de Pasteur Laboratorios Clínicos.

Adjunto a este correo encontrará los resultados de sus exámenes médicos solicitados:
- [Nombre del examen 1]
- [Nombre del examen 2]

Para cualquier duda o aclaración sobre sus resultados, no dude en contactarnos.

Quedamos atentos a sus inquietudes.

Cordialmente,
Pasteur Laboratorios Clínicos
```

**Parámetros requeridos:**
- `to_email`: Correo del usuario (string, formato válido)
- `subject`: Asunto profesional y descriptivo (string)
- `body`: Cuerpo del mensaje formal y profesional (string)
- `files_to_attach`: Lista de nombres de archivos PDF (array de strings)

## 6. search_general_exam_info
**Cuándo usarla:**
- Cuando el usuario pregunta QUÉ ES un examen específico
- Cuando necesita saber PARA QUÉ SIRVE un examen
- Cuando pregunta sobre PREPARACIÓN necesaria para un examen
- Cuando quiere conocer CARACTERÍSTICAS de un tipo de examen
- Para responder dudas generales sobre procedimientos de exámenes
- IMPORTANTE: NO es para consultar exámenes de un usuario específico, es para información descriptiva general

**Ejemplos de preguntas que requieren esta herramienta:**
- "¿Qué mide el examen de glucosa?"
- "¿Cómo me preparo para el hemograma?"
- "¿Para qué sirve el perfil lipídico?"
- "¿Qué detecta el examen de tiroides?"
- "¿Necesito ayuno para el examen de colesterol?"
- "¿Qué información da un urocultivo?"

**Parámetros requeridos:**
- `query`: Pregunta o descripción del examen (string)
- `num_results`: Número de resultados, recomendado 3-5 (integer)

## 7. search_info_about_the_lab
**Cuándo usarla:**
- Cuando el usuario pregunta sobre la HISTORIA de Pasteur
- Cuando necesita información sobre TECNOLOGÍA y equipamiento del laboratorio
- Para consultar sobre PAQUETES DE SERVICIOS disponibles
- Cuando pregunta por UBICACIONES de sedes específicas
- Para obtener HORARIOS de atención de diferentes sedes
- Cuando quiere conocer TODOS LOS SERVICIOS que ofrece Pasteur
- Para responder sobre POLÍTICAS y PROCEDIMIENTOS generales
- Para información sobre FUNDADORES o TRAYECTORIA de la empresa

**Ejemplos de preguntas que requieren esta herramienta:**
- "¿Cuándo fue fundado Pasteur?"
- "¿Qué tecnología usan en el laboratorio?"
- "¿Tienen paquetes de exámenes disponibles?"
- "¿Dónde quedan las sedes en Barranquilla?"
- "¿Cuál es el horario de atención del sábado?"
- "¿Qué servicios adicionales ofrecen?"
- "¿Quién fundó Pasteur Laboratorios?"
- "¿Hacen domicilios?"

**Parámetros requeridos:**
- `query`: Pregunta sobre el laboratorio (string)
- `num_results`: Número de resultados, recomendado 3-5 (integer)

**IMPORTANTE - Diferencia entre search_general_exam_info y search_info_about_the_lab:**
- `search_general_exam_info`: Para información sobre EXÁMENES MÉDICOS (qué son, cómo funcionan, preparación)
- `search_info_about_the_lab`: Para información sobre EL LABORATORIO COMO EMPRESA (historia, sedes, servicios, tecnología, paquetes)

## 8. verificar_disponibilidad_citas
**Cuándo usarla:**
- SIEMPRE antes de crear una cita nueva
- Cuando el usuario pregunta "¿hay disponibilidad para...?"
- Para verificar horarios disponibles en una ciudad y fecha específica
- IMPORTANTE: Usar SIEMPRE como primer paso al agendar citas

**Parámetros requeridos:**
- `fecha_cita`: Fecha y hora exacta (string) - "2025-10-15 10:30 AM"
- `ciudad`: Ciudad (string) - "Barranquilla", "Bogotá", etc.

## 9. obtener_citas_activas_usuario
**Cuándo usarla:**
- Cuando el usuario pregunta "¿qué citas tengo?"
- Para consultar citas programadas de un usuario
- Cuando necesita saber sus próximas citas
- IMPORTANTE: Requiere user_id (obtener primero con listar_usuarios)

**Parámetros requeridos:**
- `id_usuario`: ID interno del usuario (integer) - Obtener con listar_usuarios

## 10. crear_cita
**Cuándo usarla:**
- SOLO después de verificar disponibilidad con `verificar_disponibilidad_citas`
- Cuando el usuario CONFIRMA que quiere agendar en ese horario
- NUNCA crear cita sin verificar disponibilidad primero
- La función envía correo de confirmación automáticamente

**Flujo OBLIGATORIO para agendar:**
1. Usuario pide agendar cita
2. Obtener: fecha/hora, tipo de examen, ciudad (preguntar lo que falte)
3. Usar `listar_usuarios` para obtener user_id del usuario (IMPORTANTE: guarda el user_id)
4. Usar `verificar_disponibilidad_citas` para verificar
5. Confirmar con usuario: "Hay disponibilidad para [fecha] en [ciudad], ¿confirmas la cita?"
6. Si usuario confirma → Usar `crear_cita` con el user_id guardado
7. Informar que se envió correo de confirmación

**Parámetros requeridos:**
- `id_usuario`: ID interno del usuario (integer) - Obtener con listar_usuarios
- `fecha_cita`: Fecha/hora (string)
- `tipo_examen`: Tipo de examen (string)
- `ciudad`: Ciudad (string)

## 11. eliminar_cita
**Cuándo usarla:**
- Cuando el usuario quiere cancelar una cita
- SOLO después de mostrar las citas activas con `obtener_citas_activas_usuario`
- Confirmar siempre antes de eliminar

**Parámetros requeridos:**
- `id`: ID único de la cita (integer)

# Flujo de Conversación

## Saludo Inicial
- Preséntate de forma cálida: "Hola! 👋 Soy Juliana, asistente virtual de Pasteur Laboratorios. ¿En qué puedo ayudarte hoy?"
- Si el usuario ya te saludó o dijo su nombre, no te vuelvas a presentar
- Pregunta el nombre SOLO si necesitas identificar al usuario para una consulta específica

## Identificar Necesidad
- Escucha qué necesita el usuario
- Determina el tipo de consulta:
  * DATOS DE USUARIO: Consultar exámenes propios, citas, envío de resultados → Necesitarás `listar_usuarios`
  * INFO EXÁMENES: Qué es un examen, preparación, características → Usa `search_general_exam_info`
  * INFO LABORATORIO: Sedes, horarios, servicios, historia, paquetes → Usa `search_info_about_the_lab`

## Búsqueda de Información
- Usa las herramientas apropiadas según el tipo de consulta
- Sé clara sobre qué estás buscando
- Si necesitas datos del usuario, pide su nombre completo

## Atención de Solicitud
- Resuelve la necesidad específica del usuario
- Presenta información de forma clara y estructurada
- Usa emojis de forma profesional para hacer el mensaje más amigable

## Confirmación y Cierre
- Pregunta si necesita algo más: "¿Hay algo más en lo que pueda ayudarte?"
- Cierra cordialmente: "Con gusto! Que tengas un excelente día 😊"

# Reglas de Conversación

## DO (Hacer SIEMPRE)
- Sé clara, directa y profesional
- Usa el nombre del usuario cuando lo conozcas
- Estructura bien tus respuestas con saltos de línea
- Usa emojis de forma profesional (no excesiva)
- Identifica correctamente qué tipo de información necesitas buscar
- Usa las herramientas apropiadas según el contexto
- Sé empática y cercana

## DON'T (NUNCA hacer)
- NO inventes información que no tengas de las herramientas
- NO confundas `user_id` con `identificacion` (cédula)
- NO busques en `listar_usuarios` si la pregunta es sobre información general
- NO uses `search_general_exam_info` para consultar exámenes de un usuario específico
- NO uses `search_info_about_the_lab` para información sobre tipos de exámenes médicos
- NO seas demasiado formal o robotica
- NO uses muletillas de voz como "eee" o "mmm" (esto es texto, no voz)

# REGLA CRÍTICA: Confirmación Antes de Acciones

**IMPORTANTE - NUNCA ejecutes acciones sin confirmación explícita del usuario:**

## Acciones que REQUIEREN confirmación:
1. **Enviar correos** (`send_email_with_file`)
2. **Crear citas** (`crear_cita`)
3. **Eliminar citas** (`eliminar_cita`)

## Flujo OBLIGATORIO para acciones:

### Ejemplo 1: Envío de exámenes por correo
❌ **INCORRECTO:**
Usuario: "Envíame mis exámenes por correo"
Asistente: *Ejecuta send_email_with_file* → "Listo, ya te envié los exámenes"

✅ **CORRECTO:**
Usuario: "Envíame mis exámenes por correo"
Asistente: "Perfecto! Veo que tienes disponibles:
- Examen de orina
- Hemograma completo

¿Confirmas que quieres que te los envíe a [correo]? Responde 'sí' o 'confirmo' para proceder."

Usuario: "Sí, confirmo"
Asistente: *Ejecuta send_email_with_file* → "Perfecto! Te acabo de enviar los exámenes a tu correo. Revisa tu bandeja de entrada."

### Ejemplo 2: Crear cita
❌ **INCORRECTO:**
Asistente: *Verifica disponibilidad* → *Ejecuta crear_cita inmediatamente*

✅ **CORRECTO:**
Asistente: "Perfecto! Hay disponibilidad para el 25 de octubre a las 10:00 AM en Barranquilla para el examen de Hemograma.

¿Confirmas que quieres agendar esta cita? Responde 'sí' o 'confirmo' para proceder."

Usuario: "Sí"
Asistente: *Ejecuta crear_cita* → "Excelente! Tu cita ha sido agendada para el 25 de octubre a las 10:00 AM en Barranquilla. Te llegará un correo de confirmación."

### Ejemplo 3: Eliminar cita
❌ **INCORRECTO:**
Usuario: "Cancela mi cita"
Asistente: *Ejecuta eliminar_cita inmediatamente*

✅ **CORRECTO:**
Usuario: "Cancela mi cita"
Asistente: "Veo que tienes una cita programada para el 25 de octubre a las 10:00 AM en Barranquilla.

¿Confirmas que quieres cancelar esta cita? Responde 'sí' o 'confirmo' para proceder."

Usuario: "Sí"
Asistente: *Ejecuta eliminar_cita* → "Tu cita ha sido cancelada exitosamente."

## Palabras de confirmación válidas:
- "sí", "si", "confirmo", "confirmar", "dale", "ok", "okay", "procede", "adelante", "claro"

## Cómo detectar si el usuario ya confirmó:
- Revisa el mensaje anterior del asistente
- Si el asistente pidió confirmación y el usuario responde con palabra de confirmación → Ejecuta la acción
- Si no hay solicitud de confirmación previa → Pide confirmación primero

# Formato de Respuestas para WhatsApp
- Usa saltos de línea para separar secciones
- Usa emojis relevantes pero profesionales
- Sé concisa pero completa
- Estructura la información de forma clara
- Usa negrita (*texto*) para resaltar información importante

# Manejo de Zona Horaria Colombia
La fecha y hora actual en Colombia (UTC-5) es: {current_datetime_colombia}

IMPORTANTE al agendar citas:
- Colombia está en zona horaria UTC-5 (no cambia por horario de verano)
- Horario de atención sugerido: Lunes a Viernes 7:00 AM - 5:00 PM, Sábados 7:00 AM - 12:00 PM
- Si el usuario pide una hora fuera de horario, sugiere alternativas dentro del horario
- Verifica siempre que la fecha sea FUTURA (no en el pasado)

# Recordatorio Final
- Eres un asistente por WHATSAPP (texto), no llamada telefónica
- Usa las herramientas PROACTIVAMENTE para ayudar al usuario
- IDENTIFICA correctamente qué tipo de consulta es antes de elegir herramienta
- VERIFICA la información antes de confirmar algo al usuario
- Sé PROFESIONAL pero HUMANA en tu trato
- Representa con orgullo la trayectoria de más de 75 años de Pasteur
"""

async def send_whatsapp_message(remote_jid: str, message: str) -> bool:
    """
    Envía un mensaje de WhatsApp usando Evolution API
    """
    url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    payload = {
        "number": remote_jid,
        "text": message
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            print(f"✓ Mensaje enviado exitosamente a {remote_jid}")
            return True
    except Exception as e:
        print(f"✗ Error enviando mensaje: {e}")
        import traceback
        traceback.print_exc()
        return False

async def process_message_with_openai(conversation_history: List[Dict[str, str]], user_message: str, remote_jid: str) -> str:
    """
    Procesa un mensaje usando OpenAI API con function calling y caché Redis
    """
    try:
        # 1. Intentar obtener conversación del caché Redis
        cached_conversation = conversation_cache.get_conversation(remote_jid)

        if cached_conversation:
            # Usar conversación en caché (incluye resultados de funciones previas)
            print(f"📥 Usando conversación en caché ({len(cached_conversation)} mensajes)")
            conversation_to_use = cached_conversation
        else:
            # Crear nueva conversación con los mensajes recientes de WhatsApp
            print(f"📭 No hay caché, creando nueva conversación con {len(conversation_history)} mensajes")
            conversation_to_use = conversation_history.copy()

        # 2. Agregar mensaje actual del usuario a la conversación
        conversation_to_use.append({"role": "user", "content": user_message})

        # 3. Preparar mensajes para OpenAI
        messages = [
            {"role": "system", "content": get_text_assistant_prompt()}
        ]
        messages.extend(conversation_to_use)

        print(f"\n🤖 Procesando con OpenAI...")
        print(f"📝 Mensajes enviados: {len(messages)}")
        print(f"   - System: 1")
        print(f"   - Conversación: {len(conversation_to_use)}")
        print(f"   - Total: {len(messages)}")

        # Convertir tools al formato de OpenAI Chat Completions
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })

        # Primera llamada a OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            tools=openai_tools,
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # Si hay function calls, procesarlas
        if tool_calls:
            print(f"\n🔧 Se detectaron {len(tool_calls)} function calls")

            # Convertir response_message a dict para agregarlo a messages
            # El objeto ChatCompletionMessage necesita ser serializado
            response_message_dict = {
                "role": "assistant",
                "content": response_message.content or "",  # OpenAI no acepta null, usar string vacío
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in tool_calls
                ]
            }
            messages.append(response_message_dict)

            # Ejecutar cada function call
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args_str = tool_call.function.arguments

                print(f"   📞 Ejecutando: {function_name}")
                print(f"   📋 Argumentos: {function_args_str}")

                # Ejecutar la función usando available_functions
                try:
                    # Parsear argumentos JSON
                    function_args = json.loads(function_args_str)

                    # Obtener la función del diccionario
                    if function_name not in available_functions:
                        raise ValueError(f"Función {function_name} no encontrada en available_functions")

                    function_to_call = available_functions[function_name]

                    # Lista de funciones que requieren db_path
                    db_functions = {
                        'listar_usuarios', 'obtener_usuario', 'crear_usuario', 'actualizar_usuario',
                        'eliminar_usuario', 'obtener_examenes_medicos', 'crear_examen_medico',
                        'actualizar_examen_medico', 'eliminar_examen_medico', 'obtener_cita_examen_medico',
                        'crear_cita_examen_medico', 'verificar_disponibilidad_citas', 'obtener_citas_activas_usuario',
                        'crear_cita', 'obtener_cita_por_id', 'listar_todas_citas', 'eliminar_cita'
                    }

                    # Inyectar db_path si la función lo requiere
                    if function_name in db_functions:
                        db_path = os.path.join(os.path.dirname(__file__), "database.db")
                        function_args['db_path'] = db_path
                        print(f"   📁 Inyectando db_path: {db_path}")

                    # Ejecutar la función con los argumentos
                    function_response = function_to_call(**function_args)

                    # Convertir respuesta a string si es necesario
                    if not isinstance(function_response, str):
                        function_response = json.dumps(function_response, ensure_ascii=False)

                    print(f"   ✓ Resultado: {function_response[:200]}...")

                    # Agregar el resultado de la función a los mensajes
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response
                    })

                except Exception as e:
                    print(f"   ✗ Error ejecutando {function_name}: {e}")
                    import traceback
                    traceback.print_exc()

                    # Agregar error como respuesta de la función
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": f"Error: {str(e)}"
                    })

            # Segunda llamada a OpenAI con los resultados de las funciones
            print(f"\n🤖 Segunda llamada a OpenAI con resultados de funciones...")
            second_response = openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=messages
            )

            final_message = second_response.choices[0].message.content
        else:
            # No hay function calls, usar la respuesta directa
            final_message = response_message.content

        # 4. Agregar respuesta del asistente a la conversación
        conversation_to_use.append({"role": "assistant", "content": final_message})

        # 5. Guardar conversación actualizada en Redis (con todos los mensajes incluyendo resultados de funciones)
        # Nota: conversation_to_use ya incluye el mensaje del usuario y la respuesta del asistente
        # Los resultados de las funciones están en 'messages' pero no los guardamos explícitamente
        # porque el LLM ya los procesó y generó la respuesta final

        # Construir conversación limpia para Redis (sin system prompt, solo user/assistant)
        clean_conversation = []
        for msg in messages[1:]:  # Saltar system prompt
            if msg.get("role") in ["user", "assistant"]:
                clean_conversation.append({
                    "role": msg["role"],
                    "content": msg.get("content", "")
                })
            elif msg.get("role") == "tool":
                # Guardar resultados de funciones en el contexto
                clean_conversation.append({
                    "role": "tool",
                    "name": msg.get("name"),
                    "content": msg.get("content")
                })

        conversation_cache.save_conversation(remote_jid, clean_conversation)

        print(f"\n✓ Respuesta generada: {final_message[:200]}...")
        print(f"💾 Conversación guardada en Redis con {len(clean_conversation)} mensajes")

        return final_message

    except Exception as e:
        print(f"✗ Error procesando con OpenAI: {e}")
        import traceback
        traceback.print_exc()
        return "Disculpa, tuve un problema al procesar tu mensaje. ¿Podrías intentarlo de nuevo?"

@app.post("/webhook/evolution")
async def evolution_webhook(request: Request, payload: WebhookPayload):
    try:
        print(f"Evento recibido: {payload.event}")
        
        if payload.event == "messages.upsert":
            await handle_message(payload.data)
        
        elif payload.event == "connection.update":
            await handle_connection_update(payload.data)
        
        return {"status": "success", "message": "Webhook procesado"}
    
    except Exception as e:
        print(f"Error procesando webhook: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def handle_message(data: Dict[str, Any]):
    """Procesa mensajes recibidos y mantiene historial"""
    try:
        message = data.get("message", {})
        key = data.get("key", {})
        
        remote_jid = key.get("remoteJid")
        from_me = key.get("fromMe", False)
        message_timestamp = data.get("messageTimestamp", int(datetime.now().timestamp()))
        push_name = data.get("pushName", "Desconocido")
        
        # Guardar mensaje en el store local
        message_store.add_message(remote_jid, {
            "key": key,
            "message": message,
            "messageTimestamp": message_timestamp,
            "fromMe": from_me,
            "pushName": push_name
        })
        
        # Extraer el texto del mensaje actual
        text = extract_message_text(message)
        
        print(f"\n{'='*50}")
        print(f"Nuevo mensaje de {push_name} ({remote_jid})")
        print(f"Mensaje: {text}")
        print(f"{'='*50}\n")
        
        # Obtener los últimos mensajes de la API
        api_messages = await get_last_messages(remote_jid, limit=5)
        
        if api_messages:
            print(f"Últimos {len(api_messages)} mensajes del chat (desde API):")
            print(f"{'-'*50}")
            
            # Ordenar mensajes por timestamp
            sorted_messages = sorted(
                api_messages, 
                key=lambda x: x.get("messageTimestamp", 0)
            )
            
            for idx, msg in enumerate(sorted_messages, 1):
                try:
                    msg_key = msg.get("key", {})
                    msg_content = msg.get("message", {})
                    
                    msg_text = extract_message_text(msg_content)
                    sender_name = msg.get("pushName", "Desconocido")
                    is_from_me = msg_key.get("fromMe", False)
                    sender = f"Tú" if is_from_me else sender_name
                    timestamp = msg.get("messageTimestamp", "")
                    
                    print(f"{idx}. [{sender}] {msg_text}")
                    if timestamp:
                        try:
                            dt = datetime.fromtimestamp(int(timestamp))
                            print(f"   Hora: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                        except:
                            pass
                    print()
                    
                except Exception as e:
                    print(f"{idx}. [Error procesando mensaje]: {e}")
                    continue
            
            # Crear contexto de la conversación
            context_lines = []
            for m in sorted_messages:
                if isinstance(m, dict):
                    msg_key = m.get("key", {})
                    msg_content = m.get("message", {})
                    is_from_me = msg_key.get("fromMe", False)
                    sender_name = "Asistente (Juliana)" if is_from_me else m.get("pushName", "Cliente")
                    text = extract_message_text(msg_content)
                    context_lines.append(f"{sender_name}: {text}")
            
            context = "\n".join(context_lines)
            print(f"\n📝 Contexto de la conversación:\n{'-'*50}")
            print(context)
            print(f"{'-'*50}\n")
            
            # Solo responder si el mensaje NO es de nosotros
            if not from_me:
                # Preparar historial de conversación para OpenAI
                conversation_history = []
                for m in sorted_messages[:-1]:  # Excluir el mensaje actual que ya se agregará
                    if isinstance(m, dict):
                        msg_key = m.get("key", {})
                        msg_content = m.get("message", {})
                        is_from_me_hist = msg_key.get("fromMe", False)
                        msg_text = extract_message_text(msg_content)
                        
                        # Solo agregar mensajes con texto válido
                        if msg_text and not msg_text.startswith("["):
                            role = "assistant" if is_from_me_hist else "user"
                            conversation_history.append({
                                "role": role,
                                "content": msg_text
                            })
                
                # Extraer texto del mensaje actual
                current_message_text = extract_message_text(message)
                
                # Solo procesar si el mensaje tiene texto válido
                if current_message_text and not current_message_text.startswith("["):
                    print(f"\n🚀 Enviando mensaje a OpenAI para procesamiento...")
                    
                    # Procesar con OpenAI
                    response_text = await process_message_with_openai(
                        conversation_history=conversation_history,
                        user_message=current_message_text,
                        remote_jid=remote_jid
                    )
                    
                    # Enviar respuesta por WhatsApp
                    print(f"\n📤 Enviando respuesta por WhatsApp...")
                    success = await send_whatsapp_message(remote_jid, response_text)
                    
                    if success:
                        print(f"✓ Conversación completada exitosamente")
                    else:
                        print(f"✗ Error enviando respuesta al usuario")
                else:
                    print(f"⚠️ Mensaje sin texto válido, no se procesará")
            else:
                print(f"⚠️ Mensaje enviado por nosotros, no se responderá")
            
        else:
            print("⚠ No se pudieron obtener mensajes de la API")
            print("Mostrando historial local:")
            local_messages = message_store.get_messages(remote_jid, limit=5)
            
            for idx, msg in enumerate(local_messages, 1):
                msg_key = msg.get("key", {})
                msg_content = msg.get("message", {})
                msg_text = extract_message_text(msg_content)
                sender = "Tú" if msg.get("fromMe") else msg.get("pushName", "Cliente")
                print(f"{idx}. [{sender}] {msg_text}")
            
            # Procesar con OpenAI usando historial local si el mensaje no es de nosotros
            if not from_me:
                # Preparar historial de conversación
                conversation_history = []
                for msg in local_messages[:-1]:  # Excluir el mensaje actual
                    msg_content = msg.get("message", {})
                    is_from_me_hist = msg.get("fromMe", False)
                    msg_text = extract_message_text(msg_content)
                    
                    if msg_text and not msg_text.startswith("["):
                        role = "assistant" if is_from_me_hist else "user"
                        conversation_history.append({
                            "role": role,
                            "content": msg_text
                        })
                
                # Extraer texto del mensaje actual
                current_message_text = extract_message_text(message)
                
                # Solo procesar si el mensaje tiene texto válido
                if current_message_text and not current_message_text.startswith("["):
                    print(f"\n🚀 Enviando mensaje a OpenAI para procesamiento (historial local)...")
                    
                    # Procesar con OpenAI
                    response_text = await process_message_with_openai(
                        conversation_history=conversation_history,
                        user_message=current_message_text,
                        remote_jid=remote_jid
                    )
                    
                    # Enviar respuesta por WhatsApp
                    print(f"\n📤 Enviando respuesta por WhatsApp...")
                    success = await send_whatsapp_message(remote_jid, response_text)
                    
                    if success:
                        print(f"✓ Conversación completada exitosamente")
                    else:
                        print(f"✗ Error enviando respuesta al usuario")
                else:
                    print(f"⚠️ Mensaje sin texto válido, no se procesará")
            else:
                print(f"⚠️ Mensaje enviado por nosotros, no se responderá")
            
    except Exception as e:
        print(f"Error en handle_message: {e}")
        import traceback
        traceback.print_exc()
        raise

def extract_message_text(message_content) -> str:
    """Extrae el texto de diferentes tipos de mensajes"""
    try:
        if not isinstance(message_content, dict):
            return "[Mensaje en formato incorrecto]"
        
        # Mensaje de texto simple
        if "conversation" in message_content:
            return str(message_content["conversation"])
        
        # Mensaje de texto extendido
        if "extendedTextMessage" in message_content:
            ext_msg = message_content["extendedTextMessage"]
            if isinstance(ext_msg, dict):
                return str(ext_msg.get("text", ""))
        
        # Mensaje con imagen
        if "imageMessage" in message_content:
            img_msg = message_content["imageMessage"]
            if isinstance(img_msg, dict):
                caption = img_msg.get("caption", "")
                return f"📷 [Imagen] {caption}" if caption else "📷 [Imagen]"
        
        # Mensaje con video
        if "videoMessage" in message_content:
            vid_msg = message_content["videoMessage"]
            if isinstance(vid_msg, dict):
                caption = vid_msg.get("caption", "")
                return f"🎥 [Video] {caption}" if caption else "🎥 [Video]"
        
        # Mensaje de audio
        if "audioMessage" in message_content:
            ptt = message_content["audioMessage"].get("ptt", False)
            return "🎤 [Nota de voz]" if ptt else "🎵 [Audio]"
        
        # Mensaje de documento
        if "documentMessage" in message_content:
            doc_msg = message_content["documentMessage"]
            if isinstance(doc_msg, dict):
                filename = doc_msg.get("fileName", "documento")
                return f"📄 [Documento: {filename}]"
        
        # Sticker
        if "stickerMessage" in message_content:
            return "😄 [Sticker]"
        
        # Ubicación
        if "locationMessage" in message_content:
            return "📍 [Ubicación compartida]"
        
        # Contacto
        if "contactMessage" in message_content:
            return "👤 [Contacto compartido]"
        
        # Mensaje de reacción
        if "reactionMessage" in message_content:
            reaction = message_content["reactionMessage"].get("text", "")
            return f"❤️ [Reacción: {reaction}]"
        
        return "[Mensaje sin texto]"
        
    except Exception as e:
        print(f"Error extrayendo texto: {e}")
        return "[Error al procesar mensaje]"

async def handle_connection_update(data: Dict[str, Any]):
    """Maneja actualizaciones de conexión"""
    try:
        state = data.get("state")
        print(f"📱 Estado de conexión: {state}")
    except Exception as e:
        print(f"Error en connection update: {e}")

@app.get("/messages/{remote_jid}")
async def get_messages_endpoint(
    remote_jid: str, 
    limit: int = 5,
    page: int = 1
):
    """
    Endpoint para obtener mensajes manualmente

    """
    # Modificar payload para incluir paginación
    url = f"{EVOLUTION_API_URL}/chat/findMessages/{INSTANCE_NAME}"
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    payload = {
        "where": {
            "key": {
                "remoteJid": remote_jid
            }
        },
        "page": page,
        "offset": limit
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        data = response.json()
    
    return data

@app.get("/chats")
async def list_chats():
    """Lista todos los chats en memoria local"""
    chats = []
    for jid, messages in message_store.messages.items():
        last_message = messages[-1] if messages else {}
        chats.append({
            "remoteJid": jid,
            "pushName": last_message.get("pushName", "Desconocido"),
            "messageCount": len(messages),
            "lastMessage": extract_message_text(last_message.get("message", {})),
            "lastTimestamp": last_message.get("messageTimestamp")
        })
    
    return {"chats": chats, "total": len(chats)}

@app.get("/")
async def root():
    return {
        "status": "active",
        "webhook_url": "/webhook/evolution",
        "endpoints": {
            "messages": "/messages/{remote_jid}",
            "chats": "/chats"
        },
        "chats_in_memory": len(message_store.messages)
    }


if __name__ == "__main__":
    import uvicorn
    print(f"Listening on http://localhost:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
    #run: uvicorn main:app --reload --host 0.0.0.0 --port 5001