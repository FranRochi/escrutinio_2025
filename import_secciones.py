import csv
import pymysql

# Credenciales MySQL
DB_HOST = "escrutinio_db"   # nombre del servicio en docker-compose
DB_USER = "root"
DB_PASS = "1q2w3e4r!"
DB_NAME = "escrutinio"

CIRCUITOS_CSV = "/app/Circuitos.csv"
ESTABLECIMIENTOS_CSV = "/app/Establecimientos.csv"


# Mapeo: nro CSV -> id real en elecciones_seccion
SECCION_MAP = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    6: 6,
    7: 7,
    9: 8,  # en tu tabla, la 9na está con id=8
}

def importar_circuitos(conn):
    with open(CIRCUITOS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";", quotechar='"')
        next(reader, None)

        with conn.cursor() as cur:
            for row in reader:
                seccion_csv = int(row[0].strip())
                seccion_id = SECCION_MAP.get(seccion_csv)
                if not seccion_id:
                    print(f"⚠ Sección {seccion_csv} no encontrada en mapa, fila {row}")
                    continue

                cod_circ = row[1].strip()
                nombre = row[2].strip() if len(row) > 2 else None

                cur.execute("""
                    INSERT INTO elecciones_circuito (codigo_circuito, nombre_circuito, seccion_id)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        nombre_circuito = VALUES(nombre_circuito),
                        seccion_id = VALUES(seccion_id)
                """, (cod_circ, nombre, seccion_id))
        conn.commit()
    print("✔ Circuitos importados con mapa de secciones.")



def vincular_escuelas(conn):
    """
    Vincula cada escuela con su circuito según Establecimientos.csv
    """
    with open(ESTABLECIMIENTOS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";", quotechar='"')
        next(reader, None)

        with conn.cursor() as cur:
            for row in reader:
                # ID_ESTAB1 (2da col, con coma decimal → normalizamos)
                id_estab = int(float(row[1].replace(",", ".")))
                cod_circ = row[5].strip()

                cur.execute("SELECT id FROM elecciones_circuito WHERE codigo_circuito=%s", (cod_circ,))
                res = cur.fetchone()
                if not res:
                    print(f"⚠ Circuito {cod_circ} no encontrado para escuela {id_estab}")
                    continue
                circuito_id = res[0]

                cur.execute("""
                    UPDATE elecciones_escuela
                    SET circuito_id=%s
                    WHERE id=%s
                """, (circuito_id, id_estab))
        conn.commit()
    print("✔ Escuelas vinculadas con circuitos.")


if __name__ == "__main__":
    conn = pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME,
        charset="utf8mb4", cursorclass=pymysql.cursors.Cursor
    )

    try:
        importar_circuitos(conn)
        vincular_escuelas(conn)
    finally:
        conn.close()
