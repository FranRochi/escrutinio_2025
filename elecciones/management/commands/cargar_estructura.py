from django.core.management.base import BaseCommand
from elecciones.models import Circuito, Escuela, Mesa
import random

class Command(BaseCommand):
    help = 'Carga circuitos, escuelas y mesas con datos aleatorios'

    def handle(self, *args, **kwargs):
        random.seed(42)

        circuitos = []
        numeros_circuito = random.sample(range(100, 999), 5)

        for num in sorted(numeros_circuito):
            circuito, created = Circuito.objects.get_or_create(numero_circuito=num)
            if created:
                self.stdout.write(f"Circuito {num} creado.")
            else:
                self.stdout.write(f"Circuito {num} ya existía.")
            circuitos.append(circuito)

        nombres_posibles = [
            "Esc. Belgrano", "Esc. Sarmiento", "Esc. San Martín", "Esc. Moreno", "Esc. Rosas",
            "Esc. Malvinas", "Esc. San Juan", "Esc. Eva Perón", "Esc. Alberdi", "Esc. Güemes",
            "Esc. Brown", "Esc. Mitre", "Esc. Rawson", "Esc. Rivadavia", "Esc. Urquiza",
            "Esc. Madres de Plaza", "Esc. Kirchner", "Esc. Illia", "Esc. Pellegrini", "Esc. Azurduy",
            "Esc. Fangio", "Esc. Leloir", "Esc. Balseiro", "Esc. Grierson", "Esc. Alfonsín"
        ]


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

        self.stdout.write(self.style.SUCCESS("✅ Circuitos, escuelas y mesas cargadas correctamente."))
