# elecciones/urls.py
from django.urls import path
from django.shortcuts import redirect
from . import views
from django.views.generic import TemplateView

urlpatterns = [
    path('', lambda request: redirect('login'), name='root'),

    # Login propio
    path('login/', views.login_view, name='login'),
    path('accounts/login/', views.login_view, name='accounts_login'),

    # Panel operador
    path('panel_operador/', views.panel_operador, name='panel_operador'),
    path('operador/mesa/<int:mesa_id>/datos/', views.mesa_datos, name='mesa_datos'),

    # Guardado
    path('operador/guardar-votos/', views.guardar_votos, name='guardar_votos'),

    # Panelista
    path('panel-panelista/', views.resultados_panelista, name='panel_panelista'),

    # API Login (JWT)
    path('api/login/', views.api_login_view, name='api_login'),
]
