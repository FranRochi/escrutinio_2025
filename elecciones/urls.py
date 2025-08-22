# elecciones/urls.py
from django.urls import path
from django.shortcuts import redirect
from . import views
from elecciones import views as v

# Import del export: si el módulo existe, lo usamos; si no, el proyecto igual levanta
try:
    from . import exports
    HAS_EXPORTS = True
except Exception:
    exports = None
    HAS_EXPORTS = False

urlpatterns = [
    path('', lambda request: redirect('login'), name='root'),

    # Login propio
    path('login/', views.login_view, name='login'),
    path('accounts/login/', views.login_view, name='accounts_login'),
    path('logout/', views.logout_view, name='logout'),

    # Panel operador
    path('panel_operador/', views.panel_operador, name='panel_operador'),
    path('operador/mesa/<int:mesa_id>/datos/', views.mesa_datos, name='mesa_datos'),

    # Guardado
    path('operador/guardar-votos/', views.guardar_votos, name='guardar_votos'),

    # === NUEVO PANEL LIVIANO (tabs DIPUTADOS / CONCEJALES) ===
    path('panel/', views.panel_dashboard, name='panel_dashboard'),                       # vista HTML
    path('api/panel/subcomandos/', views.api_subcomandos, name='api_subcomandos'),
    path('api/panel/summary/', views.api_summary, name='api_summary'),                   # JSON tabla central
    path('api/panel/metadata/', views.api_metadata, name='api_metadata'),                # JSON % escrutado
    path('api/panel/online-users/', views.api_online_users, name='api_online_users'),    # JSON usuarios online
    path('api/panel/summary-both/', views.api_summary_both, name='api_summary_both'),

    # PANEL DE GRAFICOS TOTALES
    path("panel/graficos/", views.panel_graficos, name="panel_graficos"),

    #PANEL DE RESULTADOS
    path('panel/resultados/', views.panel_resultados, name='panel_resultados'),
    path('api/panel/summary_both/', v.api_summary_both, name='api_summary_both'),

]

# Ruta de export a Excel solo si existe el módulo/función
if HAS_EXPORTS and hasattr(exports, 'export_summary_excel'):
    urlpatterns += [
        path('export/summary.xlsx', exports.export_summary_excel, name='export_summary_excel'),
    ]
