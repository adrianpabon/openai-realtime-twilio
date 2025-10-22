'''
La idea es tener tres tablas

Tabla usuarios:

- id autoincrement (key)
- cedula UNIQUE 
- nombre
- apellido
- correo
-  direccion
- time creacion
- time update


Tabla examenes_medicos
- id 
- id_usuario
- time_creacion
- resumen (text)
- nombre_archivo


Tabla cita_examen_medico
- id 
- id_usuario
- fecha_cita
- time_creacion
- time_update
- id_examen_medico
- ciudad
- direccion_usuario


'''

import sqlite3
import os 
from typing import Optional, Tuple, List, Dict, Any, Union
import re

DB_NAME = "database.db"



def obtener_usuario(identificacion: int, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM usuarios WHERE cedula = ?
    ''', (identificacion,))
    return cursor.fetchone()

def crear_usuario(identificacion: int, nombre: str, apellido: str, correo: str, direccion: str, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO usuarios (identificacion, nombre, apellido, correo, direccion) VALUES (?, ?, ?, ?, ?)
    ''', (identificacion, nombre, apellido, correo, direccion))
    conn.commit()
    conn.close()
    return cursor.lastrowid


def actualizar_usuario(identificacion: int, nombre: str, apellido: str, correo: str, direccion: str, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE usuarios SET nombre = ?, apellido = ?, correo = ?, direccion = ? WHERE identificacion = ?
    ''', (nombre, apellido, correo, direccion, identificacion))
    conn.commit()
    conn.close()
    return cursor.rowcount

def eliminar_usuario(identificacion: int, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM usuarios WHERE identificacion = ?
    ''', (identificacion,))
    conn.commit()
    conn.close()
    return cursor.rowcount  

def obtener_examenes_medicos(id_usuario: int, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM examenes_medicos WHERE id_usuario = ?
    ''', (id_usuario,))
    return cursor.fetchall()

def crear_examen_medico(id_usuario: int, resumen: str, nombre_archivo: str, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO examenes_medicos (id_usuario, resumen, nombre_archivo) VALUES (?, ?, ?)
    ''', (id_usuario, resumen, nombre_archivo))
    conn.commit()
    conn.close()
    return cursor.lastrowid
    
def actualizar_examen_medico(id: int, resumen: str, nombre_archivo: str, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE examenes_medicos SET resumen = ?, nombre_archivo = ? WHERE id = ?
    ''', (resumen, nombre_archivo, id))
    conn.commit()
    conn.close()
    return cursor.rowcount
    
def eliminar_examen_medico(id: int, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM examenes_medicos WHERE id = ?
    ''', (id,))
    conn.commit()
    conn.close()
    return cursor.rowcount
    
def obtener_cita_examen_medico(id_usuario: int, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM cita_examen_medico WHERE id_usuario = ?
    ''', (id_usuario,))
    return cursor.fetchall()
    
def crear_cita_examen_medico(id_usuario: int, fecha_cita: str, id_examen_medico: int, ciudad: str, direccion_usuario: str, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO cita_examen_medico (id_usuario, fecha_cita, id_examen_medico, ciudad, direccion_usuario) VALUES (?, ?, ?, ?, ?)
    ''', (id_usuario, fecha_cita, id_examen_medico, ciudad, direccion_usuario))
    conn.commit()
    conn.close()
    return cursor.lastrowid

def verificar_disponibilidad_citas(fecha_cita: str, ciudad: str, db_path: str = DB_NAME) -> Dict[str, Any]:
    """
    Verifica si hay disponibilidad en una fecha y ciudad específica.
    Muestra las citas ya programadas en ese horario y ciudad.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Buscar citas en la misma ciudad y fecha/hora
        cursor.execute('''
            SELECT
                c.id,
                c.fecha_cita,
                c.ciudad,
                u.nombre,
                u.apellido
            FROM cita_examen_medico c
            JOIN usuarios u ON c.id_usuario = u.id
            WHERE c.ciudad = ? AND c.fecha_cita = ?
        ''', (ciudad, fecha_cita))

        citas_existentes = []
        for row in cursor.fetchall():
            citas_existentes.append({
                "cita_id": row["id"],
                "fecha_cita": row["fecha_cita"],
                "ciudad": row["ciudad"],
                "paciente": f"{row['nombre']} {row['apellido']}"
            })

        # Si hay muchas citas (más de 5 en el mismo horario), considerar no disponible
        disponible = len(citas_existentes) < 5

        return {
            "disponible": disponible,
            "ciudad": ciudad,
            "fecha_cita": fecha_cita,
            "citas_programadas": len(citas_existentes),
            "mensaje": f"{'✅ Hay disponibilidad' if disponible else '❌ No hay disponibilidad'} para {fecha_cita} en {ciudad}. Citas programadas: {len(citas_existentes)}"
        }

    except Exception as e:
        return {
            "disponible": False,
            "error": str(e)
        }
    finally:
        conn.close()


def obtener_citas_activas_usuario(id_usuario: int, db_path: str = DB_NAME) -> Dict[str, Any]:
    """
    Obtiene todas las citas activas/futuras de un usuario específico por su user_id.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Buscar usuario por ID
        cursor.execute('SELECT id, nombre, apellido, cedula FROM usuarios WHERE id = ?', (id_usuario,))
        usuario = cursor.fetchone()

        if not usuario:
            return {
                "success": False,
                "error": "Usuario no encontrado",
                "id_usuario": id_usuario
            }

        # Obtener todas las citas del usuario
        cursor.execute('''
            SELECT
                c.id,
                c.fecha_cita,
                c.ciudad,
                c.direccion_usuario,
                c.time_creacion
            FROM cita_examen_medico c
            WHERE c.id_usuario = ?
            ORDER BY c.fecha_cita DESC
        ''', (id_usuario,))

        citas = []
        for row in cursor.fetchall():
            citas.append({
                "cita_id": row["id"],
                "fecha_cita": row["fecha_cita"],
                "ciudad": row["ciudad"],
                "direccion": row["direccion_usuario"],
                "fecha_creacion": row["time_creacion"]
            })

        return {
            "success": True,
            "nombre_paciente": f"{usuario['nombre']} {usuario['apellido']}",
            "cedula": usuario['cedula'],
            "id_usuario": id_usuario,
            "total_citas": len(citas),
            "citas": citas,
            "mensaje": f"Se encontraron {len(citas)} citas para {usuario['nombre']} {usuario['apellido']}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        conn.close()


def crear_cita(id_usuario: int, fecha_cita: str, tipo_examen: str, ciudad: str, db_path: str = DB_NAME) -> Dict[str, Any]:
    """
    Crea una cita médica para un usuario (por user_id) y envía correo de confirmación.
    Retorna información completa de la cita creada.
    """
    from email_helper import send_email_with_file

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Verificar si el usuario existe
        cursor.execute('SELECT id, nombre, apellido, correo, cedula FROM usuarios WHERE id = ?', (id_usuario,))
        usuario = cursor.fetchone()

        if not usuario:
            return {
                "success": False,
                "error": "Usuario no encontrado. Debe registrarse primero.",
                "id_usuario": id_usuario
            }

        nombre = usuario[1]
        apellido = usuario[2]
        correo = usuario[3]
        cedula = usuario[4]
        nombre_completo = f"{nombre} {apellido}"

        # Verificar disponibilidad primero
        disponibilidad = verificar_disponibilidad_citas(fecha_cita, ciudad, db_path)

        if not disponibilidad.get("disponible"):
            return {
                "success": False,
                "error": f"No hay disponibilidad para {fecha_cita} en {ciudad}",
                "citas_programadas": disponibilidad.get("citas_programadas", 0)
            }

        # Crear la cita
        cursor.execute('''
            INSERT INTO cita_examen_medico (id_usuario, fecha_cita, ciudad, direccion_usuario)
            VALUES (?, ?, ?, ?)
        ''', (id_usuario, fecha_cita, ciudad, "Por confirmar - Se contactará para confirmar dirección"))

        cita_id = cursor.lastrowid
        conn.commit()

        # Enviar correo de confirmación
        subject = f"Confirmación de Cita - Pasteur Laboratorios Clínicos"
        body = f"""Estimado/a {nombre_completo}:

Reciba un cordial saludo de parte de Pasteur Laboratorios Clínicos.

Le confirmamos que su cita ha sido agendada exitosamente con los siguientes detalles:

📋 DETALLES DE LA CITA:
• ID de Cita: #{cita_id}
• Paciente: {nombre_completo}
• Cédula: {cedula}
• Fecha y Hora: {fecha_cita}
• Tipo de Examen: {tipo_examen}
• Ciudad: {ciudad}
• Dirección: Se confirmará por teléfono

⏰ IMPORTANTE:
• Por favor llegue 15 minutos antes de su cita
• Traiga su documento de identidad
• Si requiere ayuno u otra preparación, se le informará previamente

📞 Si necesita cancelar o reprogramar su cita, por favor contacte a nuestro centro.

Quedamos atentos a cualquier inquietud.

Cordialmente,
Pasteur Laboratorios Clínicos
Más de 75 años cuidando su salud
"""

        try:
            # Enviar correo sin archivos adjuntos
            send_email_with_file(
                to_email=correo,
                subject=subject,
                body=body,
                files_to_attach=[]
            )
            correo_enviado = True
        except Exception as email_error:
            print(f"Error enviando correo: {email_error}")
            correo_enviado = False

        return {
            "success": True,
            "cita_id": cita_id,
            "id_usuario": id_usuario,
            "cedula": cedula,
            "nombre": nombre_completo,
            "correo": correo,
            "fecha_cita": fecha_cita,
            "tipo_examen": tipo_examen,
            "ciudad": ciudad,
            "correo_enviado": correo_enviado,
            "mensaje": f"✅ Cita #{cita_id} creada exitosamente para {nombre_completo} el {fecha_cita} en {ciudad}. Confirmación enviada al correo {correo}."
        }

    except Exception as e:
        conn.rollback()
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        conn.close()

def obtener_cita_por_id(cita_id: int, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    """Obtiene los detalles completos de una cita por su ID"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            c.id,
            c.fecha_cita,
            c.ciudad,
            c.direccion_usuario,
            c.time_creacion,
            u.cedula as identificacion,
            u.nombre,
            u.apellido,
            u.correo
        FROM cita_examen_medico c
        JOIN usuarios u ON c.id_usuario = u.id
        WHERE c.id = ?
    ''', (cita_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "fecha_cita": row["fecha_cita"],
            "ciudad": row["ciudad"],
            "direccion": row["direccion_usuario"],
            "fecha_creacion": row["time_creacion"],
            "paciente": {
                "identificacion": row["identificacion"],
                "nombre": row["nombre"],
                "apellido": row["apellido"],
                "correo": row["correo"]
            }
        }
    return None

def listar_todas_citas(db_path: str = DB_NAME) -> List[Dict[str, Any]]:
    """Lista todas las citas con información del usuario"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            c.id,
            c.fecha_cita,
            c.ciudad,
            c.direccion_usuario,
            c.time_creacion,
            u.cedula as identificacion,
            u.nombre,
            u.apellido
        FROM cita_examen_medico c
        JOIN usuarios u ON c.id_usuario = u.id
        ORDER BY c.fecha_cita DESC
    ''')

    citas = []
    for row in cursor.fetchall():
        citas.append({
            "id": row["id"],
            "fecha_cita": row["fecha_cita"],
            "ciudad": row["ciudad"],
            "direccion": row["direccion_usuario"],
            "fecha_creacion": row["time_creacion"],
            "paciente_nombre": f"{row['nombre']} {row['apellido']}",
            "identificacion": row["identificacion"]
        })

    conn.close()
    return citas


def listar_usuarios(db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM usuarios
    ''')
    return cursor.fetchall()

def eliminar_cita(id: int, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM cita_examen_medico WHERE id = ?
    ''', (id,))
    conn.commit()
    conn.close()
    return cursor.rowcount

