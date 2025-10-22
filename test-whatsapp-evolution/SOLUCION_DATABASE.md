# Solución al Error "no such table: usuarios"

## 🔍 Problema Identificado

El error ocurría porque el webhook en `test-whatsapp-evolution/webhook.py` intentaba acceder a la base de datos usando una ruta relativa (`database.db`), pero el archivo de configuración `database.py` buscaba la base de datos en el directorio actual de ejecución.

```
sqlite3.OperationalError: no such table: usuarios
```

## ✅ Solución Implementada

### 1. Configuración de Ruta Absoluta

Se modificó `webhook.py` para usar una ruta absoluta a la base de datos del directorio raíz:

```python
import pathlib

# Agregar el directorio padre al path
parent_dir = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Configurar la ruta de la base de datos al directorio raíz
DB_PATH = str(parent_dir / "database.db")
print(f"📊 Usando base de datos: {DB_PATH}")
```

### 2. Detección Dinámica de Funciones de Base de Datos

El sistema detecta automáticamente qué funciones vienen del módulo `database.py` y están definidas en `functions.py`:

```python
# Extraer automáticamente las funciones de database
import database
from functions import available_functions

DATABASE_FUNCTIONS = set()

# Detectar qué funciones de available_functions vienen de database.py
for func_name, func in available_functions.items():
    if hasattr(database, func_name):
        DATABASE_FUNCTIONS.add(func_name)

print(f"🔧 Funciones de database detectadas: {sorted(DATABASE_FUNCTIONS)}")
```

Esto detectará automáticamente funciones como:
- `listar_usuarios`
- `obtener_usuario`
- `obtener_examenes_medicos`
- `obtener_cita_examen_medico`
- `crear_cita`
- `verificar_disponibilidad_citas`
- `obtener_citas_activas_usuario`
- `eliminar_cita`

### 3. Wrapper para Inyectar db_path

Se creó una función wrapper que inyecta automáticamente el parámetro `db_path` **solo** a las funciones detectadas:

```python
async def execute_function_with_db_path(function_name: str, arguments: str):
    """
    Wrapper que ejecuta funciones inyectando db_path cuando sea necesario
    Solo aplica a funciones que vienen del módulo database.py
    """
    kwargs = json.loads(arguments) if arguments else {}
    
    # Si es una función de database, agregar db_path
    if function_name in DATABASE_FUNCTIONS:
        kwargs['db_path'] = DB_PATH
        print(f"   💾 Agregando db_path a {function_name}")
    
    # Ejecutar usando el function manager
    result = await function_manager.execute_function(function_name, json.dumps(kwargs))
    return result
```

**Beneficios de la detección dinámica:**
- ✅ Automático - se adapta a cambios en `functions.py`
- ✅ Preciso - solo afecta funciones de database
- ✅ Mantenible - no hay lista hardcodeada que actualizar
- ✅ Seguro - no afecta funciones RAG ni de email

### 4. Actualización del Procesamiento de Mensajes

Se modificó `process_message_with_openai` para usar el nuevo wrapper:

```python
# Antes:
function_response = await function_manager.execute_function(
    function_name=function_name,
    arguments=function_args
)

# Después:
function_response = await execute_function_with_db_path(
    function_name=function_name,
    arguments=function_args
)
```

## 🎯 Resultado

Ahora el sistema:

1. ✅ Detecta automáticamente la ruta correcta de la base de datos
2. ✅ Usa la base de datos del directorio raíz independientemente de dónde se ejecute
3. ✅ Inyecta automáticamente el `db_path` a todas las funciones de base de datos
4. ✅ Muestra un mensaje de log al iniciar indicando qué base de datos está usando

## 📝 Logs Esperados

Al iniciar el webhook, deberías ver:

```
📊 Usando base de datos: /ruta/completa/a/openai-realtime-twilio/database.db
🔧 Funciones de database detectadas: ['crear_cita', 'eliminar_cita', 'listar_usuarios', 
    'obtener_cita_examen_medico', 'obtener_citas_activas_usuario', 'obtener_examenes_medicos', 
    'obtener_usuario', 'verificar_disponibilidad_citas']
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**Nota:** El mensaje `🔧 Funciones de database detectadas` confirma que el sistema detectó correctamente qué funciones necesitan `db_path`.

Y al procesar mensajes con function calling:

```
🤖 Procesando con OpenAI...
📝 Mensajes enviados: 6

🔧 Se detectaron 1 function calls
   📞 Ejecutando: listar_usuarios
   📋 Argumentos: {}
   💾 Agregando db_path a listar_usuarios  ← ¡Inyección automática!
   ✓ Resultado: {"usuarios": [...]}...

🤖 Segunda llamada a OpenAI con resultados de funciones...
✓ Respuesta generada: Hola! 👋...
📤 Enviando respuesta por WhatsApp...
✓ Mensaje enviado exitosamente
✓ Conversación completada exitosamente
```

**Nota:** El mensaje `💾 Agregando db_path` aparece **solo** para funciones de database, no para funciones RAG o de email.

## 🔧 Verificación

Para verificar que todo funciona correctamente:

1. **Verifica que la base de datos existe:**
   ```bash
   ls -la ../database.db
   ```

2. **Si no existe, inicialízala:**
   ```bash
   cd ..
   python init_db.py
   cd test-whatsapp-evolution
   ```

3. **Inicia el webhook y verifica el mensaje de log:**
   ```bash
   python webhook.py
   ```
   
   Deberías ver: `📊 Usando base de datos: /ruta/completa/database.db`

4. **Prueba enviando un mensaje al bot** por WhatsApp

## 📚 Archivos Modificados

- ✅ `test-whatsapp-evolution/webhook.py` - Configuración de rutas y wrapper
- ✅ `test-whatsapp-evolution/README.md` - Documentación actualizada
- ✅ `test-whatsapp-evolution/SOLUCION_DATABASE.md` - Este documento

## 🎉 Beneficios

1. **Simplicidad**: No necesitas copiar la base de datos a múltiples ubicaciones
2. **Consistencia**: Siempre usa la misma base de datos
3. **Mantenibilidad**: Un solo lugar para gestionar los datos
4. **Flexibilidad**: Funciona independientemente del directorio de ejecución
5. **Debugging**: Logs claros que muestran qué base de datos se está usando

## 🚀 Próximos Pasos

El sistema está listo para usar. Asegúrate de:

1. Tener la base de datos inicializada en el directorio raíz
2. Configurar `.env` con `OPENAI_API_KEY`
3. Configurar las credenciales de Evolution API
4. Iniciar Redis para las funciones RAG
5. Configurar el webhook en Evolution API

¡Listo para responder mensajes de WhatsApp con IA! 🎊

