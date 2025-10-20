from database import (
    listar_usuarios,
    obtener_examenes_medicos,
    obtener_cita_examen_medico,
    obtener_usuario,
    crear_cita,
    verificar_disponibilidad_citas,
    obtener_citas_activas_usuario,
    eliminar_cita
)

from email_helper import send_email_with_file
from rag_functions import search_general_exam_info, search_info_about_the_lab


tools = [
    {
        "type": "function",
        "name": "listar_usuarios",
        "description": "Lista todos los usuarios registrados en la base de datos. Retorna información completa de cada usuario incluyendo identificación, nombre, apellido, correo, dirección y fechas de creación/actualización.",
        "parameters": {
            "type": "object",
            "properties": {

            },
        }
    },
    {
        "type": "function",
        "name": "obtener_usuario",
        "description": "Obtiene la información completa de un usuario específico mediante su número de identificación (cédula). Retorna datos personales como nombre, apellido, correo, dirección y fechas de registro.",
        "parameters": {
            "type": "object",
            "properties": {
                "identificacion": {
                    "type": "integer",
                    "description": "Número de identificación (cédula) del usuario a consultar. Debe ser un número entero válido"
                },
            },
            "required": ["identificacion"]
        }
    },
    {
        "type": "function",
        "name": "obtener_examenes_medicos",
        "description": "Consulta todos los exámenes médicos asociados a un usuario específico. Retorna lista completa de exámenes con sus resúmenes, nombres de archivos PDF y fechas de creación.",
        "parameters": {
            "type": "object",
            "properties": {
                "id_usuario": {
                    "type": "integer",
                    "description": "ID interno del usuario en la base de datos (no confundir con identificación/cédula). Este ID se obtiene primero consultando el usuario por su cédula"
                }
            },
            "required": ["id_usuario"]
        }
    },
    {
        "type": "function",
        "name": "obtener_cita_examen_medico",
        "description": "Consulta todas las citas de exámenes médicos programadas para un usuario específico. Retorna información detallada de cada cita incluyendo fecha, ciudad, dirección, examen asociado y fechas de creación/actualización.",
        "parameters": {
            "type": "object",
            "properties": {
                "id_usuario": {
                    "type": "integer",
                    "description": "ID interno del usuario en la base de datos (no confundir con identificación/cédula). Este ID se obtiene primero consultando el usuario por su cédula"
                }
            },
            "required": ["id_usuario"]
        }
    },
    {
        "type": "function",
        "name": "send_email_with_file",
        "description": "Envía un correo electrónico con archivos adjuntos de exámenes médicos desde la carpeta docs. Los archivos disponibles son PDFs de exámenes (orina, sangre, etc.) que se adjuntan automáticamente según los nombres proporcionados.",
        "parameters": {
            "type": "object",
            "properties": {
                "to_email": {
                    "type": "string",
                    "description": "Dirección de correo electrónico del destinatario. Debe ser un email válido con formato usuario@dominio.com"
                },
                "subject": {
                    "type": "string",
                    "description": "Asunto del correo electrónico. Debe ser descriptivo del contenido que se está enviando"
                },
                "body": {
                    "type": "string",
                    "description": "Cuerpo del mensaje del correo electrónico en texto plano. Contenido principal que verá el destinatario"
                },
                "files_to_attach": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Lista de nombres de archivos PDF a adjuntar desde la carpeta docs/. Ejemplos: ['examen_orina_1.pdf', 'examen_sangre_2.pdf']. Solo se adjuntarán archivos que existan en la carpeta docs"
                }
            },
            "required": ["to_email", "subject", "body", "files_to_attach"]
        }
    },
    {
        "type": "function",
        "name": "search_general_exam_info",
        "description": "Busca información general sobre un examen médico específico. Utiliza búsqueda vectorial para encontrar detalles sobre qué hace un examen, sus características, preparación requerida, etc. NO es para consultar exámenes de un usuario específico, sino para obtener información descriptiva sobre tipos de exámenes disponibles.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Pregunta o descripción del examen médico sobre el cual se desea obtener información. Ejemplo: '¿Qué mide el examen de glucosa?' o 'información sobre hemograma completo'"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Número de resultados a retornar. Por defecto se recomienda entre 3-5 resultados para obtener información completa"
                }
            },
            "required": ["query", "num_results"]
        }
    },
    {
        "type": "function",
        "name": "search_info_about_the_lab",
        "description": "Busca información general sobre el laboratorio que NO esté relacionada con exámenes médicos específicos. Utiliza búsqueda vectorial sobre documentos del laboratorio para responder preguntas sobre servicios, ubicaciones, horarios, políticas, procedimientos generales, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Pregunta sobre información general del laboratorio. Ejemplo: 'horarios de atención', 'ubicaciones disponibles', 'cómo agendar una cita', 'políticas de privacidad'"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Número de resultados a retornar. Por defecto se recomienda entre 3-5 resultados para obtener información completa"
                }
            },
            "required": ["query", "num_results"]
        }
    },
    {
        "type": "function",
        "name": "verificar_disponibilidad_citas",
        "description": "Verifica si hay disponibilidad para agendar una cita en una fecha, hora y ciudad específicas. Muestra cuántas citas ya están programadas en ese horario. IMPORTANTE: Usar SIEMPRE antes de crear una cita para confirmar disponibilidad con el usuario.",
        "parameters": {
            "type": "object",
            "properties": {
                "fecha_cita": {
                    "type": "string",
                    "description": "Fecha y hora exacta a verificar en formato '2025-10-15 10:30 AM' o similar. Debe incluir día, hora y minutos"
                },
                "ciudad": {
                    "type": "string",
                    "description": "Ciudad donde se verificará disponibilidad. Ejemplos: 'Barranquilla', 'Bogotá', 'Medellín', 'Cali'"
                }
            },
            "required": ["fecha_cita", "ciudad"]
        }
    },
    {
        "type": "function",
        "name": "obtener_citas_activas_usuario",
        "description": "Consulta todas las citas activas y programadas de un usuario específico usando su user_id (NO cédula). IMPORTANTE: Primero usar listar_usuarios para obtener el user_id del usuario. Útil cuando el usuario pregunta '¿qué citas tengo?' o 'consultar mis citas programadas'.",
        "parameters": {
            "type": "object",
            "properties": {
                "id_usuario": {
                    "type": "integer",
                    "description": "ID interno del usuario (user_id) obtenido con listar_usuarios. NO es la cédula."
                }
            },
            "required": ["id_usuario"]
        }
    },
    {
        "type": "function",
        "name": "crear_cita",
        "description": "Crea y confirma una nueva cita médica para un usuario registrado usando su user_id (NO cédula). IMPORTANTE: (1) Primero usar listar_usuarios para obtener user_id, (2) Usar verificar_disponibilidad_citas, (3) Confirmar con el usuario, (4) Crear cita. La función valida disponibilidad internamente y envía correo de confirmación automáticamente.",
        "parameters": {
            "type": "object",
            "properties": {
                "id_usuario": {
                    "type": "integer",
                    "description": "ID interno del usuario (user_id) obtenido con listar_usuarios. NO es la cédula."
                },
                "fecha_cita": {
                    "type": "string",
                    "description": "Fecha y hora de la cita en formato '2025-10-15 10:30 AM' o similar. Asegurarse que hay disponibilidad"
                },
                "tipo_examen": {
                    "type": "string",
                    "description": "Tipo de examen médico a realizar. Ejemplos: 'Hemograma completo', 'Glucosa en ayunas', 'Examen de orina', etc."
                },
                "ciudad": {
                    "type": "string",
                    "description": "Ciudad donde se realizará el examen. Ejemplos: 'Barranquilla', 'Bogotá', 'Medellín', 'Cali'"
                }
            },
            "required": ["id_usuario", "fecha_cita", "tipo_examen", "ciudad"]
        }
    },
    {
        "type": "function",
        "name": "eliminar_cita",
        "description": "Elimina una cita médica previamente programada usando su ID de cita. IMPORTANTE: (1) Primero usar obtener_citas_activas_usuario para mostrar las citas del usuario y obtener el ID, (2) Confirmar con el usuario qué cita desea eliminar, (3) Ejecutar la eliminación. La función elimina permanentemente la cita de la base de datos.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "ID único de la cita que se desea eliminar. Este ID se obtiene consultando las citas activas del usuario"
                }
            },
            "required": ["id"]
        }
    }
]


available_functions = {
    "listar_usuarios": listar_usuarios,
    "obtener_usuario": obtener_usuario,
    "obtener_examenes_medicos": obtener_examenes_medicos,
    "obtener_cita_examen_medico": obtener_cita_examen_medico,
    "send_email_with_file": send_email_with_file,
    "search_general_exam_info": search_general_exam_info,
    "search_info_about_the_lab": search_info_about_the_lab,
    "verificar_disponibilidad_citas": verificar_disponibilidad_citas,
    "obtener_citas_activas_usuario": obtener_citas_activas_usuario,
    "crear_cita": crear_cita,
    "eliminar_cita": eliminar_cita
}