from database import (
    listar_usuarios,
    obtener_examenes_medicos,
    obtener_cita_examen_medico,
    obtener_usuario
)

from email_helper import send_email_with_file


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
    }
]


available_functions = {
    "listar_usuarios": listar_usuarios,
    "obtener_usuario": obtener_usuario,
    "obtener_examenes_medicos": obtener_examenes_medicos,
    "obtener_cita_examen_medico": obtener_cita_examen_medico,
    "send_email_with_file": send_email_with_file    
}