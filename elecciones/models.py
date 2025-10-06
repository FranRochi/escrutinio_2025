# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone   # NEW
from django.db.models import Q #NEW

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
    circuito = models.ForeignKey(
        "Circuito",   # 👈 así evitamos problemas de orden
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
        ('marcador', 'Marcador'),
        ('subcomando', 'Responsable de Subcomando'),
        ('computos', 'Cómputos'), 
    ]
    role = models.CharField(max_length=20, choices=ROLES, default='operador')

    escuela = models.ForeignKey(
        Escuela,
        on_delete=models.SET_NULL,
        related_name="usuarios",
        null=True,
        blank=True,
    )

    subcomando = models.ForeignKey(
        Subcomando,
        on_delete=models.SET_NULL,
        related_name="usuarios",
        null=True,
        blank=True,
    )

    celular = models.CharField(max_length=50, null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True, db_index=True)

    @property
    def online(self):
        if not self.last_seen:
            return False
        return (timezone.now() - self.last_seen).total_seconds() <= 120

    @property
    def mesas_visibles(self):
        """Devuelve las mesas que el usuario puede ver según su rol."""
        if self.is_superuser or self.role in ('admin', 'computos'):
            return Mesa.objects.all()

        if self.role == 'subcomando' and self.subcomando_id:
            return Mesa.objects.filter(escuela__subcomando_id=self.subcomando_id)

        if self.escuela_id:
            return Mesa.objects.filter(escuela_id=self.escuela_id)

        return Mesa.objects.none()

    def puede_editar_mesa(self, mesa):
        """Chequea si el usuario puede editar una mesa concreta."""
        if self.is_superuser or self.role in ('admin', 'computos'):
            return True
        if self.role == 'subcomando' and self.subcomando_id:
            return mesa.escuela.subcomando_id == self.subcomando_id
        if self.escuela_id:
            return mesa.escuela_id == self.escuela_id
        return False


# ----------------------------
# ---------MARCADOR-----------
# ----------------------------

class Marcador(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mesas_habilitadas')
    mesa = models.ForeignKey(Mesa, on_delete=models.CASCADE, related_name='marcadores')
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Marcador"
        verbose_name_plural = "Marcadores"
        # Evita duplicar exactamente la misma pareja user/mesa
        constraints = [
            models.UniqueConstraint(fields=['user', 'mesa'], name='uniq_user_mesa'),
            # Clave: SOLO puede haber 1 activo por usuario
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(activo=True),
                name='uniq_user_activo'
            ),
        ]

    def __str__(self):
        return f"{self.user.username} → Mesa {self.mesa.numero_mesa} ({'activo' if self.activo else 'inactivo'})"
    
class MarcacionTemp(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="marcaciones_temp")
    mesa = models.ForeignKey(Mesa, on_delete=models.CASCADE, related_name="marcaciones_temp")
    orden = models.CharField(max_length=3)
    dni = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=['user','mesa','orden'], name='uniq_marcacion_temp')
        ]


# ----------------------------
# --SECCIONES-----CIRUITOS----
# ----------------------------
class Seccion(models.Model):
    nombre_seccion = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Sección"
        verbose_name_plural = "Secciones"

    def __str__(self):
        return self.nombre_seccion


class Circuito(models.Model):
    codigo_circuito = models.CharField(max_length=10, unique=True)
    seccion = models.ForeignKey(Seccion, on_delete=models.CASCADE, related_name="circuitos")

    class Meta:
        verbose_name = "Circuito"
        verbose_name_plural = "Circuitos"

    def __str__(self):
        return f"Circ. {self.codigo_circuito} ({self.seccion})"

