import pandas as pd
import random
import re
from elecciones.models import User, Escuela

EXCEL_PATH = "/app/fiscales_generales.xlsx"
OUTPUT_PATH = "/app/credenciales_generadas.xlsx"
SPECIAL_CHARS = list("!#$%&/()=?¡¿/*°")

def limpiar_numero(valor):
    """
    Convierte el valor a string, quita .0, espacios y todo lo que no sea dígito.
    Devuelve None si queda vacío.
    """
    if pd.isna(valor):
        return None
    s = str(valor).strip()
    s = re.sub(r"\D", "", s)
    return s or None

df = pd.read_excel(EXCEL_PATH)

creados = 0
actualizados = 0
sin_dni = []
credenciales = []

for _, row in df.iterrows():
    dni = limpiar_numero(row.get("dni"))
    if not dni:
        sin_dni.append(row.to_dict()); continue

    id_escuela = row.get("id_escuela")
    try:
        id_escuela = int(id_escuela) if pd.notna(id_escuela) else None
    except Exception:
        id_escuela = None

    nombre = row.get("nombre")
    nombre = "" if pd.isna(nombre) else str(nombre).strip()

    celular = limpiar_numero(row.get("celular"))

    # username = DNI
    username = dni
    # password = DNI + (char especial) + (dos dígitos random)
    special = random.choice(SPECIAL_CHARS)
    rand_suffix = f"{random.randint(0, 99):02d}"
    password = f"{dni}{special}{rand_suffix}"

    escuela = None
    if id_escuela:
        try:
            escuela = Escuela.objects.get(id=id_escuela)
        except Escuela.DoesNotExist:
            escuela = None

    user = User.objects.filter(username=username).first()
    if user:
        user.first_name = nombre
        user.celular = celular
        user.escuela = escuela
        user.role = "operador"
        user.set_password(password)
        user.save(update_fields=["first_name","celular","escuela","role","password"])
        actualizados += 1
    else:
        User.objects.create_user(
            username=username,
            password=password,
            role="operador",
            escuela=escuela,
            first_name=nombre,
            celular=celular,
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
    })

# Exportar credenciales
pd.DataFrame(credenciales).to_excel(OUTPUT_PATH, index=False)

print(f"Usuarios creados: {creados}")
print(f"Usuarios actualizados: {actualizados}")
print(f"Fiscales sin DNI: {len(sin_dni)}")
if sin_dni:
    print("Fiscales sin DNI:", sin_dni)
print(f"Credenciales exportadas a: {OUTPUT_PATH}")
