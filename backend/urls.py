from django.contrib import admin
from django.urls import path, include 
from django.views.generic import TemplateView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

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

    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/', include('api.urls')),

]
