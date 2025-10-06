# elecciones/urls.py
from django.urls import path
from django.shortcuts import redirect
from . import views
from elecciones import views as v

# 👇 Import del refresh de JWT
from rest_framework_simplejwt.views import TokenRefreshView

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

    # 👉 Nueva ruta para refresh de tokens
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Panel operador
    path('panel_operador/', views.panel_operador, name='panel_operador'),
    path('operador/mesa/<int:mesa_id>/datos/', views.mesa_datos, name='mesa_datos'),

    # Para panelistas/admins (solo lectura)
    path('panel/mesa/<int:mesa_id>/datos/', views.mesa_datos_panelista, name='mesa_datos_panelista'),

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

    # PANEL DE RESULTADOS
    path('panel/resultados/', views.panel_resultados, name='panel_resultados'),
    path('api/panel/summary_both/', v.api_summary_both, name='api_summary_both'),

    # SECCIONES / CIRCUITOS  
    path("api/panel/secciones/", views.api_secciones, name="api_secciones"),
    path("api/panel/circuitos/", views.api_circuitos, name="api_circuitos"),
    path("api/panel/circuitos_diputados/", views.api_circuitos_diputados, name="api_circuitos_diputados"),

    # paneles por secciones y circuitos
    path('panel/secciones', views.panel_secciones, name='panel_secciones'),
    path('panel/circuitos/', views.panel_circuitos, name='panel_circuitos'),

    path("api/panel/seccion/<str:nombre>/", views.api_seccion_detalle, name="api_seccion_detalle"),

    # PANEL DE USUARIOS
    path("panel/usuarios/", views.panel_usuarios, name="panel_usuarios"),
    path("api/panel/usuarios_tabla/", views.api_usuarios_tabla, name="api_usuarios_tabla"),

    path("export_adherentes_pdf/", views.export_adherentes_pdf, name="export_adherentes_pdf"),

    #EXCEL CIRCUITOS
    path("export/circuitos/", views.export_circuitos_excel, name="export_circuitos_excel"),
    path("export/circuitos_diputados/", views.export_circuitos_excel_diputados, name="export_circuitos_excel_diputados"),

    # EXCEL SUBCOMANDOS
    path("export/subcomandos/", views.export_subcomandos_excel, name="export_subcomandos_excel"),

    #PANEL DE SUBCOMANDOS
    path('panel/subcomandos/', views.panel_subcomandos, name='panel_subcomandos'),
    path("api/panel/subcomandos/", views.api_subcomandos, name="api_subcomandos"),
    path("api/panel/subcomando/<str:nombre>/", views.api_subcomando_detalle, name="api_subcomando_detalle"),
    path("api/panel/subcomandos_concejales/", views.api_subcomandos_concejales, name="api_subcomandos_concejales"),
    path("api/panel/subcomandos_diputados/", views.api_subcomandos_diputados, name="api_subcomandos_diputados"),

    # PANEL EXTRANJEROS
    path('panel/extranjeros/', views.panel_extranjeros, name='panel_extranjeros'),
    path("api/panel/subcomandos_extranjeros_concejales/", views.subcomandos_extranjeros_concejales, name="subcomandos_extranjeros_concejales"),
    path("api/panel/subcomandos_extranjeros_diputados/", views.subcomandos_extranjeros_diputados, name="subcomandos_extranjeros_diputados"),
    path("export/subcomandos_extranjeros/", views.export_subcomandos_extranjeros_excel, name="export_subcomandos_extranjeros_excel"),

    #DESCARGA EXCEL TOTAL MESAS
    path("export/mesas_por_cargo.xlsx", views.export_mesas_por_cargo_excel, name="export_mesas_por_cargo_excel"),

]

# Ruta de export a Excel solo si existe el módulo/función
if HAS_EXPORTS and hasattr(exports, 'export_summary_excel'):
    urlpatterns += [
        path('export/summary.xlsx', exports.export_summary_excel, name='export_summary_excel'),
    ]
