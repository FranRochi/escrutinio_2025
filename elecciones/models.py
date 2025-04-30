# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

class Circuito(models.Model):
    numero_circuito = models.IntegerField(unique=True)

    def __str__(self):
        return f"Circuito {self.numero_circuito}"

class Escuela(models.Model):
    nombre_escuela = models.CharField(max_length=255)
    numero_escuela = models.IntegerField(unique=True)
    circuito = models.ForeignKey(Circuito, on_delete=models.CASCADE, related_name="escuelas")

    def __str__(self):
        return f"Escuela {self.nombre_escuela} (N° {self.numero_escuela})"


class Mesa(models.Model):
    numero_mesa = models.IntegerField(unique=True)
    escuela = models.ForeignKey(Escuela, on_delete=models.CASCADE, related_name="mesas")
    circuito = models.ForeignKey(Circuito, on_delete=models.CASCADE, related_name="mesas_directas")  # nuevo campo

    def __str__(self):
        return f"Mesa {self.numero_mesa}"


#ELECCIONES

class Eleccion(models.Model):
    TIPO_ELECCION = [
        ('Ejecutiva', 'Ejecutiva'),
        ('Legislativa', 'Legislativa'),
    ]
    nombre_eleccion = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=TIPO_ELECCION)

    def __str__(self):
        return f"Elección: {self.nombre_eleccion} ({self.tipo})"

class Partido(models.Model):
    numero_lista = models.IntegerField(primary_key=True)  # El número de lista será la clave primaria
    nombre_partido = models.CharField(max_length=255)
    sigla = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.nombre_partido} ({self.sigla}) - N° Lista {self.numero_lista}"

class CargoPostulacion(models.Model):
    nombre_postulacion = models.CharField(max_length=255)  # Ejemplo: "Diputado Nacional", "Senador", etc.
    tipo = models.CharField(max_length=50)  # "Ejecutivo" o "Legislativo"
    eleccion = models.ForeignKey(Eleccion, on_delete=models.CASCADE, related_name="cargos")

    def __str__(self):
        return f"{self.nombre_postulacion} ({self.tipo}) - Elección: {self.eleccion.nombre_eleccion}"

class PartidoPostulacion(models.Model):
    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='partidos_postulados')
    cargo_postulacion = models.ForeignKey(CargoPostulacion, on_delete=models.CASCADE, related_name='cargos_postulados')
    

    def __str__(self):
        return f"{self.partido.nombre_partido} se postula a {self.cargo_postulacion.nombre_postulacion}"


#USUARIOS

class User(AbstractUser):
    ROLES = [
        ('operador', 'Operador'),
        ('panelista', 'Panelista'),
        ('admin', 'Administrador'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLES, default='operador')

    def __str__(self):
        return f"{self.username} - {self.get_role_display()}"