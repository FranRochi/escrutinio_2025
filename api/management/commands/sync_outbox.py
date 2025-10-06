# api/management/commands/sync_outbox.py
from django.core.management.base import BaseCommand
from api.outbox_pull import sync_from_registro

class Command(BaseCommand):
    help = "Sincroniza outbox desde Registro"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument("--max-batches", type=int, default=10)

    def handle(self, *args, **opts):
        ok, msg = sync_from_registro(limit=opts["limit"], max_batches=opts["max_batches"])
        self.stdout.write(msg)
        if not ok:
            self.stderr.write(msg)
            # exit code != 0 para que el bucle lo registre como error
            raise SystemExit(1)
