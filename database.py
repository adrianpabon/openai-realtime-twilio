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
        SELECT * FROM usuarios WHERE identificacion = ?
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


def listar_usuarios(db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM usuarios
    ''')
    return cursor.fetchall()

