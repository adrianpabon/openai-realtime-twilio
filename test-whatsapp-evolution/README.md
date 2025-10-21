# WhatsApp Bot con OpenAI - Evolution API

Este módulo implementa un bot de WhatsApp inteligente para Pasteur Laboratorios Clínicos que utiliza la API de OpenAI con capacidad de function calling para responder automáticamente a mensajes de clientes.

## 🚀 Características

- **Procesamiento inteligente de mensajes** usando GPT-4 Turbo
- **Function Calling** para ejecutar acciones específicas:
  - Listar y buscar usuarios
  - Consultar exámenes médicos
  - Obtener información de citas
  - Enviar exámenes por correo
  - Búsqueda de información sobre exámenes (RAG)
  - Búsqueda de información del laboratorio (RAG)
  - Verificar disponibilidad de citas
  - Crear y eliminar citas
- **Gestión de historial de conversación** para contexto en las respuestas
- **Respuestas automáticas** personalizadas y profesionales
- **Integración con Evolution API** para WhatsApp

## 📋 Requisitos Previos

1. **Python 3.8+**
2. **OpenAI API Key** - Configurada en `.env`
3. **Evolution API** - Instancia configurada y funcionando
4. **Redis** - Para las funciones RAG
5. **Base de datos** - SQLite con los datos de usuarios y exámenes (ubicada en el directorio raíz del proyecto)

> **Nota sobre la Base de Datos**: El webhook automáticamente usa la base de datos `database.db` del directorio raíz del proyecto. No necesitas copiarla a `test-whatsapp-evolution/`.

## 🔧 Configuración

### 1. Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con:

```env
OPENAI_API_KEY=tu_api_key_aquí
```

### 2. Configuración de Evolution API

En `webhook.py`, actualiza las siguientes constantes:

```python
EVOLUTION_API_URL = "https://tu-evolution-api.com"
EVOLUTION_API_KEY = "tu_api_key"
INSTANCE_NAME = "nombre_de_tu_instancia"
```

### 3. Instalación de Dependencias

Las dependencias ya están incluidas en `requirements.txt` del proyecto principal:

```bash
pip install -r requirements.txt
```

Principales dependencias:
- `openai` - Para la API de OpenAI
- `fastapi` - Framework web
- `httpx` - Cliente HTTP asíncrono
- `pydantic` - Validación de datos
- `python-dotenv` - Gestión de variables de entorno

### 4. Configuración de la Base de Datos

El webhook usa automáticamente la base de datos del directorio raíz del proyecto. Si aún no has inicializado la base de datos, ejecuta desde la raíz del proyecto:

```bash
# Desde el directorio raíz (openai-realtime-twilio)
python init_db.py
```

Esto creará `database.db` con las tablas necesarias:
- `usuarios` - Información de pacientes
- `examenes_medicos` - Resultados de exámenes
- `cita_examen_medico` - Citas programadas

El sistema automáticamente detecta y usa esta base de datos cuando se ejecuta desde `test-whatsapp-evolution/`.

## 🎯 Cómo Funciona

### Flujo de Procesamiento de Mensajes

1. **Recepción del Webhook**
   - Evolution API envía un webhook cuando llega un mensaje
   - El endpoint `/webhook/evolution` recibe el evento

2. **Gestión del Historial**
   - Se obtienen los últimos 5 mensajes de la conversación
   - Se construye un historial de contexto para OpenAI

3. **Procesamiento con OpenAI**
   - Se envía el historial y el mensaje actual a GPT-4 Turbo
   - El modelo decide si necesita usar alguna herramienta (function calling)
   - Si hay function calls, se ejecutan usando `FunctionManager`

4. **Ejecución de Funciones**
   - Las funciones se ejecutan de forma asíncrona
   - Los resultados se envían de vuelta a OpenAI
   - OpenAI genera una respuesta final basada en los resultados

5. **Respuesta al Usuario**
   - La respuesta final se envía por WhatsApp usando Evolution API
   - Se guarda en el historial para futuras conversaciones

### System Prompt

El bot utiliza un system prompt detallado basado en `realtime_config.py` pero adaptado para mensajes de texto. El prompt incluye:

- **Personalidad**: Juliana, asistente profesional y cálida de Pasteur
- **Contexto de la empresa**: Historia, servicios, tecnología
- **Instrucciones de uso de herramientas**: Cuándo y cómo usar cada función
- **Reglas de conversación**: Tono, formato, estructura de respuestas
- **Manejo de situaciones especiales**: Errores, escalación, etc.

## 🛠️ Funciones Disponibles (Function Calling)

### Gestión de Usuarios
- `listar_usuarios()` - Lista todos los usuarios
- `obtener_usuario(identificacion)` - Obtiene un usuario por cédula

### Gestión de Exámenes
- `obtener_examenes_medicos(id_usuario)` - Consulta exámenes de un usuario
- `send_email_with_file(...)` - Envía exámenes por correo

### Gestión de Citas
- `obtener_cita_examen_medico(id_usuario)` - Consulta citas de un usuario
- `verificar_disponibilidad_citas(fecha_cita, ciudad)` - Verifica disponibilidad
- `crear_cita(...)` - Crea una nueva cita
- `eliminar_cita(id)` - Elimina una cita
- `obtener_citas_activas_usuario(id_usuario)` - Lista citas activas

### Información General (RAG)
- `search_general_exam_info(query, num_results)` - Busca info sobre exámenes
- `search_info_about_the_lab(query, num_results)` - Busca info del laboratorio

## 🚦 Inicio del Servidor

### Antes de Iniciar

Asegúrate de que:
1. La base de datos esté inicializada (ejecutar `python init_db.py` desde la raíz)
2. El archivo `.env` esté configurado en la raíz con `OPENAI_API_KEY`
3. Redis esté corriendo (para funciones RAG)

### Desarrollo

```bash
cd test-whatsapp-evolution
python webhook.py
```

Al iniciar, deberías ver:
```
📊 Usando base de datos: /ruta/completa/database.db
🔧 Funciones de database detectadas: ['crear_cita', 'eliminar_cita', 'listar_usuarios', ...]
INFO:     Started server process...
```

El sistema detecta automáticamente qué funciones necesitan acceso a la base de datos.

El servidor se iniciará en `http://0.0.0.0:8000`

### Producción con Uvicorn

```bash
cd test-whatsapp-evolution
uvicorn webhook:app --host 0.0.0.0 --port 8000 --reload
```

## 📡 Endpoints Disponibles

### POST `/webhook/evolution`
Recibe webhooks de Evolution API

**Eventos soportados:**
- `messages.upsert` - Mensajes nuevos o actualizados
- `connection.update` - Actualizaciones de conexión

### GET `/messages/{remote_jid}`
Obtiene mensajes de un chat específico

**Parámetros:**
- `remote_jid` - ID del chat (ej: `573001234567@s.whatsapp.net`)
- `limit` - Cantidad de mensajes (default: 5)
- `page` - Página (default: 1)

### GET `/chats`
Lista todos los chats en memoria local

### GET `/`
Estado del servidor y endpoints disponibles

## 🔍 Logs y Debug

El sistema imprime logs detallados:

```
✓ Mensaje recibido de Usuario
🤖 Procesando con OpenAI...
📝 Mensajes enviados: 3
🔧 Se detectaron 2 function calls
   📞 Ejecutando: listar_usuarios
   ✓ Resultado: [...]
   📞 Ejecutando: obtener_examenes_medicos
   ✓ Resultado: [...]
🤖 Segunda llamada a OpenAI con resultados de funciones...
✓ Respuesta generada: Hola! 👋...
📤 Enviando respuesta por WhatsApp...
✓ Mensaje enviado exitosamente
✓ Conversación completada exitosamente
```

## 🔒 Seguridad

- **Validación de mensajes**: Solo responde a mensajes de usuarios (no responde a sus propios mensajes)
- **Validación de contenido**: Ignora mensajes sin texto válido (imágenes, stickers, etc. sin caption)
- **Manejo de errores**: Todos los errores se capturan y registran sin detener el servicio
- **Variables de entorno**: API keys y credenciales en `.env` (no en código)

## 📱 Configuración del Webhook en Evolution API

1. Accede a tu instancia de Evolution API
2. Configura el webhook URL: `https://tu-servidor.com/webhook/evolution`
3. Habilita los eventos:
   - `messages.upsert`
   - `connection.update`

## 🎨 Personalización

### Modificar el System Prompt

Edita la función `get_text_assistant_prompt()` en `webhook.py` para ajustar:
- Personalidad del asistente
- Tono de las respuestas
- Instrucciones específicas
- Reglas de conversación

### Agregar Nuevas Funciones

1. Define la función en `functions.py`
2. Agrega la descripción al array `tools` en `functions.py`
3. Registra la función en `available_functions`
4. Actualiza el system prompt con instrucciones de uso

### Cambiar el Modelo de OpenAI

En `process_message_with_openai()`, cambia:

```python
model="gpt-4-turbo-preview"  # o "gpt-4o", "gpt-3.5-turbo", etc.
```

## 🐛 Solución de Problemas

### Error: "no such table: usuarios"
Este error indica que la base de datos no está inicializada correctamente.

**Solución:**
```bash
# Desde el directorio raíz del proyecto
cd ..
python init_db.py
```

El sistema usa automáticamente la base de datos del directorio raíz. Al iniciar el webhook, deberías ver:
```
📊 Usando base de datos: /ruta/completa/database.db
```

### Error: "OpenAI API Key not found"
- Verifica que existe `.env` en la raíz del proyecto con `OPENAI_API_KEY`
- Asegúrate de que `load_dotenv()` se está ejecutando
- El `.env` debe estar en el directorio raíz, no en `test-whatsapp-evolution/`

### Error: "Function not found"
- Verifica que la función esté registrada en `available_functions` (en `functions.py`)
- Revisa que el nombre coincida exactamente con el tool

### No responde a mensajes
- Verifica que el webhook esté configurado en Evolution API
- Revisa los logs para ver si llegan los eventos
- Confirma que `from_me` sea `False` (no responde a sus propios mensajes)
- Verifica que el mensaje tenga texto válido (no solo imágenes o stickers)

### Error ejecutando funciones de database
- Verifica que `database.db` exista en el directorio raíz
- Ejecuta `python init_db.py` desde la raíz si es necesario
- Revisa que el mensaje de inicio muestre la ruta correcta: `📊 Usando base de datos: ...`

### Error en funciones RAG (search_general_exam_info, search_info_about_the_lab)
- Confirma que Redis esté corriendo: `redis-cli ping` (debería responder `PONG`)
- Verifica que los índices estén creados ejecutando los scripts en `scripts/`
- Revisa que `OPENAI_API_KEY` esté configurada (RAG usa embeddings de OpenAI)

## 📊 Ejemplo de Conversación

**Usuario:** Hola, quiero consultar mis exámenes

**Bot:** Hola! 👋 Soy Juliana, asistente virtual de Pasteur Laboratorios. Con gusto te ayudo a consultar tus exámenes.

Para ayudarte mejor, ¿me puedes decir tu nombre completo por favor?

**Usuario:** Juan Pérez

**Bot:** Perfecto Juan. Déjame buscar tus exámenes disponibles...

*[Ejecuta: listar_usuarios(), obtener_examenes_medicos()]*

Encontré los siguientes exámenes disponibles:

📋 *Examen de Sangre Completo*
- Fecha: 2025-10-15
- Estado: Disponible

📋 *Examen de Orina*
- Fecha: 2025-10-15
- Estado: Disponible

¿Quieres que te los envíe por correo?

## 📄 Licencia

Este módulo es parte del proyecto Pasteur Laboratorios Clínicos.

## 👥 Soporte

Para soporte o preguntas, contacta al equipo de desarrollo.

