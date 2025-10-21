import pandas as pd
import random
import re
from elecciones.models import User, Escuela

EXCEL_PATH  = "/app/responsables_edificio_OCT_2025.xlsx"
OUTPUT_PATH = "/app/credenciales_responsables_OCT.xlsx"

SPECIAL_CHARS = list("!#$%&/()=?¡¿/*°")

def normalizar_numero(x):
    """
    - Si viene float tipo 2214204884.0 -> '2214204884'
    - Si viene en notación científica -> sólo dígitos
    - Quita espacios, guiones, paréntesis, etc. Deja únicamente dígitos.
    """
    if pd.isna(x):
        return None
    # Floats exactos (terminan en .0)
    if isinstance(x, float):
        if x.is_integer():
            return str(int(x))
        # Si tuviera decimales reales (raro para DNI/celular), igual conservamos dígitos
        s = f"{x}"
        return re.sub(r"\D", "", s) or None
    s = str(x).strip()
    # Caso típico '2214204884.0' leído como str
    m = re.match(r"^(\d+)\.0+$", s)
    if m:
        return m.group(1)
    # General: dejar solo dígitos
    s = re.sub(r"\D", "", s)
    return s or None

# Leer aplicando normalización en columnas clave
df = pd.read_excel(
    EXCEL_PATH,
    converters={
        "dni": normalizar_numero,
        "celular": normalizar_numero,
        "id_escuela": lambda v: None if pd.isna(v) else int(v),
    }
)

creados = 0
actualizados = 0
sin_dni = []
duplicados_dni = []
credenciales = []
vistos = set()

for _, row in df.iterrows():
    dni = row.get("dni")
    if not dni:
        sin_dni.append(row.to_dict())
        continue

    if dni in vistos:
        duplicados_dni.append(row.to_dict())
    else:
        vistos.add(dni)

    id_escuela = row.get("id_escuela")
    nombre = row.get("nombre")
    nombre = "" if pd.isna(nombre) else str(nombre).strip()
    celular = row.get("celular")  # ya normalizado (solo dígitos) o None
    email = row.get("email")
    email = None if pd.isna(email) else str(email).strip()

    username = dni
    special  = random.choice(SPECIAL_CHARS)
    sufijo   = f"{random.randint(0, 99):02d}"
    password = f"{dni}{special}{sufijo}"

    escuela = None
    if id_escuela:
        try:
            escuela = Escuela.objects.get(id=id_escuela)
        except Escuela.DoesNotExist:
            escuela = None

    user = User.objects.filter(username=username).first()
    if user:
        user.first_name = nombre
        user.celular    = celular
        user.email      = email
        user.escuela    = escuela
        user.role       = "operador"
        user.set_password(password)
        user.save(update_fields=["first_name","celular","email","escuela","role","password"])
        actualizados += 1
    else:
        User.objects.create_user(
            username=username,
            password=password,
            role="operador",
            escuela=escuela,
            first_name=nombre,
            celular=celular,
            email=email,
        )
        creados += 1

    credenciales.append({
        "nombre": nombre,
        "dni": dni,
        "username": username,
        "password": password,
        "id_escuela": id_escuela,
        "escuela": escuela.nombre_escuela if escuela else None,
        "celular": celular,
        "email": email,
    })

pd.DataFrame(credenciales).to_excel(OUTPUT_PATH, index=False)

print(f"Usuarios creados: {creados}")
print(f"Usuarios actualizados: {actualizados}")
print(f"Responsables sin DNI: {len(sin_dni)}")
if sin_dni:
    print("Sin DNI:", sin_dni)
if duplicados_dni:
    print(f"DNI duplicados en Excel: {len(duplicados_dni)} (revisar)")
print(f"Credenciales exportadas a: {OUTPUT_PATH}")
