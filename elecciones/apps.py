from django.apps import AppConfig


class EleccionesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'elecciones'

    def ready(self):
        from . import signals  # NOQA