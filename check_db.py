import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

tables = ['usuarios', 'examenes_medicos', 'cita_examen_medico']

for table in tables:
    print(f'\n=== Tabla: {table} ===')

    # Mostrar estructura
    cursor.execute(f'PRAGMA table_info({table})')
    columns = cursor.fetchall()
    print('Columnas:')
    for col in columns:
        print(f'  - {col[1]} ({col[2]})')

    # Contar filas
    cursor.execute(f'SELECT COUNT(*) FROM {table}')
    count = cursor.fetchone()[0]
    print(f'Total de filas: {count}')

    # Mostrar datos si hay pocas filas
    if count > 0 and count <= 20:
        cursor.execute(f'SELECT * FROM {table}')
        rows = cursor.fetchall()
        print('Datos:')
        for row in rows:
            print(f'  {row}')
    elif count > 20:
        cursor.execute(f'SELECT * FROM {table} LIMIT 5')
        rows = cursor.fetchall()
        print('Primeras 5 filas:')
        for row in rows:
            print(f'  {row}')

conn.close()
