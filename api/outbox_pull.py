# api/outbox_pull.py (Escrutinio)
import time
import logging
import requests
from django.conf import settings
from api.models import Padron, Adherente

log = logging.getLogger("sync")
REGISTRO_URL = settings.REGISTRO_BASE_URL.rstrip("/")

def sync_from_registro(limit: int = 200, max_batches: int = 10):
    """
    Trae pendientes desde Registro en tandas hasta 'max_batches' o
    hasta que no haya más items. Devuelve (ok, mensaje).
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "escrutinio-sync/1.0",
        "X-Registro-Sync-Token": settings.REGISTRO_OUTBOX_TOKEN,
    })

    start = time.monotonic()
    total_applied = 0
    fetched_batches = 0

    try:
        for _ in range(max_batches):
            r = session.get(f"{REGISTRO_URL}/api/outbox/pending", params={"limit": limit}, timeout=5)
            if not r.ok:
                msg = f"Error consultando pending: HTTP {r.status_code}"
                log.error(msg)
                return False, msg

            data = r.json()
            ops = data.get("items", [])
            fetched_batches += 1
            if not ops:
                break  # nada más para traer

            applied_ids = []
            for op in ops:
                payload = op["payload"]
                mesa = payload["mesa"]
                orden = payload["orden"]
                dni = payload["dni"]
                accion = payload["accion"]

                voto = (accion == "SI")
                # idempotente: update directo
                Padron.objects.filter(mesa=mesa, orden=orden).update(voto=voto)
                Adherente.objects.filter(dni=dni).update(voto=voto)

                applied_ids.append(op["op_id"])

            # ACK sólo lo aplicado
            if applied_ids:
                ack = session.post(f"{REGISTRO_URL}/api/outbox/ack/", json={"ops": applied_ids}, timeout=5)
                if not ack.ok:
                    msg = f"ACK falló: HTTP {ack.status_code} - {ack.text[:200]}"
                    log.error(msg)
                    # No devolvemos False: si falla el ACK, se van a re-aplicar en la próxima, pero es idempotente.
                    # Devolvemos ok=True pero avisamos.
                    total_applied += len(applied_ids)
                    dur = time.monotonic() - start
                    log.warning("sync_outbox applied=%d fetched_batches=%d dur=%.3fs (ACK FALLÓ)",
                                total_applied, fetched_batches, dur)
                    return True, f"Aplicados {total_applied}, ACK falló"

            total_applied += len(applied_ids)

        dur = time.monotonic() - start
        log.info("sync_outbox applied=%d fetched_batches=%d dur=%.3fs",
                 total_applied, fetched_batches, dur)
        return True, f"Aplicados {total_applied} cambios"

    except Exception as e:
        msg = f"Excepción en sync_from_registro: {e}"
        log.exception(msg)
        return False, msg
