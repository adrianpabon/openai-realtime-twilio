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
from functions import tools
import locale

load_dotenv()

# Configurar la ruta de la base de datos al directorio raíz
DB_PATH = str(parent_dir / "database.db")
print(f"📊 Usando base de datos: {DB_PATH}")

app = FastAPI()

# Configuración de EvolutionAPI
EVOLUTION_API_URL = "https://evolution-api-production-827b.up.railway.app"
EVOLUTION_API_KEY = "8BF194C1A4C39A38A4EF7DEB99B49"
INSTANCE_NAME = "opti"

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

# Extraer automáticamente las funciones de database desde functions.py
# Estas son las funciones que se importan de database.py en functions.py
import database
DATABASE_FUNCTIONS = set()

# Obtener todas las funciones de database que están en available_functions
from functions import available_functions
for func_name, func in available_functions.items():
    # Verificar si la función viene del módulo database
    if hasattr(database, func_name):
        DATABASE_FUNCTIONS.add(func_name)

print(f"🔧 Funciones de database detectadas: {sorted(DATABASE_FUNCTIONS)}")

async def execute_function_with_db_path(function_name: str, arguments: str):
    """
    Wrapper que ejecuta funciones inyectando db_path cuando sea necesario
    Solo aplica a funciones que vienen del módulo database.py
    """
    # Parse argumentos
    kwargs = json.loads(arguments) if arguments else {}
    
    # Si es una función de database, agregar db_path
    if function_name in DATABASE_FUNCTIONS:
        kwargs['db_path'] = DB_PATH
        print(f"   💾 Agregando db_path a {function_name}")
    
    # Ejecutar usando el function manager
    result = await function_manager.execute_function(function_name, json.dumps(kwargs))
    return result

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
    Procesa un mensaje usando OpenAI API con function calling
    """
    try:
        # Preparar mensajes para OpenAI
        messages = [
            {"role": "system", "content": get_text_assistant_prompt()}
        ]
        
        # Agregar historial de conversación
        messages.extend(conversation_history)
        
        # Agregar mensaje actual del usuario
        messages.append({"role": "user", "content": user_message})
        
        print(f"\n🤖 Procesando con OpenAI...")
        print(f"📝 Mensajes enviados: {len(messages)}")
        
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
            model="gpt-4-turbo-preview",
            messages=messages,
            tools=openai_tools,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        
        # Si hay function calls, procesarlas
        if tool_calls:
            print(f"\n🔧 Se detectaron {len(tool_calls)} function calls")
            
            # Agregar la respuesta del asistente a los mensajes
            messages.append(response_message)
            
            # Ejecutar cada function call
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments
                
                print(f"   📞 Ejecutando: {function_name}")
                print(f"   📋 Argumentos: {function_args}")
                
                # Ejecutar la función con db_path inyectado
                try:
                    function_response = await execute_function_with_db_path(
                        function_name=function_name,
                        arguments=function_args
                    )
                    
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
                model="gpt-4-turbo-preview",
                messages=messages
            )
            
            final_message = second_response.choices[0].message.content
        else:
            # No hay function calls, usar la respuesta directa
            final_message = response_message.content
        
        print(f"\n✓ Respuesta generada: {final_message[:200]}...")
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
                    sender_name = "Usuario" if is_from_me else m.get("pushName", "Cliente")
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
    Ejemplo: /messages/573232257331@s.whatsapp.net?limit=10&page=1
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
