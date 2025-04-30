from django.urls import path
from django.shortcuts import redirect
from . import views

urlpatterns = [
    path('', lambda request: redirect('login')),  
    path('login/', views.login_view, name='login'),
    path('panel_operador/', views.panel_operador, name='panel_operador'),
    path('api/obtener_datos_mesa/', views.obtener_datos_mesa, name='obtener_datos_mesa'),  # Nueva ruta
]
