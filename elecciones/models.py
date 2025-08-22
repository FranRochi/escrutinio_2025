# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone   # NEW

# ----------------------------
# PADRÓN / GEO
# ----------------------------
class Subcomando(models.Model):
    nombre_subcomando = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = "Subcomando"
        verbose_name_plural = "Subcomandos"

    def __str__(self):
        return self.nombre_subcomando


class Escuela(models.Model):
    nombre_escuela = models.CharField(max_length=255)
    subcomando = models.ForeignKey(
        Subcomando,
        on_delete=models.SET_NULL,
        related_name="escuelas",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Escuela"
        verbose_name_plural = "Escuelas"

    def __str__(self):
        return f"Escuela {self.nombre_escuela}"


class Mesa(models.Model):
    numero_mesa = models.IntegerField(unique=True, db_index=True)  # CHANGE: index
    escuela = models.ForeignKey(
        Escuela,
        on_delete=models.CASCADE,
        related_name="mesas",
    )
    escrutada = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Mesa"
        verbose_name_plural = "Mesas"

    def __str__(self):
        return f"Mesa {self.numero_mesa}"


# ----------------------------
# ELECCIONES
# ----------------------------
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
    numero_lista = models.IntegerField(primary_key=True)
    nombre_partido = models.CharField(max_length=255)
    sigla = models.CharField(max_length=10)
    orden = models.IntegerField(null=True, blank=True, db_index=True, db_column='orden')

    class Meta:
        # OJO: los NULL en 'orden' van primero en ASC; si querés “NULLS LAST” lo resolvemos en la query.
        ordering = ['orden', 'numero_lista']

    def __str__(self):
        return f"{self.nombre_partido} ({self.sigla}) - N° Lista {self.numero_lista}"


class CargoPostulacion(models.Model):
    nombre_postulacion = models.CharField(max_length=255)
    tipo = models.CharField(max_length=50)  # "Ejecutivo" o "Legislativo"
    eleccion = models.ForeignKey(Eleccion, on_delete=models.CASCADE, related_name="cargos")

    def __str__(self):
        return f"{self.nombre_postulacion} ({self.tipo}) - Elección: {self.eleccion.nombre_eleccion}"


class PartidoPostulacion(models.Model):
    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='partidos_postulados')
    cargo_postulacion = models.ForeignKey(CargoPostulacion, on_delete=models.CASCADE, related_name='cargos_postulados')

    class Meta:
        indexes = [  # NEW: índice compuesto para sumar más rápido por cargo
            models.Index(fields=['cargo_postulacion', 'partido']),
        ]

    def __str__(self):
        return f"{self.partido.nombre_partido} se postula a {self.cargo_postulacion.nombre_postulacion}"


# ----------------------------
# VOTOS
# ----------------------------
class VotoMesaCargo(models.Model):
    mesa = models.ForeignKey(Mesa, on_delete=models.CASCADE, related_name="votos_cargo")
    partido_postulacion = models.ForeignKey(PartidoPostulacion, on_delete=models.CASCADE, related_name="votos")
    votos = models.PositiveIntegerField()

    class Meta:
        unique_together = ('mesa', 'partido_postulacion')
        indexes = [  # NEW: índices que usan tus agregaciones
            models.Index(fields=['partido_postulacion']),
            models.Index(fields=['mesa']),
        ]

    def __str__(self):
        return f"{self.votos} votos a {self.partido_postulacion} en Mesa {self.mesa.numero_mesa}"


class VotoMesaEspecial(models.Model):
    # Sugerencia: alinearlo con lo que usa el front/validación
    TIPO_VOTO = [
        ('blanco', 'En blanco'),
        ('impugnado', 'Impugnado'),
    ]
    mesa = models.ForeignKey(Mesa, on_delete=models.CASCADE, related_name="votos_especiales")
    cargo_postulacion = models.ForeignKey(
        CargoPostulacion,
        on_delete=models.CASCADE,
        related_name="votos_especiales",
        null=True,
        blank=True
    )
    tipo = models.CharField(max_length=20, choices=TIPO_VOTO)
    votos = models.PositiveIntegerField()

    class Meta:
        unique_together = ('mesa', 'cargo_postulacion', 'tipo')
        indexes = [  # NEW
            models.Index(fields=['cargo_postulacion']),
            models.Index(fields=['mesa']),
        ]


class ResumenMesa(models.Model):
    mesa = models.OneToOneField(Mesa, on_delete=models.CASCADE, related_name="resumen")
    electores_votaron = models.PositiveIntegerField()
    sobres_encontrados = models.PositiveIntegerField()
    diferencia = models.IntegerField()
    escrutada = models.BooleanField(default=False)

    def __str__(self):
        return f"Resumen de {self.mesa}"


# ----------------------------
# USUARIOS
# ----------------------------
class User(AbstractUser):
    ROLES = [
        ('operador', 'Operador'),
        ('panelista', 'Panelista'),
        ('admin', 'Administrador'),
    ]
    role = models.CharField(max_length=20, choices=ROLES, default='operador')

    escuela = models.ForeignKey(
        Escuela,
        on_delete=models.SET_NULL,
        related_name="usuarios",
        null=True,
        blank=True,
    )

    # NEW: para estado online
    last_seen = models.DateTimeField(null=True, blank=True, db_index=True)

    @property
    def mesas_visibles(self):
        if self.escuela_id:
            return Mesa.objects.filter(escuela_id=self.escuela_id)
        return Mesa.objects.none()

    @property
    def online(self):  # útil en admin o plantillas
        if not self.last_seen:
            return False
        # 2 minutos de tolerancia
        return (timezone.now() - self.last_seen).total_seconds() <= 120
