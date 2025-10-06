from django.core.management.base import BaseCommand
from api.models import IntegrationOutbox
from api.services import sync_voto_adherentes
import time

class Command(BaseCommand):
    help = "Reintenta enviar eventos pendientes a Adherentes"

    def handle(self, *args, **options):
        qs = IntegrationOutbox.objects.filter(estado='pending').order_by('created_at')[:200]
        for ev in qs:
            ok, err = sync_voto_adherentes(
                ev.payload.get('dni'),
                ev.payload.get('sexo'),
                ev.payload.get('accion')
            )
            if ok:
                ev.estado = 'sent'
                ev.last_error = None
            else:
                ev.intentos += 1
                ev.last_error = err
                if ev.intentos >= 5:
                    ev.estado = 'error'
            ev.save(update_fields=['estado','intentos','last_error','updated_at'])
            time.sleep(0.05)
