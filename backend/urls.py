from django.contrib import admin
from django.urls import path, include 
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),

    # 🔓 PUBLICA: service worker en la RAÍZ
    path(
        'sw-votos.js',
        TemplateView.as_view(
            template_name='panel_operador/sw-votos.js',
            content_type='application/javascript'
        ),
        name='sw-votos'
    ),

    path('', include('elecciones.urls')),  # Incluye las URLs de la aplicación 'elecciones'

]
