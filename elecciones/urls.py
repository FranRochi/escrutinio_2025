from django.urls import path
from django.shortcuts import redirect
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path('', lambda request: redirect('login')),  # Redirige a login
    path('login/', views.login_view, name='login'),
    path('panel_operador/', views.panel_operador, name='panel_operador'),
    path('accounts/login/', views.login_view, name='login'),

    
    # API JWT
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/login/', views.api_login_view, name='api_login'),

    path('api/obtener_datos_mesa/', views.obtener_datos_mesa, name='obtener_datos_mesa'),

    # Vistas del operador
    path("operador/", views.panel_operador, name="panel_operador"),
    path("operador/datos-mesa/<int:mesa_id>/", views.obtener_datos_mesa, name="datos_mesa"),
    path("operador/guardar-votos/<int:mesa_id>/", views.guardar_votos, name="guardar_votos"),
    path("guardar-votos/", views.guardar_votos, name="guardar_votos"),
    path("operador/guardar-votos/", views.guardar_votos, name="guardar_votos"),

    # Vistas panelistas
    path('panel-panelista/', views.resultados_panelista, name='panel_panelista'),

]
