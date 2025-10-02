import sqlite3
import sqlite3
import os 
from typing import Optional, Tuple, List, Dict, Any, Union
import re



DB_NAME = "database.db"
def init_db(db_path: str = DB_NAME):

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cedula TEXT UNIQUE,
            nombre TEXT,
            apellido TEXT,
            correo TEXT,
            direccion TEXT,
            time_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            time_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS examenes_medicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario INTEGER,
            time_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resumen TEXT,
            nombre_archivo TEXT,
            FOREIGN KEY (id_usuario) REFERENCES usuarios (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cita_examen_medico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario INTEGER,
            fecha_cita TIMESTAMP,
            time_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            time_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            id_examen_medico INTEGER,
            ciudad TEXT,
            direccion_usuario TEXT,
            FOREIGN KEY (id_usuario) REFERENCES usuarios (id),
            FOREIGN KEY (id_examen_medico) REFERENCES examenes_medicos (id)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"Database initialized successfully in {db_path}")

def seed_example_data(db_path: str = DB_NAME):
    import random
    from datetime import datetime
    import glob

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure DB is initialized
    init_db(db_path)

    users = [
        ("10000001", "Kenneth", "Barrios", "kennethbarriosq@gmail.com", "Direccion 1"),
        ("10000002", "Adrian", "Pabon", "adrianpabonmendoza@gmail.com", "Direccion 2"),
        ("10000003", "Christian", "Quintero", "christianq@uninorte.edu.co", "Direccion 3"),
        ("10000004", "Samuel", "Solano", "samdace19@gmail.com", "Direccion 4"),
    ]

    # Insert users if not exist
    user_ids = {}
    for cedula, nombre, apellido, correo, direccion in users:
        cursor.execute("SELECT id FROM usuarios WHERE cedula = ?", (cedula,))
        row = cursor.fetchone()
        if row:
            user_ids[cedula] = row[0]
        else:
            cursor.execute(
                "INSERT INTO usuarios (cedula, nombre, apellido, correo, direccion) VALUES (?, ?, ?, ?, ?)",
                (cedula, nombre, apellido, correo, direccion),
            )
            user_ids[cedula] = cursor.lastrowid

    # Gather docs
    docs_dir = os.path.join(os.path.dirname(__file__), "docs")
    pdf_paths = sorted(glob.glob(os.path.join(docs_dir, "*.pdf")))

    # Helper to random date in September 2025
    def random_september_2025_date():
        day = random.randint(1, 30)
        hour = random.randint(8, 17)
        minute = random.choice([0, 15, 30, 45])
        return datetime(2025, 9, day, hour, minute, 0).isoformat(" ")

    # Seed exams and appointments per user
    for cedula, user_id in user_ids.items():
        for pdf_path in pdf_paths:
            file_name = os.path.basename(pdf_path)
            resumen = f"Resultado del examen asociado al archivo {file_name}"
            cursor.execute(
                "INSERT INTO examenes_medicos (id_usuario, resumen, nombre_archivo) VALUES (?, ?, ?)",
                (user_id, resumen, file_name),
            )
            examen_id = cursor.lastrowid

            fecha_cita = random_september_2025_date()
            ciudad = random.choice(["Barranquilla", "Bogotá", "Medellín", "Cali"]) 
            direccion_usuario = random.choice([
                "Calle 1 #2-3", "Carrera 45 # 67-89", "Av. 30 # 15-20", "Transv. 9 # 10-11"
            ])
            cursor.execute(
                """
                INSERT INTO cita_examen_medico (
                    id_usuario, fecha_cita, id_examen_medico, ciudad, direccion_usuario
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, fecha_cita, examen_id, ciudad, direccion_usuario),
            )

    conn.commit()
    conn.close()
    print("Example data seeded successfully.")

if __name__ == "__main__":
    init_db()
    seed_example_data()