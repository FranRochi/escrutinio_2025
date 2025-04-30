from django.urls import path
from django.shortcuts import redirect
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    login_view,
    panel_operador,
    obtener_datos_mesa,
    api_login_view,
)

urlpatterns = [
    path('', lambda request: redirect('login')),  
    path('login/', login_view, name='login'),
    path('panel_operador/', panel_operador, name='panel_operador'),
    path('api/obtener_datos_mesa/', obtener_datos_mesa, name='obtener_datos_mesa'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/login/', api_login_view, name='api_login'),
]
