import asyncio
import json
import os
import wave
import base64
from datetime import datetime
from typing import Optional

class CallRecorder:
    """Clase para grabar llamadas desde el WebSocket de OpenAI Realtime API"""
    
    def __init__(self, recordings_dir: str = "recordings"):
        self.recordings_dir = recordings_dir
        self.current_call_id: Optional[str] = None
        self.audio_chunks = []
        self.conversation_log = []
        self.start_time: Optional[datetime] = None
        
        # Crear directorio si no existe
        os.makedirs(recordings_dir, exist_ok=True)
    
    def start_recording(self, call_id: str):
        """Inicia una nueva grabación"""
        self.current_call_id = call_id
        self.audio_chunks = []
        self.conversation_log = []
        self.start_time = datetime.now()
        
        print(f"🔴 Iniciando grabación para call_id: {call_id}")
    
    async def process_audio_chunk(self, message_data: dict):
        """Procesa chunks de audio del WebSocket"""
        message_type = message_data.get("type")

        # Probar ambos tipos de eventos: response.audio.delta y response.audio_transcript.delta
        if message_type in ["response.audio.delta", "response.output_audio.delta"]:
            audio_data = message_data.get("delta", "")
            if audio_data:
                # Decodificar audio base64 y almacenar
                try:
                    audio_bytes = base64.b64decode(audio_data)
                    self.audio_chunks.append({
                        "timestamp": datetime.now().isoformat(),
                        "source": "assistant",
                        "data": audio_bytes
                    })
                    # Log cada 10 chunks para no saturar
                    if len(self.audio_chunks) % 10 == 0:
                        print(f"🎵 Audio chunks capturados: {len(self.audio_chunks)} (evento: {message_type})")
                except Exception as e:
                    print(f"⚠️ Error procesando audio: {e}")
            else:
                print(f"⚠️ {message_type} sin data")
    
    async def log_conversation(self, message_data: dict):
        """Registra la conversación en texto"""
        message_type = message_data.get("type", "")
        timestamp = datetime.now().isoformat()
        
        # Transcripción del asistente
        if message_type == "response.output_audio_transcript.delta":
            transcript = message_data.get("delta", "")
            if transcript.strip():
                self.conversation_log.append({
                    "timestamp": timestamp,
                    "speaker": "assistant",
                    "text": transcript,
                    "type": "transcript_delta"
                })
        
        # Transcripción del usuario completada
        elif message_type == "conversation.item.input_audio_transcription.completed":
            transcript = message_data.get("transcript", "")
            if transcript.strip():
                self.conversation_log.append({
                    "timestamp": timestamp,
                    "speaker": "user",
                    "text": transcript,
                    "type": "transcript_completed"
                })
        
        # Otros eventos importantes
        elif message_type in ["session.created", "response.created", "response.done"]:
            self.conversation_log.append({
                "timestamp": timestamp,
                "event": message_type,
                "data": message_data
            })
    
    async def save_recording(self) -> dict:
        """Guarda la grabación completa"""
        if not self.current_call_id:
            return {"error": "No hay grabación activa"}

        print(f"💾 Guardando grabación - Audio chunks: {len(self.audio_chunks)}, Conversación: {len(self.conversation_log)}")

        timestamp_str = self.start_time.strftime("%Y%m%d_%H%M%S")
        base_filename = f"{timestamp_str}_{self.current_call_id}"

        results = {}
        
        try:
            # 1. Guardar log de conversación
            conversation_file = os.path.join(self.recordings_dir, f"{base_filename}_conversation.json")
            
            conversation_data = {
                "call_id": self.current_call_id,
                "start_time": self.start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
                "conversation": self.conversation_log,
                "total_messages": len(self.conversation_log),
                "audio_chunks_count": len(self.audio_chunks)
            }
            
            with open(conversation_file, 'w', encoding='utf-8') as f:
                f.write(json.dumps(conversation_data, indent=2, ensure_ascii=False))
            
            results["conversation_file"] = conversation_file
            
            # 2. Guardar audio chunks como archivo WAV reproducible
            if self.audio_chunks:
                audio_file = os.path.join(self.recordings_dir, f"{base_filename}_audio.wav")

                # Combinar todos los chunks de audio
                audio_data = b''
                for chunk in self.audio_chunks:
                    audio_data += chunk["data"]

                # Guardar como WAV
                # OpenAI Realtime API usa PCM16 24kHz mono
                with wave.open(audio_file, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit (2 bytes)
                    wav_file.setframerate(24000)  # 24kHz
                    wav_file.writeframes(audio_data)

                results["audio_file"] = audio_file
                results["audio_chunks"] = len(self.audio_chunks)

                print(f"🎵 Audio guardado: {len(audio_data)} bytes → {audio_file}")
            
            # 3. Crear resumen de la grabación
            summary_file = os.path.join(self.recordings_dir, f"{base_filename}_summary.txt")
            
            # Extraer texto completo de la conversación
            user_texts = []
            assistant_texts = []
            
            for entry in self.conversation_log:
                if entry.get("speaker") == "user":
                    user_texts.append(entry.get("text", ""))
                elif entry.get("speaker") == "assistant":
                    assistant_texts.append(entry.get("text", ""))
            
            summary_content = f"""RESUMEN DE LLAMADA
=====================================
Call ID: {self.current_call_id}
Inicio: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
Duración: {conversation_data['duration_seconds']:.1f} segundos
Total mensajes: {len(self.conversation_log)}
Chunks de audio: {len(self.audio_chunks)}

CONVERSACIÓN USUARIO:
{' '.join(user_texts)}

CONVERSACIÓN ASISTENTE:
{' '.join(assistant_texts)}

ARCHIVOS GENERADOS:
- Conversación: {os.path.basename(conversation_file)}
- Audio: {os.path.basename(audio_file) if self.audio_chunks else 'No disponible'}
- Resumen: {os.path.basename(summary_file)}
"""
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(summary_content)
            
            results["summary_file"] = summary_file
            results["call_id"] = self.current_call_id
            results["duration"] = conversation_data['duration_seconds']
            
            print(f"✅ Grabación guardada: {base_filename}")
            
        except Exception as e:
            print(f"❌ Error guardando grabación: {e}")
            results["error"] = str(e)
        
        # Limpiar datos de la grabación actual
        self.current_call_id = None
        self.audio_chunks = []
        self.conversation_log = []
        self.start_time = None
        
        return results
    
    def get_recordings_list(self) -> list:
        """Lista todas las grabaciones disponibles"""
        recordings = []
        
        try:
            for file in os.listdir(self.recordings_dir):
                if file.endswith('_summary.txt'):
                    # Extraer información del nombre del archivo
                    base_name = file.replace('_summary.txt', '')
                    parts = base_name.split('_')
                    
                    if len(parts) >= 2:
                        timestamp_str = parts[0]
                        call_id = '_'.join(parts[1:])
                        
                        # Verificar archivos relacionados
                        conversation_file = f"{base_name}_conversation.json"
                        audio_file = f"{base_name}_audio.wav"

                        recordings.append({
                            "timestamp": timestamp_str,
                            "call_id": call_id,
                            "base_name": base_name,
                            "files": {
                                "summary": file,
                                "conversation": conversation_file if os.path.exists(os.path.join(self.recordings_dir, conversation_file)) else None,
                                "audio": audio_file if os.path.exists(os.path.join(self.recordings_dir, audio_file)) else None
                            }
                        })
            
            # Ordenar por timestamp (más reciente primero)
            recordings.sort(key=lambda x: x["timestamp"], reverse=True)
            
        except Exception as e:
            print(f"❌ Error listando grabaciones: {e}")
        
        return recordings

# Instancia global del grabador
call_recorder = CallRecorder()