# 📹 SISTEMA DE GRABACIÓN DE LLAMADAS
# =====================================

## 🎯 **Características implementadas:**

### ✅ **Grabación automática:**
- Se inicia automáticamente cuando se establece el WebSocket
- Graba audio chunks del asistente en base64
- Registra transcripciones completas de la conversación
- Guarda eventos importantes del WebSocket

### ✅ **Archivos generados por llamada:**
- `{timestamp}_{call_id}_conversation.json` - Log completo de la conversación
- `{timestamp}_{call_id}_audio.bin` - Audio binario concatenado
- `{timestamp}_{call_id}_summary.txt` - Resumen legible de la llamada

### ✅ **APIs REST para manejo:**
- `GET /recordings` - Lista todas las grabaciones
- `GET /recordings/{id}/conversation` - Conversación específica
- `GET /recordings/{id}/summary` - Resumen específico
- `DELETE /recordings/{id}` - Eliminar grabación

## 🚀 **Cómo usar:**

### **1. Iniciar el servidor con grabación:**
```bash
python main.py
```

### **2. Las grabaciones se almacenan automáticamente en:**
```
recordings/
├── 20251020_143025_rtc_abc123_conversation.json
├── 20251020_143025_rtc_abc123_audio.bin
└── 20251020_143025_rtc_abc123_summary.txt
```

### **3. Consultar grabaciones:**
```bash
# Listar todas las grabaciones
curl http://localhost:5001/recordings

# Ver conversación específica
curl http://localhost:5001/recordings/20251020_143025_rtc_abc123/conversation

# Ver resumen
curl http://localhost:5001/recordings/20251020_143025_rtc_abc123/summary
```

## 📊 **Estructura del JSON de conversación:**
```json
{
  "call_id": "rtc_abc123",
  "start_time": "2025-10-20T14:30:25.123456",
  "end_time": "2025-10-20T14:35:10.654321",
  "duration_seconds": 285.5,
  "conversation": [
    {
      "timestamp": "2025-10-20T14:30:26.000000",
      "speaker": "user",
      "text": "Hola, quiero agendar una cita",
      "type": "transcript_completed"
    },
    {
      "timestamp": "2025-10-20T14:30:27.000000",
      "speaker": "assistant",  
      "text": "¡Hola! Estaré encantado de ayudarte a agendar tu cita...",
      "type": "transcript_delta"
    }
  ],
  "total_messages": 15,
  "audio_chunks_count": 42
}
```

## ⚙️ **Configuración avanzada:**

### **Cambiar directorio de grabaciones:**
```python
# En call_recorder.py
call_recorder = CallRecorder(recordings_dir="mis_grabaciones")
```

### **Filtrar qué grabar:**
```python
# En handle_websocket_message(), puedes agregar condiciones:
if message_type in ["response.audio.delta", "conversation.item.input_audio_transcription.completed"]:
    await call_recorder.process_audio_chunk(message_data)
    await call_recorder.log_conversation(message_data)
```

## 🔧 **Opciones adicionales:**

### **Opción 2: Grabación desde Twilio (Servidor)**
```python
# Para grabar directamente desde Twilio, agregar en webhook:
@app.post("/webhook")
async def webhook(request: Request):
    # ... código existente ...
    
    # Habilitar grabación en Twilio
    call_accept["record"] = True
    call_accept["recording_channels"] = "dual"  # Ambos canales
```

### **Opción 3: Convertir audio a WAV:**
```python
def convert_audio_to_wav(audio_file_path, output_wav_path):
    """Convierte el audio binario a WAV"""
    import wave
    
    with open(audio_file_path, 'rb') as audio_file:
        audio_data = audio_file.read()
    
    # Configuración de audio (ajustar según OpenAI)
    sample_rate = 24000  # Hz
    channels = 1  # Mono
    sample_width = 2  # 16-bit
    
    with wave.open(output_wav_path, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data)
```

## 📁 **Administración de grabaciones:**

### **Limpiar grabaciones antiguas:**
```python
import os
from datetime import datetime, timedelta

def cleanup_old_recordings(days_old=30):
    """Elimina grabaciones más antiguas que X días"""
    cutoff_date = datetime.now() - timedelta(days=days_old)
    
    for file in os.listdir("recordings"):
        if file.endswith("_summary.txt"):
            # Extraer timestamp del nombre
            timestamp_str = file.split("_")[0]
            file_date = datetime.strptime(timestamp_str, "%Y%m%d")
            
            if file_date < cutoff_date:
                base_name = file.replace("_summary.txt", "")
                # Eliminar todos los archivos relacionados
                for ext in ["_conversation.json", "_audio.bin", "_summary.txt"]:
                    file_path = f"recordings/{base_name}{ext}"
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"🗑️ Eliminado: {file_path}")
```

## ⚡ **Rendimiento:**

- **Espacio en disco**: ~1-2MB por minuto de conversación
- **CPU**: Mínimo impacto, solo procesa JSON y escribe archivos
- **Memoria**: Los chunks de audio se mantienen en memoria hasta el final de la llamada

## 🔐 **Seguridad:**

- Las grabaciones contienen información sensible
- Considerar encriptación para datos en reposo
- Implementar autenticación en los endpoints `/recordings`
- Cumplir con regulaciones de privacidad (GDPR, etc.)

¡Tu sistema de grabación está listo para usar! 🎉