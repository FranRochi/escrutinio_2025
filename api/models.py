# api/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone

class Padron(models.Model):
    dni = models.CharField(max_length=12)
    sexo = models.CharField(max_length=1)  # 'M'/'F'
    ayn = models.CharField(max_length=255, null=True, blank=True)
    domicilio = models.CharField(max_length=255, null=True, blank=True)
    edad = models.IntegerField(null=True, blank=True)  # <-- agregado
    subcomando = models.IntegerField(null=True, blank=True)
    seccion = models.IntegerField(null=True, blank=True)
    circuito = models.CharField(max_length=10, null=True, blank=True)
    mesa = models.IntegerField(db_index=True)
    orden = models.CharField(max_length=3, db_index=True)  # '001'
    id_escuela = models.IntegerField(null=True, blank=True)
    escuela = models.CharField(max_length=255, null=True, blank=True)
    domicilio_escuela = models.CharField(max_length=255, null=True, blank=True)
    voto = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'padron'
        managed = False            # YA existe en MySQL
        unique_together = (('mesa', 'orden'),)

    def __str__(self):
        return f"{self.ayn} - Mesa {self.mesa} / Orden {self.orden}"


# --- VotoLog ---
class VotoLog(models.Model):
    mesa = models.IntegerField()
    orden = models.CharField(max_length=3)
    dni = models.CharField(max_length=12)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    accion = models.CharField(max_length=2, choices=[('SI','SI'),('NO','NO')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'voto_logs'
        # Si ya creaste la tabla a mano, dejá:
        managed = False
        indexes = [models.Index(fields=['mesa', 'orden'])]

class IntegrationOutbox(models.Model):
    EVENTO_CHOICES = [('voto_registrado', 'voto_registrado')]
    ESTADO_CHOICES = [('pending','pending'), ('sent','sent'), ('error','error')]

    evento = models.CharField(max_length=64, choices=EVENTO_CHOICES)
    payload = models.JSONField()  # {"dni":"...", "sexo":"M", "accion":"SI"}
    estado = models.CharField(max_length=16, choices=ESTADO_CHOICES, default='pending')
    intentos = models.PositiveIntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integrations_outbox'
        indexes = [models.Index(fields=['estado'])]

class Adherente(models.Model):
    dni = models.CharField(max_length=10)
    sexo = models.CharField(
        max_length=1,
        choices=[('M', 'Masculino'), ('F', 'Femenino'), ('X', 'No binario')]
    )
    apellido = models.CharField(max_length=100, null=True, blank=True)
    nombre = models.CharField(max_length=100, null=True, blank=True)
    domicilio = models.CharField(max_length=255, null=True, blank=True)
    circuito = models.CharField(max_length=100, null=True, blank=True)
    cod_localidad = models.CharField(max_length=20, blank=True, null=True)
    apellido_nombre = models.CharField(max_length=255, blank=True, null=True)

    voto = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    creado_por = models.BigIntegerField(null=True, blank=True)
    creado_por_nombre = models.CharField(max_length=255, null=True, blank=True)
    creado_en = models.DateTimeField()   # MySQL lo genera por default

    referente = models.BigIntegerField(null=True, blank=True)
    referente_nombre = models.CharField(max_length=255, null=True, blank=True)

    email = models.EmailField(blank=True, null=True)
    celular = models.CharField(max_length=20, blank=True, null=True)
    localidad_donde_reside = models.CharField(max_length=100, blank=True, null=True)
    localidad_donde_vota = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = "adherentes"
        managed = False
        indexes = [models.Index(fields=["dni", "sexo"])]
        constraints = []

    def __str__(self):
        return f"{self.apellido}, {self.nombre} ({self.dni})"


