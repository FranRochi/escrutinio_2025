from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.core.cache import caches

from api.models import Padron, VotoLog, IntegrationOutbox, Adherente

cache = caches["default"]

def _k_mark(mesa_id: int, orden: str) -> str:
    return f"voto:mesa:{mesa_id}:orden:{orden}"

def _k_pending_set(mesa_id: int) -> str:
    return f"pending:mesa:{mesa_id}"


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_outbox_row(self, outbox_id: int):
    """
    Procesa una fila del outbox: marcar_voto o eliminar_marcacion.
    """
    with transaction.atomic():
        ob = (
            IntegrationOutbox.objects.select_for_update(skip_locked=True)
            .filter(id=outbox_id)
            .first()
        )
        if not ob or ob.estado not in ("pending", "retry"):
            return

        ob.estado = "processing"
        ob.save(update_fields=["estado"])

        payload = ob.payload or {}
        try:
            mesa = int(payload.get("mesa"))
            orden = str(payload.get("orden")).zfill(3)
        except Exception as e:
            ob.estado = "error"
            ob.last_error = f"Payload inválido: {payload} ({e})"
            ob.save(update_fields=["estado", "last_error"])
            return

        accion = (payload.get("accion") or "SI").upper()
        user_id = payload.get("user_id")

        try:
            persona = Padron.objects.get(mesa=mesa, orden=orden)
        except Padron.DoesNotExist:
            ob.estado = "error"
            ob.last_error = f"No existe en padron mesa={mesa}, orden={orden}"
            ob.save(update_fields=["estado", "last_error"])
            return

        # ====================================
        # A) Marcar voto
        # ====================================
        if ob.evento == "marcar_voto" and accion == "SI":
            # 1. actualizar padrón
            Padron.objects.filter(id=persona.id).update(voto=True)

            # 2. actualizar adherente si existe
            Adherente.objects.filter(dni=persona.dni, sexo=persona.sexo).update(voto=True)

            # 3. log (idempotente)
            VotoLog.objects.get_or_create(
                mesa=mesa,
                orden=orden,
                defaults={
                    "dni": persona.dni,
                    "usuario_id": user_id,
                    "accion": "SI",
                    "ts": timezone.now(),
                },
            )

        # ====================================
        # B) Eliminar marcación
        # ====================================
        elif ob.evento == "eliminar_marcacion" or accion == "NO":
            # 1. actualizar padrón
            Padron.objects.filter(id=persona.id).update(voto=False)

            # 2. actualizar adherente si existe
            Adherente.objects.filter(dni=persona.dni, sexo=persona.sexo).update(voto=False)

            # 3. log (NO siempre se registra)
            VotoLog.objects.create(
                mesa=mesa,
                orden=orden,
                dni=persona.dni,
                usuario_id=user_id,
                accion="NO",
                ts=timezone.now(),
            )

        else:
            ob.estado = "error"
            ob.last_error = f"Evento desconocido: {ob.evento} (accion={accion})"
            ob.save(update_fields=["estado", "last_error"])
            return

        # ====================================
        # Limpiar redis
        # ====================================
        client = cache.client.get_client(write=True)
        client.srem(_k_pending_set(mesa), orden)
        # no borramos _k_mark para "SI" porque asegura idempotencia
        if accion == "NO":
            client.delete(_k_mark(mesa, orden))

        # Finalizar
        ob.estado = "done"
        ob.processed_at = timezone.now()
        ob.save(update_fields=["estado", "processed_at"])


@shared_task
def flush_outbox(batch_size: int = 500):
    """
    Levanta hasta batch_size filas pendientes y las procesa en paralelo.
    """
    ids = list(
        IntegrationOutbox.objects
        .filter(estado__in=("pending", "retry"))
        .order_by("id")
        .values_list("id", flat=True)[:batch_size]
    )
    for ob_id in ids:
        process_outbox_row.delay(ob_id)
