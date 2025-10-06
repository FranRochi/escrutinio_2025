import os
import sys
import django
import random
from faker import Faker

# 👉 Asegurar que /app esté en el PYTHONPATH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# Configuración Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from elecciones.models import (
    Circuito,
    Escuela,
    Mesa,
    Partido,
    PartidoPostulacion,
    VotoMesaCargo,
    Eleccion,
    CargoPostulacion,
)

fake = Faker("es_AR")

def run():
    # Cantidad de datos fake a crear
    N_CIRCUITOS = 5       # ⚡ podés subir a 100 o más
    N_ESCUELAS_POR_CIRC = 3
    N_MESAS_POR_ESC = 5
    PARTIDOS = ["FP", "AP", "EVEN", "SBA", "FTIT", "NA"]

    print("Creando elección y cargo...")
    eleccion, _ = Eleccion.objects.get_or_create(
        nombre_eleccion="Elección Fake",
        tipo="Ejecutiva"
    )
    cargo, _ = CargoPostulacion.objects.get_or_create(
        nombre_postulacion="Presidente",
        tipo="Ejecutiva",
        eleccion=eleccion
    )

    print("Creando partidos...")
    partidos_objs = {}
    for i, sigla in enumerate(PARTIDOS, start=1):
        partido, _ = Partido.objects.get_or_create(
            numero_lista=i,
            defaults={
                "nombre_partido": f"Partido {sigla}",
                "sigla": sigla,
            }
        )
        partidos_objs[sigla] = partido

    print("Creando circuitos, escuelas, mesas y votos...")
    mesa_numero = 1
    for i in range(N_CIRCUITOS):
        circ = Circuito.objects.create(codigo_circuito=f"{i:05d}", seccion_id=1)  
        # ⚠️ Ajustar seccion_id si no existe al menos 1 Seccion en tu DB

        for j in range(N_ESCUELAS_POR_CIRC):
            esc = Escuela.objects.create(
                circuito=circ,
                nombre_escuela=fake.company(),
                subcomando=None  # ⚠️ si tu modelo requiere, podés asignar uno existente
            )

            for k in range(N_MESAS_POR_ESC):
                mesa = Mesa.objects.create(
                    escuela=esc,
                    numero_mesa=mesa_numero,
                    escrutada=random.choice([True, False])
                )
                mesa_numero += 1

                # Generar votos por partido
                for sigla, partido in partidos_objs.items():
                    postulacion, _ = PartidoPostulacion.objects.get_or_create(
                        partido=partido,
                        cargo_postulacion=cargo
                    )
                    VotoMesaCargo.objects.create(
                        mesa=mesa,
                        partido_postulacion=postulacion,
                        votos=random.randint(0, 300)
                    )

    print("✅ Datos fake creados!")

if __name__ == "__main__":
    run()
