import random
from myapp.models import Circuito, Escuela, Mesa  # Cambiá 'myapp' por el nombre real de tu app

nombres_posibles = [
    "Esc. Belgrano", "Esc. Sarmiento", "Esc. San Martín", "Esc. Moreno", "Esc. Rosas",
    "Esc. Malvinas", "Esc. San Juan", "Esc. Eva Perón", "Esc. Alberdi", "Esc. Güemes",
    "Esc. Brown", "Esc. Mitre", "Esc. Rawson", "Esc. Rivadavia", "Esc. Urquiza"
]

circuitos = list(Circuito.objects.all())  # O cualquier queryset válido

usados_nombres = set()
numero_escuela = 1
numero_mesa = 1001

for circuito in circuitos:
    cantidad_escuelas = random.randint(2, 4)
    for _ in range(cantidad_escuelas):
        if len(usados_nombres) == len(nombres_posibles):
            raise ValueError("No hay suficientes nombres únicos de escuelas.")

        while True:
            nombre = random.choice(nombres_posibles)
            if nombre not in usados_nombres:
                usados_nombres.add(nombre)
                break

        escuela = Escuela.objects.create(
            nombre_escuela=nombre,
            numero_escuela=numero_escuela,
            circuito=circuito
        )
        numero_escuela += 1

        for _ in range(7):
            Mesa.objects.create(
                numero_mesa=numero_mesa,
                escuela=escuela,
                circuito=circuito
            )
            numero_mesa += 1
