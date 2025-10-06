from django.shortcuts import render, redirect, get_object_or_404
from .models import Mesa, Subcomando, Partido, CargoPostulacion, PartidoPostulacion, VotoMesaCargo, VotoMesaEspecial, ResumenMesa, Seccion, Circuito
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseForbidden, JsonResponse
from collections import defaultdict
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime
from django.db.models import Sum, Count, Q
import logging
from django.db import transaction
from django.utils import timezone
from django.db.utils import OperationalError, ProgrammingError
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.utils.cache import add_never_cache_headers
from api.models import Padron, Adherente

@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username','').strip()
        password = request.POST.get('password','')
        next_url = request.POST.get('next') or request.GET.get('next')  # 👈 respetar next

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)

            # 1) Si vino ?next=..., respetarlo
            if next_url:
                return redirect(next_url)

            # 2) Si no hay next, redirección por rol
            if getattr(user, 'role', None) == 'operador':
                return redirect('panel_operador')
            elif getattr(user, 'role', None) == 'subcomando':
                return redirect('panel_operador')  # 👈 o si querés crear un panel propio
            elif getattr(user, 'role', None) == 'computos':   # 👈 NUEVO
                return redirect('panel_operador')
            elif getattr(user, 'role', None) == 'panelista':
                return redirect('panel_dashboard')
            elif getattr(user, 'role', None) == 'admin' or user.is_superuser:
                return redirect('panel_dashboard')
            else:
                return render(request, 'login.html', {
                    'error': True,
                    'mensaje': 'Rol desconocido'
                })

        # Credenciales inválidas
        return render(request, 'login.html', {'error': True})

    # GET
    return render(request, 'login.html')

#----- LOG OUT ------
@never_cache
@login_required
def logout_view(request):
    """
    Cierra la sesión del usuario, invalida la sesión en servidor
    y devuelve una pequeña página que ejecuta limpieza de caches del lado del cliente
    y redirige al login.
    """
    # Limpia la sesión del lado servidor
    request.session.flush()
    logout(request)

    # Pequeño HTML con JS para limpiar storage/caches del lado cliente.
    html = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Cerrando sesión…</title>
  <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0"/>
  <meta http-equiv="Pragma" content="no-cache"/>
  <meta http-equiv="Expires" content="0"/>
</head>
<body>
  <p>Cerrando sesión…</p>
  <script>
    (async function clearAll(){
      try {
        // local/session storage
        try { localStorage.clear(); } catch(e){}
        try { sessionStorage.clear(); } catch(e){}
        // IndexedDB (votos-offline)
        try {
          if (window.indexedDB) {
            const dbs = await indexedDB.databases?.() || [];
            for (const {name} of dbs) { try { await new Promise((ok,ko)=>{ const r = indexedDB.deleteDatabase(name); r.onsuccess=ok; r.onerror=ko; r.onblocked=ok; }); } catch(e){} }
          }
        } catch(e){}
        // Caches API
        try {
          if (window.caches?.keys) {
            const keys = await caches.keys();
            await Promise.all(keys.map(k => caches.delete(k)));
          }
        } catch(e){}
        // Service Workers
        try {
          if ('serviceWorker' in navigator) {
            const regs = await navigator.serviceWorker.getRegistrations();
            await Promise.all(regs.map(r => r.unregister()));
          }
        } catch(e){}
      } finally {
        window.location.replace("/login/"); // ajustá si tu ruta al login es distinta
      }
    })();
  </script>
</body>
</html>
    """.strip()

    resp = HttpResponse(html)
    add_never_cache_headers(resp)
    return resp
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def api_login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')

    from django.contrib.auth import authenticate
    user = authenticate(request, username=username, password=password)

    if user is not None:
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })
    else:
        return Response({"error": "Credenciales inválidas"}, status=401)


# views.py
@never_cache
@login_required
def panel_operador(request):
    if request.user.role not in ('operador', 'subcomando', 'computos', 'admin') and not request.user.is_superuser:
        return HttpResponseForbidden("No tenés permiso para acceder a este panel.")

    mesas = request.user.mesas_visibles.order_by('numero_mesa')

    partidos = Partido.objects.all()
    cargos = CargoPostulacion.objects.all().order_by('id')

    partidos_map = []
    for partido in partidos:
        candidatura_por_cargo = {}
        for candidatura in PartidoPostulacion.objects.filter(partido=partido):
            candidatura_por_cargo[candidatura.cargo_postulacion_id] = candidatura
        partidos_map.append({
            'partido': partido,
            'candidaturas': candidatura_por_cargo
        })

    tipos_voto_especial = ['blanco', 'impugnado']

    return render(request, 'panel_operador/panel_operador.html', {
        'mesas': mesas,
        'partidos': partidos,
        'cargos': cargos,
        'partidos_map': partidos_map,
        'tipos_voto_especial': tipos_voto_especial,
        # mostrar nombre subcomando si no tiene escuela
        # 👇 lógica para mostrar distinto según rol
        'escuela_nombre': (
            f"Usuario: {request.user.username}"
            if request.user.role == 'computos'
            else getattr(request.user.escuela, "nombre_escuela", None) 
                or getattr(request.user.subcomando, "nombre_subcomando", "Sin asignar")
        ),
    })
# ----------------------------
# Guardar votos (con validación de tipos especiales)
# ----------------------------

audit = logging.getLogger("audit")
app_log = logging.getLogger("app")

VALID_TIPOS_ESPECIALES = {"blanco", "nulo", "recurrido", "impugnado"}  # ajustá si tu modelo usa otros nombres

def _to_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def guardar_votos(request):
    user = request.user

    mesa_id = request.data.get('mesa_id')
    votos_cargo = request.data.get('votos_cargo', []) or []
    votos_especiales = request.data.get('votos_especiales', []) or []
    resumen_mesa = request.data.get('resumen_mesa', {}) or {}

    mesa = get_object_or_404(Mesa, id=mesa_id)

    # 👉 Siempre se puede editar/sobrescribir
    estaba_escrutada = bool(mesa.escrutada)

    try:
        with transaction.atomic():
            # --- Votos por cargo ---
            for voto in votos_cargo:
                partido_postulacion_id = voto.get('partido_postulacion_id')
                cantidad = max(_to_int(voto.get('votos'), 0), 0)
                if not partido_postulacion_id:
                    continue
                VotoMesaCargo.objects.update_or_create(
                    mesa=mesa,
                    partido_postulacion_id=partido_postulacion_id,
                    defaults={'votos': cantidad},
                )

            # --- Votos especiales ---
            for voto in votos_especiales:
                tipo = str(voto.get('tipo', '')).lower().strip()
                cargo_post_id = voto.get('cargo_postulacion_id')
                cantidad = max(_to_int(voto.get('votos'), 0), 0)
                if not cargo_post_id or not tipo:
                    continue
                VotoMesaEspecial.objects.update_or_create(
                    mesa=mesa,
                    cargo_postulacion_id=cargo_post_id,
                    tipo=tipo,
                    defaults={'votos': cantidad}
                )

            # --- Resumen ---
            electores_votaron  = max(_to_int(resumen_mesa.get('electores_votaron'), 0), 0)
            sobres_encontrados = max(_to_int(resumen_mesa.get('sobres_encontrados'), 0), 0)
            diferencia         = max(_to_int(resumen_mesa.get('diferencia'), 0), 0)

            ResumenMesa.objects.update_or_create(
                mesa=mesa,
                defaults={
                    'electores_votaron': electores_votaron,
                    'sobres_encontrados': sobres_encontrados,
                    'diferencia': diferencia,
                    'escrutada': True,
                }
            )

            if not mesa.escrutada:
                mesa.escrutada = True
                mesa.save(update_fields=['escrutada'])

        # Logs de negocio
        if not estaba_escrutada:
            audit.info(f"MESA_ESCRUTADA usuario={user.username} mesa_id={mesa.id}")
        else:
            audit.info(f"MESA_EDITADA usuario={user.username} mesa_id={mesa.id}")

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        app_log.exception("Error guardando votos para mesa_id=%s", mesa_id)
        return JsonResponse({'status': 'error', 'message': 'Error interno al guardar la mesa'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@login_required
def mesa_datos_panelista(request, mesa_id):
    if request.user.role not in ("panelista", "admin") and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)

    mesa = get_object_or_404(Mesa, id=mesa_id)
    cap = 460 if mesa.numero_mesa >= 9000 else 350

    resumen_obj = ResumenMesa.objects.filter(mesa=mesa).first()
    resumen = {
        'electores_votaron': resumen_obj.electores_votaron if resumen_obj else 0,
        'sobres_encontrados': resumen_obj.sobres_encontrados if resumen_obj else 0,
        'diferencia': resumen_obj.diferencia if resumen_obj else 0,
    }

    votos_cargo = list(
        VotoMesaCargo.objects.filter(mesa=mesa)
        .values('partido_postulacion_id', 'partido_postulacion__cargo_postulacion_id', 'votos')
    )
    votos_cargo = [
        {
            'partido_postulacion_id': v['partido_postulacion_id'],
            'cargo_id': v['partido_postulacion__cargo_postulacion_id'],
            'votos': v['votos'],
        }
        for v in votos_cargo
    ]

    votos_especiales = list(
        VotoMesaEspecial.objects.filter(mesa=mesa)
        .values('cargo_postulacion_id', 'tipo', 'votos')
    )

    # 👇 cálculo automático de total general
    total_general = (
        sum(v['votos'] for v in votos_cargo if v['votos']) +
        sum(v['votos'] for v in votos_especiales if v['votos'])
    )

    return JsonResponse({
        'status': 'ok',
        'escrutada': 1 if mesa.escrutada else 0,
        'cap': cap,
        'resumen': resumen,
        'votos_cargo': votos_cargo,
        'votos_especiales': votos_especiales,
        'total_general': total_general,   # ⬅️ nuevo campo
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@login_required
def mesa_datos(request, mesa_id):
    mesa = get_object_or_404(Mesa, id=mesa_id)
    cap = 460 if mesa.numero_mesa >= 9000 else 350

    resumen_obj = ResumenMesa.objects.filter(mesa=mesa).first()
    resumen = {
        'electores_votaron': resumen_obj.electores_votaron if resumen_obj else 0,
        'sobres_encontrados': resumen_obj.sobres_encontrados if resumen_obj else 0,
        'diferencia': resumen_obj.diferencia if resumen_obj else 0,
    }

    votos_cargo = list(
        VotoMesaCargo.objects.filter(mesa=mesa)
        .values('partido_postulacion_id',
                'partido_postulacion__cargo_postulacion_id',
                'votos')
    )
    votos_cargo = [
        {
            'partido_postulacion_id': v['partido_postulacion_id'],
            'cargo_id': v['partido_postulacion__cargo_postulacion_id'],
            'votos': v['votos'],
        }
        for v in votos_cargo
    ]

    votos_especiales = list(
        VotoMesaEspecial.objects.filter(mesa=mesa)
        .values('cargo_postulacion_id', 'tipo', 'votos')
    )

    # 👇 cálculo automático de total general
    total_general = (
        sum(v['votos'] for v in votos_cargo if v['votos']) +
        sum(v['votos'] for v in votos_especiales if v['votos'])
    )

    return JsonResponse({
        'status': 'ok',
        'escrutada': 1 if mesa.escrutada else 0,
        'cap': cap,
        'resumen': resumen,
        'votos_cargo': votos_cargo,
        'votos_especiales': votos_especiales,
        'total_general': total_general,   # ⬅️ nuevo campo para el front
    })



# =========================
# NUEVO PANEL LIVIANO
# =========================

@login_required
def panel_dashboard(request):
    if getattr(request.user, 'role', None) not in ('panelista', 'admin') and not request.user.is_superuser:
        return HttpResponseForbidden("No tenés permiso para acceder a este panel.")

    cargos_qs = (CargoPostulacion.objects
                 .filter(nombre_postulacion__in=['Diputados Provinciales', 'Concejales'])
                 .order_by('id')
                 .values('id', 'nombre_postulacion'))
    cargos = list(cargos_qs)

    # fallback por si la DB aún no tiene esos cargos cargados
    if not cargos:
        cargos = [
            {'id': 0, 'nombre_postulacion': 'Concejales'},
            {'id': 1, 'nombre_postulacion': 'Diputados Provinciales'},
        ]

    return render(request, 'panel/panel_dashboard.html', {
        'cargos': cargos,
    })

@never_cache
@login_required
def api_summary(request):
    cargo_id = request.GET.get('cargo_id')
    cargo_name = (request.GET.get('cargo') or '').strip()

    cargo = None
    if cargo_id and cargo_id.isdigit():
        cargo = CargoPostulacion.objects.filter(id=int(cargo_id)).first()
    if not cargo and cargo_name:
        alias = cargo_name.upper()
        mapa = {
            'DIPUTADOS': 'Diputados Provinciales',
            'DIPUTADOS PROVINCIALES': 'Diputados Provinciales',
            'CONCEJALES': 'Concejales',
        }
        target = mapa.get(alias, cargo_name)
        cargo = CargoPostulacion.objects.filter(nombre_postulacion__iexact=target).first()

    if not cargo:
        return JsonResponse({'error': 'Cargo inválido'}, status=400)

    # 👇 Superusuarios, admins y panelistas ven todo
    if request.user.is_superuser or request.user.role in ("admin", "panelista"):
        mesas_visibles = Mesa.objects.all()
    else:
        mesas_visibles = request.user.mesas_visibles

    qs = (VotoMesaCargo.objects
          .select_related('partido_postulacion__partido')
          .filter(partido_postulacion__cargo_postulacion=cargo,
                  mesa__in=mesas_visibles)
          .values('partido_postulacion__partido__pk',
                  'partido_postulacion__partido__nombre_partido')
          .annotate(votos=Sum('votos'))
          .order_by('-votos'))

    total_validos = sum((row['votos'] or 0) for row in qs)
    data = []
    for row in qs:
        votos = row['votos'] or 0
        pct = (votos * 100 / total_validos) if total_validos else 0
        data.append({
            'partido_id': row['partido_postulacion__partido__pk'],
            'partido': row['partido_postulacion__partido__nombre_partido'],
            'votos': votos,
            'porcentaje': round(pct, 2),
        })

    # ✅ ahora usamos Mesa.escrutada
    mesas_escrutadas = mesas_visibles.filter(escrutada=True).count()
    total_mesas = mesas_visibles.count()
    pct_mesas = round(mesas_escrutadas * 100 / total_mesas, 2) if total_mesas else 0

    return JsonResponse({
        'cargo': cargo.nombre_postulacion,
        'cargo_id': cargo.id,
        'total_validos': total_validos,
        'partidos': data,
        'mesas_escrutadas': mesas_escrutadas,
        'total_mesas': total_mesas,
        'porcentaje_mesas': pct_mesas,
        'timestamp': timezone.now().strftime('%d/%m/%Y %H:%M:%S'),
    })


@login_required
def api_summary_both(request):
    dip_id = request.GET.get('dip_id')
    con_id = request.GET.get('con_id')

    if dip_id and dip_id.isdigit():
        cargo_dip = CargoPostulacion.objects.filter(id=int(dip_id)).first()
    else:
        cargo_dip = CargoPostulacion.objects.filter(
            nombre_postulacion__iexact='Diputados Provinciales'
        ).first()

    if con_id and con_id.isdigit():
        cargo_con = CargoPostulacion.objects.filter(id=int(con_id)).first()
    else:
        cargo_con = CargoPostulacion.objects.filter(
            nombre_postulacion__iexact='Concejales'
        ).first()

    if not cargo_dip or not cargo_con:
        return JsonResponse({'error': 'No se encontraron los cargos requeridos'}, status=400)

    if request.user.is_superuser or request.user.role in ("admin", "panelista"):
        mesas_visibles = Mesa.objects.all()
    else:
        mesas_visibles = request.user.mesas_visibles

    qs = (VotoMesaCargo.objects
          .select_related('partido_postulacion__partido')
          .filter(partido_postulacion__cargo_postulacion__in=[cargo_dip, cargo_con],
                  mesa__in=mesas_visibles)
          .values('partido_postulacion__partido__pk',
                  'partido_postulacion__partido__nombre_partido',
                  'partido_postulacion__cargo_postulacion__id')
          .annotate(votos=Sum('votos')))

    total_dip = 0
    total_con = 0
    for r in qs:
        if r['partido_postulacion__cargo_postulacion__id'] == cargo_dip.id:
            total_dip += r['votos'] or 0
        else:
            total_con += r['votos'] or 0

    por_partido = {}
    for r in qs:
        pid = r['partido_postulacion__partido__pk']
        nombre = r['partido_postulacion__partido__nombre_partido']
        item = por_partido.setdefault(pid, {
            'partido_id': pid,
            'partido': nombre,
            'votos_dip': 0, 'pct_dip': 0.0,
            'votos_con': 0, 'pct_con': 0.0,
        })
        if r['partido_postulacion__cargo_postulacion__id'] == cargo_dip.id:
            item['votos_dip'] = r['votos'] or 0
        else:
            item['votos_con'] = r['votos'] or 0

    for item in por_partido.values():
        vd, vc = item['votos_dip'], item['votos_con']
        item['pct_dip'] = format((vd * 100 / total_dip), ".2f") if total_dip else "0.00"
        item['pct_con'] = format((vc * 100 / total_con), ".2f") if total_con else "0.00"

    filas = sorted(por_partido.values(), key=lambda x: (x['votos_dip'] + x['votos_con']), reverse=True)

    # ✅ ahora usamos Mesa.escrutada
    total_mesas = mesas_visibles.count()
    mesas_escrutadas = mesas_visibles.filter(escrutada=True).count()
    pct_mesas = round(mesas_escrutadas * 100 / total_mesas, 2) if total_mesas else 0

    return JsonResponse({
        'cargos': {
            'diputados': {
                'id': cargo_dip.id,
                'nombre': cargo_dip.nombre_postulacion,
                'total_validos': total_dip
            },
            'concejales': {
                'id': cargo_con.id,
                'nombre': cargo_con.nombre_postulacion,
                'total_validos': total_con
            },
        },
        'rows': filas,
        'mesas_escrutadas': mesas_escrutadas,
        'total_mesas': total_mesas,
        'porcentaje_mesas': pct_mesas,
        'timestamp': timezone.now().strftime('%d/%m/%Y %H:%M:%S'),
    })


@login_required
def api_metadata(request):
    if request.user.is_superuser or request.user.role in ("admin", "panelista"):
        mesas_visibles = Mesa.objects.all()
    else:
        mesas_visibles = request.user.mesas_visibles

    total_mesas = mesas_visibles.count()
    # ✅ antes contaba mesas con votos, ahora usamos Mesa.escrutada
    mesas_escrutadas = mesas_visibles.filter(escrutada=True).count()
    pct = round(mesas_escrutadas * 100 / total_mesas, 2) if total_mesas else 0
    return JsonResponse({
        'total_mesas': total_mesas,
        'mesas_escrutadas': mesas_escrutadas,
        'porcentaje_escrutadas': format(pct, ".2f"),
        'timestamp': timezone.now().strftime('%d/%m/%Y %H:%M:%S'),
    })


#-----TABLERO PANELISTA POR SUBCOMANDO------

@login_required
def api_subcomandos(request):
    """
    Avance por subcomando: mesas escrutadas / total.
    Usa Mesa.escrutada (más barato) — si preferís
    'mesas con votos', cambiá el filtro por VotoMesaCargo.
    """
    rows = (Subcomando.objects
            .annotate(
                total=Count('escuelas__mesas', distinct=True),
                escrutadas=Count('escuelas__mesas',
                                 filter=Q(escuelas__mesas__escrutada=True),
                                 distinct=True)
            )
    )

    items = []
    for r in rows:
        total = r.total or 0
        esc   = r.escrutadas or 0
        pct   = round(esc * 100 / total, 2) if total else 0.0
        items.append({
            'nombre': r.nombre_subcomando,
            'escrutadas': esc,
            'total': total,
            'porcentaje': pct,
        })

    # Subcomandos “sin asignar” (escuelas sin subcomando)
    sin_total = Mesa.objects.filter(escuela__subcomando__isnull=True).count()
    sin_esc   = Mesa.objects.filter(escuela__subcomando__isnull=True, escrutada=True).count()
    if sin_total:
        items.append({
            'nombre': 'Sin subcomando',
            'escrutadas': sin_esc,
            'total': sin_total,
            'porcentaje': round(sin_esc * 100 / sin_total, 2) if sin_total else 0.0,
        })

    # --- ORDEN MANUAL ---
    CUSTOM_ORDER = [
        # fila 1
        "Seccion 1ra", "Villa Elvira", "Melchor Romero", "Gonnet",
        # fila 2
        "Seccion 2da", "Sicardi-Garibaldi-Arana-Correa", "San Carlos", "Villa Castells",
        # fila 3
        "Seccion 3ra", "Altos de San Lorenzo", "Tolosa", "City Bell",
        # fila 4
        "Seccion 9na",  "Los Hornos","Ringuelet", "Villa Elisa",
        # fila 5
        "495", "Etcheverry", "Hernandez", "Arturo Segui",
        # fila 6
        "501", "Lisandro Olmos", "Gorina", "El Peligro",
        # fila 7
        "Isla Martin Garcia", "Abasto", 
    ]
    # Crear mapa normalizado
    orden_map = {name.lower().strip(): idx for idx, name in enumerate(CUSTOM_ORDER)}

    # Ordenar usando la versión normalizada
    items.sort(key=lambda x: orden_map.get(x['nombre'].lower().strip(), 999))


    return JsonResponse({'items': items})


#---PANEL DE GRAFICOS-----
@login_required
def panel_graficos(request):
    return render(request, "panel/panel_graficos.html")

#----PANEL DE RESULTADOS----
def panel_resultados(request):
    return render(request, 'panel/panel_resultados.html')

# ======================
# PANEL POR SECCIONES / CIRCUITOS
# ======================

@login_required
def panel_secciones(request):
    if getattr(request.user, 'role', None) not in ('panelista', 'admin') and not request.user.is_superuser:
        return HttpResponseForbidden("No tenés permiso para acceder a este panel.")
    return render(request, "panel/panel_secciones.html")

@login_required
def panel_circuitos(request):
    if getattr(request.user, 'role', None) not in ('panelista', 'admin') and not request.user.is_superuser:
        return HttpResponseForbidden("No tenés permiso para acceder a este panel.")
    return render(request, "panel/panel_circuitos.html")



@login_required
def api_online_users(request):
    from datetime import timedelta
    umbral = timezone.now() - timedelta(minutes=2)
    from .models import User

    try:
        rows = (User.objects
                .values('username', 'last_seen')
                .order_by('username'))
        users = []
        for r in rows:
            online = bool(r.get('last_seen') and r['last_seen'] >= umbral)
            users.append({'username': r['username'], 'online': online})
    except (OperationalError, ProgrammingError):
        # Column missing -> responder sin caer
        rows = (User.objects.values('username').order_by('username'))
        users = [{'username': r['username'], 'online': False} for r in rows]

    return JsonResponse({'users': users})

# =========================
# NUEVOS: AVANCE POR SECCION y CIRCUITO
# =========================

@login_required
def api_secciones(request):
    """
    Avance por Sección: mesas escrutadas / total.
    """
    rows = (Seccion.objects
            .annotate(
                total=Count('circuitos__escuelas__mesas', distinct=True),
                escrutadas=Count('circuitos__escuelas__mesas',
                                 filter=Q(circuitos__escuelas__mesas__escrutada=True),
                                 distinct=True)
            ))

    items = []
    for r in rows:
        total = r.total or 0
        esc   = r.escrutadas or 0
        pct   = round(esc * 100 / total, 2) if total else 0.0
        items.append({
            'nombre': r.nombre_seccion,
            'escrutadas': esc,
            'total': total,
            'porcentaje': pct,
        })

    items.sort(key=lambda x: x['nombre'])
    return JsonResponse({'items': items})


#-----------------------#
#----PANEL CIRCUITOS----#
#-----------------------#


from django.db.models import Sum

from django.db.models import Sum, Count, Q
from elecciones.models import CargoPostulacion, VotoMesaCargo, Circuito
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def api_circuitos(request):
    cargo_con = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Concejales"
    ).first()

    if not cargo_con:
        return JsonResponse({"error": "Cargo 'Concejales' no encontrado"}, status=400)

    rows = (Circuito.objects
            .annotate(
                total=Count('escuelas__mesas', distinct=True),
                escrutadas=Count('escuelas__mesas',
                                 filter=Q(escuelas__mesas__escrutada=True),
                                 distinct=True)
            ))

    items = []
    for r in rows:
        total = r.total or 0
        esc   = r.escrutadas or 0
        pct   = round(esc * 100 / total, 2) if total else 0.0

        # 🔹 Subcomandos asociados al circuito
        subcomandos = (r.escuelas
                         .values_list("subcomando__nombre_subcomando", flat=True)
                         .distinct())
        subcomandos = [s for s in subcomandos if s] or ["Sin asignar"]

        votos_qs = (
            VotoMesaCargo.objects
            .filter(
                mesa__escuela__circuito=r,
                partido_postulacion__cargo_postulacion=cargo_con
            )
            .values(
                "partido_postulacion__partido__nombre_partido",
                "partido_postulacion__partido__sigla"
            )
            .annotate(votos=Sum("votos"))
            .order_by("-votos")
        )

        total_votos = sum(v["votos"] or 0 for v in votos_qs)

        partidos = []
        for v in votos_qs:
            votos = v["votos"] or 0
            ppct = (votos * 100 / total_votos) if total_votos else 0
            partidos.append({
                "sigla": v["partido_postulacion__partido__sigla"],
                "nombre": v["partido_postulacion__partido__nombre_partido"],
                "votos": votos,
                "porcentaje": format(ppct, ".2f")
            })

        items.append({
            "nombre": r.codigo_circuito,
            "subcomandos": list(subcomandos),  # 👈 agregado
            "escrutadas": esc,
            "total": total,
            "porcentaje": pct,
            "partidos": partidos,
        })

    items.sort(key=lambda x: x["nombre"])
    return JsonResponse({"items": items})

@login_required
def api_circuitos_diputados(request):
    cargo_dip = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Diputados Provinciales"
    ).first()

    if not cargo_dip:
        return JsonResponse({"error": "Cargo 'Diputados Provinciales' no encontrado"}, status=400)

    rows = (Circuito.objects
            .annotate(
                total=Count('escuelas__mesas', distinct=True),
                escrutadas=Count('escuelas__mesas',
                                 filter=Q(escuelas__mesas__escrutada=True),
                                 distinct=True)
            ))

    items = []
    for r in rows:
        total = r.total or 0
        esc   = r.escrutadas or 0
        pct   = round(esc * 100 / total, 2) if total else 0.0

        # 🔹 Subcomandos asociados al circuito
        subcomandos = (r.escuelas
                         .values_list("subcomando__nombre_subcomando", flat=True)
                         .distinct())
        subcomandos = [s for s in subcomandos if s] or ["Sin asignar"]

        votos_qs = (
            VotoMesaCargo.objects
            .filter(
                mesa__escuela__circuito=r,
                partido_postulacion__cargo_postulacion=cargo_dip
            )
            .values(
                "partido_postulacion__partido__nombre_partido",
                "partido_postulacion__partido__sigla"
            )
            .annotate(votos=Sum("votos"))
            .order_by("-votos")
        )

        total_votos = sum(v["votos"] or 0 for v in votos_qs)

        partidos = []
        for v in votos_qs:
            votos = v["votos"] or 0
            ppct = (votos * 100 / total_votos) if total_votos else 0
            partidos.append({
                "sigla": v["partido_postulacion__partido__sigla"],
                "nombre": v["partido_postulacion__partido__nombre_partido"],
                "votos": votos,
                "porcentaje": format(ppct, ".2f")
            })

        items.append({
            "nombre": r.codigo_circuito,
            "subcomandos": list(subcomandos),
            "escrutadas": esc,
            "total": total,
            "porcentaje": pct,
            "partidos": partidos,
        })

    items.sort(key=lambda x: x["nombre"])
    return JsonResponse({"items": items})


@login_required
def api_seccion_detalle(request, nombre):
    """
    Devuelve detalle de una sección:
    - filas: lista | concejales | diputados
    - circuitos que pertenecen a esa sección (avance escrutado).
    """
    try:
        seccion = Seccion.objects.get(nombre_seccion=nombre)
    except Seccion.DoesNotExist:
        return JsonResponse({"error": f"Sección {nombre} no encontrada"}, status=404)

    # Traemos cargos
    cargo_con = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Concejales"
    ).first()
    cargo_dip = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Diputados Provinciales"
    ).first()

    if not cargo_con or not cargo_dip:
        return JsonResponse({"error": "Cargos no encontrados"}, status=400)

    # === VOTOS POR PARTIDO EN ESA SECCIÓN (agrupados) ===
    votos_qs = (
        VotoMesaCargo.objects
        .filter(
            mesa__escuela__circuito__seccion=seccion,
            partido_postulacion__cargo_postulacion__in=[cargo_con, cargo_dip]
        )
        .values(
            "partido_postulacion__partido__pk",
            "partido_postulacion__partido__nombre_partido",
            "partido_postulacion__cargo_postulacion__id"
        )
        .annotate(votos=Sum("votos"))
    )

    por_partido = {}
    for r in votos_qs:
        pid = r["partido_postulacion__partido__pk"]
        nombre_p = r["partido_postulacion__partido__nombre_partido"]
        cargo_id = r["partido_postulacion__cargo_postulacion__id"]

        item = por_partido.setdefault(pid, {
            "partido": nombre_p,
            "concejales": 0,
            "diputados": 0,
        })
        if cargo_id == cargo_con.id:
            item["concejales"] = r["votos"] or 0
        elif cargo_id == cargo_dip.id:
            item["diputados"] = r["votos"] or 0

    filas = list(por_partido.values())
    filas.sort(key=lambda x: (x["concejales"] + x["diputados"]), reverse=True)

    # === CIRCUITOS DE ESA SECCIÓN ===
    circuitos_qs = (
        Circuito.objects
        .filter(seccion=seccion)
        .annotate(
            total=Count("escuelas__mesas", distinct=True),
            escrutadas=Count(
                "escuelas__mesas",
                filter=Q(escuelas__mesas__escrutada=True),
                distinct=True
            )
        )
    )

    circuitos = []
    for c in circuitos_qs:
        total = c.total or 0
        esc = c.escrutadas or 0
        pct = (esc * 100 / total) if total else 0
        circuitos.append({
            "codigo": c.codigo_circuito,
            "escrutadas": esc,
            "total": total,
            "porcentaje": format(pct, ".2f")
        })

    return JsonResponse({
        "filas": filas,        # 👈 Listas con concejales y diputados
        "circuitos": circuitos # Avance por circuito
    })


# elecciones/views.py

from .models import User
from datetime import timedelta


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_usuarios_tabla(request):
    """
    Devuelve usuarios paginados con filtro opcional por username y subcomando.
    GET params:
      - page (default 1)
      - page_size (default 15)
      - search (busca en username o subcomando)
    """
    umbral = timezone.now() - timedelta(minutes=2)
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 15))
    search = (request.GET.get("search") or "").strip()

    qs = (User.objects
        .select_related("escuela__subcomando", "escuela__circuito__seccion")
        .order_by("username"))

    # 🔍 filtro
    if search:
        qs = qs.filter(
            Q(username__icontains=search) |
            Q(escuela__subcomando__nombre_subcomando__icontains=search)
        )

    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    qs = qs[start:end]

    data = []
    for u in qs:
        nombre = (f"{u.first_name} {u.last_name}".strip() or u.username)
        marcador = u.mesas_habilitadas.filter(activo=True).first() if hasattr(u, "mesas_habilitadas") else None
        mesa_num = marcador.mesa.numero_mesa if marcador else None
        mesa_escuela = marcador.mesa.escuela.nombre_escuela if marcador else None

        data.append({
            "id": u.id,
            "username": u.username,
            "nombre": nombre,
            "email": u.email or "",
            "role": (u.role or "").strip(),
            "escuela": getattr(u.escuela, "nombre_escuela", None),
            "subcomando": getattr(u.escuela.subcomando, "nombre_subcomando", None) if u.escuela else None,
            "celular": u.celular or "",
            "online": bool(u.last_seen and u.last_seen >= umbral),
            "mesa_asignada": mesa_num,
            "mesa_escuela": mesa_escuela,
        })

    return Response({
        "total": total,
        "page": page,
        "page_size": page_size,
        "usuarios": data,
    })


@login_required
def panel_usuarios(request):
    return render(request, "panel/panel_usuarios.html")


# views.py

from django.utils.timezone import now
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.contrib.admin.views.decorators import staff_member_required
from django.db import connection

@staff_member_required
def export_adherentes_pdf(request):
    usuario_nombre = request.GET.get("usuario")
    if not usuario_nombre:
        return HttpResponse("Debe seleccionar un usuario", status=400)

    # =========================
    # 1) Query SQL con orden personalizado
    # =========================
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT a.dni, a.apellido_nombre, a.domicilio,
                   a.referente_nombre, a.celular,
                   p.mesa, p.orden, p.id_escuela, p.escuela, p.domicilio_escuela
            FROM adherentes a
            LEFT JOIN padron p ON p.dni = a.dni
            WHERE a.voto = 0 AND a.creado_por_nombre = %s
            ORDER BY a.referente_nombre ASC, a.apellido_nombre ASC, a.dni ASC
        """, [usuario_nombre])
        rows = cursor.fetchall()

    # =========================
    # 2) PDF response
    # =========================
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{usuario_nombre}.pdf"'

    # Documento horizontal (A4 landscape)
    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        leftMargin=10,
        rightMargin=10,
        topMargin=15,
        bottomMargin=15
    )

    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Adherentes que faltan VOTAR", styles["Heading1"]),
        Paragraph(f"Generado: {now().strftime('%d/%m/%Y %H:%M:%S')}", styles["Normal"]),
        Spacer(1, 10),
    ]

    # =========================
    # 3) Tabla
    # =========================
    data = [[
        "DNI", "Apellido y Nombre", "Domicilio", "Referente", "Celular",
        "Mesa", "Orden", "ID Esc.", "Escuela", "Dom. Escuela"
    ]]
    data.extend(rows)

    # Col widths (no cambiamos nada)
    col_widths = [45, 95, 95, 85, 55, 35, 35, 50, 100, 130]

    table = Table(data, repeatRows=1, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),  # DNI centrado
        ("ALIGN", (5, 0), (7, -1), "CENTER"),  # Mesa, Orden, ID Escuela centrados
    ]))

    elements.append(table)

    # =========================
    # 4) Build PDF
    # =========================
    doc.build(elements)
    return response


# views.py (panel)
from django.db.models import F
from api.models import Adherente

@staff_member_required
def panel_pdf(request):
    usuarios = Adherente.objects.filter(voto=0).values_list("creado_por_nombre", flat=True).distinct()
    return render(request, "panel_pdf.html", {"usuarios": usuarios})


#-----------------------#
#---EXCELS---INFORMES---#
#-----------------------#
from django.http import HttpResponse

#-------------EXCEL CIRCUITOS----#


import openpyxl
from openpyxl.styles import Font, Alignment

@login_required
def export_circuitos_excel(request):
    cargo_con = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Concejales"
    ).first()

    if not cargo_con:
        return HttpResponse("Cargo 'Concejales' no encontrado", status=400)

    rows = (Circuito.objects
            .annotate(
                total=Count('escuelas__mesas', distinct=True),
                escrutadas=Count('escuelas__mesas',
                                 filter=Q(escuelas__mesas__escrutada=True),
                                 distinct=True)
            ))

    # Para ordenar las siglas de partidos según total provincial
    totales = {}
    for r in rows:
        votos_qs = (
            VotoMesaCargo.objects
            .filter(
                mesa__escuela__circuito=r,
                partido_postulacion__cargo_postulacion=cargo_con
            )
            .values(
                "partido_postulacion__partido__sigla",
                "partido_postulacion__partido__nombre_partido"
            )
            .annotate(votos=Sum("votos"))
        )
        for v in votos_qs:
            totales[v["partido_postulacion__partido__sigla"]] = \
                totales.get(v["partido_postulacion__partido__sigla"], 0) + (v["votos"] or 0)

    orden_partidos = sorted(totales.items(), key=lambda x: x[1], reverse=True)
    orden_siglas = [sigla for sigla, _ in orden_partidos]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Circuitos"

    # 👉 Encabezado (agregamos 2 columnas al final)
    headers = ["Subcomando", "Circuito"]
    for sigla in orden_siglas:
        headers.append(f"{sigla} Votos")
        headers.append(f"{sigla} %")
    headers.extend(["Total votos Blanco", "Total votos impugnados"])  # <-- NUEVO
    ws.append(headers)

    for col in range(1, len(headers) + 1):
        ws.cell(row=1, column=col).font = Font(bold=True)
        ws.cell(row=1, column=col).alignment = Alignment(horizontal="center")

    # Filas
    for r in rows:
        total = r.total or 0
        esc   = r.escrutadas or 0
        pct   = round(esc * 100 / total, 2) if total else 0.0
        circuito_label = f"{r.codigo_circuito} {esc}/{total} ({pct}%)"

        subcomandos = (r.escuelas
                         .values_list("subcomando__nombre_subcomando", flat=True)
                         .distinct())
        sub_label = ", ".join([s for s in subcomandos if s]) or "Sin asignar"

        votos_qs = (
            VotoMesaCargo.objects
            .filter(
                mesa__escuela__circuito=r,
                partido_postulacion__cargo_postulacion=cargo_con
            )
            .values(
                "partido_postulacion__partido__sigla",
                "partido_postulacion__partido__nombre_partido"
            )
            .annotate(votos=Sum("votos"))
        )
        total_votos = sum(v["votos"] or 0 for v in votos_qs)
        map_partidos = {v["partido_postulacion__partido__sigla"]: v for v in votos_qs}

        # 👉 Blancos / Impugnados del circuito y cargo
        blancos = (
            VotoMesaEspecial.objects
            .filter(
                mesa__escuela__circuito=r,
                cargo_postulacion=cargo_con,
                tipo__in=["blanco", "blancos", "en_blanco"]
            )
            .aggregate(total=Sum("votos"))["total"] or 0
        )
        impugnados = (
            VotoMesaEspecial.objects
            .filter(
                mesa__escuela__circuito=r,
                cargo_postulacion=cargo_con,
                tipo__in=["impugnado", "impugnados"]
            )
            .aggregate(total=Sum("votos"))["total"] or 0
        )

        row = [sub_label, circuito_label]
        for sigla in orden_siglas:
            v = map_partidos.get(sigla)
            votos = v["votos"] if v else 0
            ppct = (votos * 100 / total_votos) if total_votos else 0
            row.extend([votos, format(ppct, ".2f")])

        # 👉 columnas nuevas al final
        row.extend([blancos, impugnados])
        ws.append(row)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    fecha = now().strftime("%Y%m%d_%H%M")
    response["Content-Disposition"] = f'attachment; filename="circuitos_LaPlata_{fecha}.xlsx"'
    wb.save(response)
    return response


@login_required
def export_circuitos_excel_diputados(request):
    cargo_dip = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Diputados Provinciales"
    ).first()

    if not cargo_dip:
        return HttpResponse("Cargo 'Diputados Provinciales' no encontrado", status=400)

    rows = (Circuito.objects
            .annotate(
                total=Count('escuelas__mesas', distinct=True),
                escrutadas=Count('escuelas__mesas',
                                 filter=Q(escuelas__mesas__escrutada=True),
                                 distinct=True)
            ))

    # Orden global de siglas
    totales = {}
    for r in rows:
        votos_qs = (
            VotoMesaCargo.objects
            .filter(
                mesa__escuela__circuito=r,
                partido_postulacion__cargo_postulacion=cargo_dip
            )
            .values(
                "partido_postulacion__partido__sigla",
                "partido_postulacion__partido__nombre_partido"
            )
            .annotate(votos=Sum("votos"))
        )
        for v in votos_qs:
            totales[v["partido_postulacion__partido__sigla"]] = \
                totales.get(v["partido_postulacion__partido__sigla"], 0) + (v["votos"] or 0)

    orden_siglas = [sigla for sigla, _ in sorted(totales.items(), key=lambda x: x[1], reverse=True)]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Circuitos"

    # 👉 Encabezado con nuevas columnas
    headers = ["Subcomando", "Circuito"]
    for sigla in orden_siglas:
        headers.append(f"{sigla} Votos")
        headers.append(f"{sigla} %")
    headers.extend(["Total votos Blanco", "Total votos impugnados"])  # <-- NUEVO
    ws.append(headers)

    for col in range(1, len(headers) + 1):
        ws.cell(row=1, column=col).font = Font(bold=True)
        ws.cell(row=1, column=col).alignment = Alignment(horizontal="center")

    for r in rows:
        total = r.total or 0
        esc   = r.escrutadas or 0
        pct   = round(esc * 100 / total, 2) if total else 0.0
        circuito_label = f"{r.codigo_circuito} {esc}/{total} ({pct}%)"

        subcomandos = (r.escuelas
                         .values_list("subcomando__nombre_subcomando", flat=True)
                         .distinct())
        sub_label = ", ".join([s for s in subcomandos if s]) or "Sin asignar"

        votos_qs = (
            VotoMesaCargo.objects
            .filter(
                mesa__escuela__circuito=r,
                partido_postulacion__cargo_postulacion=cargo_dip
            )
            .values(
                "partido_postulacion__partido__sigla",
                "partido_postulacion__partido__nombre_partido"
            )
            .annotate(votos=Sum("votos"))
        )
        total_votos = sum(v["votos"] or 0 for v in votos_qs)
        map_partidos = {v["partido_postulacion__partido__sigla"]: v for v in votos_qs}

        # 👉 Blancos / Impugnados del circuito y cargo
        blancos = (
            VotoMesaEspecial.objects
            .filter(
                mesa__escuela__circuito=r,
                cargo_postulacion=cargo_dip,
                tipo__in=["blanco", "blancos", "en_blanco"]
            )
            .aggregate(total=Sum("votos"))["total"] or 0
        )
        impugnados = (
            VotoMesaEspecial.objects
            .filter(
                mesa__escuela__circuito=r,
                cargo_postulacion=cargo_dip,
                tipo__in=["impugnado", "impugnados"]
            )
            .aggregate(total=Sum("votos"))["total"] or 0
        )

        row = [sub_label, circuito_label]
        for sigla in orden_siglas:
            v = map_partidos.get(sigla)
            votos = v["votos"] if v else 0
            ppct = (votos * 100 / total_votos) if total_votos else 0
            row.extend([votos, format(ppct, ".2f")])

        # 👉 columnas nuevas al final
        row.extend([blancos, impugnados])
        ws.append(row)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    fecha = now().strftime("%Y%m%d_%H%M")
    response["Content-Disposition"] = f'attachment; filename="circuitos_Diputados_{fecha}.xlsx"'
    wb.save(response)
    return response


@login_required
def export_subcomandos_excel(request):
    cargo_con = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Concejales"
    ).first()
    cargo_dip = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Diputados Provinciales"
    ).first()

    if not cargo_con or not cargo_dip:
        return HttpResponse("Cargos no encontrados", status=400)

    def build_sheet(ws, cargo):
        # --- calcular orden global de partidos
        totales = {}
        for sub in Subcomando.objects.all():
            votos_qs = (
                VotoMesaCargo.objects
                .filter(
                    mesa__escuela__subcomando=sub,
                    partido_postulacion__cargo_postulacion=cargo
                )
                .values(
                    "partido_postulacion__partido__sigla",
                    "partido_postulacion__partido__nombre_partido"
                )
                .annotate(votos=Sum("votos"))
            )
            for v in votos_qs:
                totales[v["partido_postulacion__partido__sigla"]] = \
                    totales.get(v["partido_postulacion__partido__sigla"], 0) + (v["votos"] or 0)

        orden_siglas = [sigla for sigla, _ in sorted(totales.items(), key=lambda x: x[1], reverse=True)]

        # --- encabezados
        headers = ["Subcomando"]
        for sigla in orden_siglas:
            headers.append(f"{sigla} Votos")
            headers.append(f"{sigla} %")
        # 👇 columnas extra
        headers.extend(["TOTAL VOTOS BLANCOS", "TOTAL VOTOS IMPUGNADOS", "HABILITADOS PARA VOTAR"])
        ws.append(headers)
        for col in range(1, len(headers) + 1):
            ws.cell(row=1, column=col).font = Font(bold=True)
            ws.cell(row=1, column=col).alignment = Alignment(horizontal="center")

        # --- filas por subcomando
        for sub in Subcomando.objects.all().order_by("nombre_subcomando"):
            total = Mesa.objects.filter(escuela__subcomando=sub).count()
            esc   = Mesa.objects.filter(escuela__subcomando=sub, escrutada=True).count()
            pct_mesas = round(esc * 100 / total, 2) if total else 0.0
            sub_label = f"{sub.nombre_subcomando} {esc}/{total} ({pct_mesas}%)"

            votos_qs = (
                VotoMesaCargo.objects
                .filter(
                    mesa__escuela__subcomando=sub,
                    partido_postulacion__cargo_postulacion=cargo
                )
                .values(
                    "partido_postulacion__partido__sigla",
                    "partido_postulacion__partido__nombre_partido"
                )
                .annotate(votos=Sum("votos"))
            )
            total_votos = sum(v["votos"] or 0 for v in votos_qs)
            map_partidos = {v["partido_postulacion__partido__sigla"]: v for v in votos_qs}

            # === Blancos e Impugnados (usa VotoMesaEspecial)
            blancos = (
                VotoMesaEspecial.objects
                .filter(
                    mesa__escuela__subcomando=sub,
                    cargo_postulacion=cargo,
                    tipo__in=["blanco", "blancos", "en_blanco"]
                )
                .aggregate(total=Sum("votos"))["total"] or 0
            )
            impugnados = (
                VotoMesaEspecial.objects
                .filter(
                    mesa__escuela__subcomando=sub,
                    cargo_postulacion=cargo,
                    tipo__in=["impugnado", "impugnados"]
                )
                .aggregate(total=Sum("votos"))["total"] or 0
            )

            # === Habilitados (del padrón)
            mesas_nums = Mesa.objects.filter(escuela__subcomando=sub).values_list("numero_mesa", flat=True)
            habilitados = Padron.objects.filter(mesa__in=mesas_nums).count()

            row = [sub_label]
            for sigla in orden_siglas:
                v = map_partidos.get(sigla)
                votos = v["votos"] if v else 0
                ppct = (votos * 100 / total_votos) if total_votos else 0
                row.extend([votos, format(ppct, ".2f")])

            # 👇 columnas extra al final
            row.extend([blancos, impugnados, habilitados])
            ws.append(row)

    # === Crear workbook con dos hojas ===
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Concejales"
    build_sheet(ws1, cargo_con)

    ws2 = wb.create_sheet(title="Diputados")
    build_sheet(ws2, cargo_dip)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    fecha = now().strftime("%Y%m%d_%H%M")
    response["Content-Disposition"] = f'attachment; filename="subcomandos_{fecha}.xlsx"'
    wb.save(response)
    return response


#-----------------------#
#---PANEL SUBCOMANDOS---#
#-----------------------#

@login_required
def panel_subcomandos(request):
    if getattr(request.user, 'role', None) not in ('panelista', 'admin') and not request.user.is_superuser:
        return HttpResponseForbidden("No tenés permiso para acceder a este panel.")
    return render(request, "panel/panel_subcomandos.html")

@login_required
def api_subcomando_detalle(request, nombre):
    try:
        subcomando = Subcomando.objects.get(nombre_subcomando=nombre)
    except Subcomando.DoesNotExist:
        return JsonResponse({"error": f"Subcomando {nombre} no encontrado"}, status=404)

    # Traemos cargos
    cargo_con = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Concejales"
    ).first()
    cargo_dip = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Diputados Provinciales"
    ).first()

    if not cargo_con or not cargo_dip:
        return JsonResponse({"error": "Cargos no encontrados"}, status=400)

    # Votos agrupados por partido y cargo
    votos_qs = (
        VotoMesaCargo.objects
        .filter(mesa__escuela__subcomando=subcomando,
                partido_postulacion__cargo_postulacion__in=[cargo_con, cargo_dip])
        .values("partido_postulacion__partido__pk",
                "partido_postulacion__partido__nombre_partido",
                "partido_postulacion__cargo_postulacion__id")
        .annotate(votos=Sum("votos"))
    )

    por_partido = {}
    for r in votos_qs:
        pid = r["partido_postulacion__partido__pk"]
        nombre_p = r["partido_postulacion__partido__nombre_partido"]
        cargo_id = r["partido_postulacion__cargo_postulacion__id"]

        item = por_partido.setdefault(pid, {
            "partido": nombre_p,
            "concejales": 0,
            "diputados": 0,
        })
        if cargo_id == cargo_con.id:
            item["concejales"] = r["votos"] or 0
        elif cargo_id == cargo_dip.id:
            item["diputados"] = r["votos"] or 0

    filas = list(por_partido.values())
    filas.sort(key=lambda x: (x["concejales"] + x["diputados"]), reverse=True)

    # Escuelas (como ya tenías)
    escuelas_qs = (
        subcomando.escuelas
        .annotate(
            total=Count("mesas", distinct=True),
            escrutadas=Count("mesas", filter=Q(mesas__escrutada=True), distinct=True),
        )
    )
    escuelas = []
    for e in escuelas_qs:
        total = e.total or 0
        esc = e.escrutadas or 0
        pct = (esc * 100 / total) if total else 0
        escuelas.append({
            "nombre": e.nombre_escuela,
            "escrutadas": esc,
            "total": total,
            "porcentaje": format(pct, ".2f")
        })

    return JsonResponse({
        "filas": filas,   # 👈 ahora tenés concejales y diputados por lista
        "escuelas": escuelas,
    })


@login_required
def api_subcomandos_concejales(request):
    cargo = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Concejales"
    ).first()
    if not cargo:
        return JsonResponse({"error": "Cargo 'Concejales' no encontrado"}, status=400)

    rows = (Subcomando.objects
            .annotate(
                total=Count('escuelas__mesas', distinct=True),
                escrutadas=Count('escuelas__mesas',
                                 filter=Q(escuelas__mesas__escrutada=True),
                                 distinct=True)
            ))

    items = []
    for sub in rows:
        total = sub.total or 0
        esc   = sub.escrutadas or 0
        pct   = round(esc * 100 / total, 2) if total else 0.0

        votos_qs = (
            VotoMesaCargo.objects
            .filter(
                mesa__escuela__subcomando=sub,
                partido_postulacion__cargo_postulacion=cargo
            )
            .values("partido_postulacion__partido__sigla",
                    "partido_postulacion__partido__nombre_partido")
            .annotate(votos=Sum("votos"))
            .order_by("-votos")
        )

        total_votos = sum(v["votos"] or 0 for v in votos_qs)
        partidos = []
        for v in votos_qs:
            votos = v["votos"] or 0
            ppct = (votos * 100 / total_votos) if total_votos else 0
            partidos.append({
                "sigla": v["partido_postulacion__partido__sigla"],
                "nombre": v["partido_postulacion__partido__nombre_partido"],
                "votos": votos,
                "porcentaje": format(ppct, ".2f")
            })

        items.append({
            "nombre": sub.nombre_subcomando,
            "escrutadas": esc,
            "total": total,
            "porcentaje": pct,
            "partidos": partidos,
        })

    items.sort(key=lambda x: x["nombre"])
    return JsonResponse({"items": items})


@login_required
def api_subcomandos_diputados(request):
    cargo = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Diputados Provinciales"
    ).first()
    if not cargo:
        return JsonResponse({"error": "Cargo 'Diputados Provinciales' no encontrado"}, status=400)

    rows = (Subcomando.objects
            .annotate(
                total=Count('escuelas__mesas', distinct=True),
                escrutadas=Count('escuelas__mesas',
                                 filter=Q(escuelas__mesas__escrutada=True),
                                 distinct=True)
            ))

    items = []
    for sub in rows:
        total = sub.total or 0
        esc   = sub.escrutadas or 0
        pct   = round(esc * 100 / total, 2) if total else 0.0

        votos_qs = (
            VotoMesaCargo.objects
            .filter(
                mesa__escuela__subcomando=sub,
                partido_postulacion__cargo_postulacion=cargo
            )
            .values("partido_postulacion__partido__sigla",
                    "partido_postulacion__partido__nombre_partido")
            .annotate(votos=Sum("votos"))
            .order_by("-votos")
        )

        total_votos = sum(v["votos"] or 0 for v in votos_qs)
        partidos = []
        for v in votos_qs:
            votos = v["votos"] or 0
            ppct = (votos * 100 / total_votos) if total_votos else 0
            partidos.append({
                "sigla": v["partido_postulacion__partido__sigla"],
                "nombre": v["partido_postulacion__partido__nombre_partido"],
                "votos": votos,
                "porcentaje": format(ppct, ".2f")
            })

        items.append({
            "nombre": sub.nombre_subcomando,
            "escrutadas": esc,
            "total": total,
            "porcentaje": pct,
            "partidos": partidos,
        })

    items.sort(key=lambda x: x["nombre"])
    return JsonResponse({"items": items})

#-----------------------#
#---PANEL EXTRANJEROS---#
#-----------------------#

from django.db.models import Sum, F
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
import openpyxl
import json

@login_required
def panel_extranjeros(request):
    return render(request, "panel/panel_extranjeros.html")


@login_required
def subcomandos_extranjeros(request, cargo_nombre):
    """
    Devuelve votos y % por subcomando para mesas extranjeras (numero_mesa >= 9000)
    """
    mesas_extranjeras = Mesa.objects.filter(numero_mesa__gte=9000)

    # filtrar cargo
    try:
        cargo = CargoPostulacion.objects.get(nombre_postulacion__icontains=cargo_nombre)
    except CargoPostulacion.DoesNotExist:
        return JsonResponse({"items": []})

    resultados = (
        VotoMesaCargo.objects
        .filter(
            mesa__in=mesas_extranjeras,
            partido_postulacion__cargo_postulacion=cargo
        )
        .values(
            "mesa__escuela__subcomando__nombre_subcomando",
            "partido_postulacion__partido__sigla",
            "partido_postulacion__partido__nombre_partido",
        )
        .annotate(votos=Sum("votos"))
        .order_by("mesa__escuela__subcomando__nombre_subcomando")
    )

    # armar estructura: {subcomando: {...}}
    data = {}
    for r in resultados:
        sub = r["mesa__escuela__subcomando__nombre_subcomando"] or "Sin Subcomando"
        sigla = r["partido_postulacion__partido__sigla"]
        nombre = r["partido_postulacion__partido__nombre_partido"]
        votos = r["votos"] or 0

        if sub not in data:
            # calcular totales para ese subcomando
            total_mesas = mesas_extranjeras.filter(escuela__subcomando__nombre_subcomando=sub).count()
            escrutadas = mesas_extranjeras.filter(escuela__subcomando__nombre_subcomando=sub, escrutada=True).count()
            pct_mesas = round(escrutadas * 100 / total_mesas, 2) if total_mesas else 0.0

            data[sub] = {
                "total": 0,
                "partidos": {},
                "mesas_total": total_mesas,
                "mesas_escrutadas": escrutadas,
                "mesas_pct": pct_mesas,
            }

        data[sub]["total"] += votos
        data[sub]["partidos"][sigla] = {
            "sigla": sigla,
            "nombre": nombre,
            "votos": votos
        }

    # convertir a lista
    items = []
    for sub, info in data.items():
        partidos = []
        for p in info["partidos"].values():
            pct = (p["votos"] / info["total"] * 100) if info["total"] else 0
            partidos.append({
                "sigla": p["sigla"],
                "nombre": p["nombre"],
                "votos": p["votos"],
                "porcentaje": format(pct, ".2f")
            })
        items.append({
            "nombre": sub,
            "total": info["total"],
            "partidos": partidos,
            "escrutadas": info["mesas_escrutadas"],
            "total_mesas": info["mesas_total"],
            "porcentaje": info["mesas_pct"],
        })

    return JsonResponse({"items": items})



# vistas concretas
@login_required
def subcomandos_extranjeros_concejales(request):
    return subcomandos_extranjeros(request, "Concejales")


@login_required
def subcomandos_extranjeros_diputados(request):
    return subcomandos_extranjeros(request, "Diputados Provinciales")


from io import BytesIO

@login_required
def export_subcomandos_extranjeros_excel(request):
    """
    Genera un .xlsx con dos solapas:
      - 'Concejales'
      - 'Diputados'
    SOLO mesas extranjeras (numero_mesa >= 9000).
    Columnas: Subcomando | Escuela | Mesa | Total | [siglas de listas] | Blancos | Impugnados
    """
    cargo_con = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Concejales"
    ).first()
    cargo_dip = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Diputados Provinciales"
    ).first()

    if not cargo_con or not cargo_dip:
        return HttpResponse("Cargos no encontrados", status=400)

    def _build_sheet_extranjeros(ws, cargo: CargoPostulacion):
        """
        Igual que _build_sheet_mesas pero solo mesas >= 9000
        """
        # 1) Orden global de listas por total
        totales = (
            VotoMesaCargo.objects
            .filter(
                partido_postulacion__cargo_postulacion=cargo,
                mesa__numero_mesa__gte=9000
            )
            .values("partido_postulacion__partido__sigla", "partido_postulacion_id")
            .annotate(v=Sum("votos"))
        )
        orden = sorted(
            [(t["partido_postulacion__partido__sigla"] or "",
              t["partido_postulacion_id"], t["v"] or 0) for t in totales],
            key=lambda x: x[2],
            reverse=True
        )
        if not orden:
            for pp in PartidoPostulacion.objects.filter(cargo_postulacion=cargo).select_related("partido"):
                orden.append((pp.partido.sigla or pp.partido.nombre_partido, pp.id, 0))

        # 2) Encabezados
        headers = ["Subcomando", "Escuela", "Mesa", "Total"]
        headers.extend([sigla or "LISTA" for sigla, _ppid, _tot in orden])
        headers.extend(["Blancos", "Impugnados"])
        ws.append(headers)

        for col in range(1, len(headers) + 1):
            c = ws.cell(row=1, column=col)
            c.font = TH_BOLD
            c.alignment = CENTER
            c.fill = TH_FILL
            c.border = TH_BORDER

        ws.freeze_panes = "A2"

        # 3) Precálculos
        votos_por_mesa_lista = {}
        for item in (
            VotoMesaCargo.objects
            .filter(
                partido_postulacion__cargo_postulacion=cargo,
                mesa__numero_mesa__gte=9000
            )
            .values("mesa_id", "partido_postulacion_id")
            .annotate(v=Sum("votos"))
        ):
            votos_por_mesa_lista[(item["mesa_id"], item["partido_postulacion_id"])] = item["v"] or 0

        especiales_por_mesa = {}
        for sp in (
            VotoMesaEspecial.objects
            .filter(cargo_postulacion=cargo, mesa__numero_mesa__gte=9000)
            .values("mesa_id", "tipo")
            .annotate(v=Sum("votos"))
        ):
            tipo = (sp["tipo"] or "").strip().lower()
            key = (sp["mesa_id"], tipo)
            especiales_por_mesa[key] = especiales_por_mesa.get(key, 0) + (sp["v"] or 0)

        def get_blancos(mesa_id):
            return (
                especiales_por_mesa.get((mesa_id, "blanco")) or
                especiales_por_mesa.get((mesa_id, "blancos")) or
                especiales_por_mesa.get((mesa_id, "en_blanco")) or 0
            )

        def get_impug(mesa_id):
            return (
                especiales_por_mesa.get((mesa_id, "impugnado")) or
                especiales_por_mesa.get((mesa_id, "impugnados")) or 0
            )

        # 4) Filas
        mesas_qs = (
            Mesa.objects
            .filter(numero_mesa__gte=9000)
            .select_related("escuela", "escuela__subcomando")
            .order_by("numero_mesa", "escuela__subcomando__nombre_subcomando",
                      "escuela__nombre_escuela", "id")
        )

        ppid_list = [ppid for _sigla, ppid, _tot in orden]

        for m in mesas_qs:
            sub, esc, nro = _mesa_label(m)
            blancos_m = get_blancos(m.id)
            impug_m   = get_impug(m.id)

            votos_listas = [votos_por_mesa_lista.get((m.id, ppid), 0) for ppid in ppid_list]
            total_mesa = sum(votos_listas) + blancos_m + impug_m

            row = [sub, esc, nro, total_mesa]
            row.extend(votos_listas)
            row.extend([blancos_m, impug_m])
            ws.append(row)

        _autosize(ws)

    # === Workbook con dos hojas ===
    wb = openpyxl.Workbook()
    ws_con = wb.active
    ws_con.title = "Concejales"
    _build_sheet_extranjeros(ws_con, cargo_con)

    ws_dip = wb.create_sheet(title="Diputados")
    _build_sheet_extranjeros(ws_dip, cargo_dip)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    fecha = now().strftime("%Y%m%d_%H%M")
    response["Content-Disposition"] = f'attachment; filename="extranjeros_{fecha}.xlsx"'
    wb.save(response)
    return response


# ---------------------------#
# ---EXCEL--MESAS--TOTALES---#
# ---------------------------#

from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

TH_BOLD = Font(bold=True)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
TH_FILL = PatternFill("solid", fgColor="E8EEF7")
TH_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin")
)

def _mesa_label(m):
    escuela = (
        getattr(m.escuela, "nombre_escuela", None)
        or getattr(m.escuela, "nombre", None)
        or getattr(m.escuela, "nombre_establecimiento", "")
    )
    sub = getattr(getattr(m.escuela, "subcomando", None), "nombre_subcomando", "") or ""
    numero = (
        getattr(m, "numero_mesa", None)
        or getattr(m, "numero", None)
        or getattr(m, "mesa", None)
        or m.pk
    )
    return sub, escuela, numero

def _autosize(ws):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            v = cell.value
            l = len(str(v)) if v is not None else 0
            if l > max_len:
                max_len = l
        ws.column_dimensions[col_letter].width = min(max(12, max_len + 2), 45)

def _build_sheet_mesas(ws, cargo: CargoPostulacion):
    """
    Hoja por cargo:
      - Filas: todas las mesas
      - Columnas: Subcomando | Escuela | Mesa | Total | [por cada lista: SIGLA] | Blancos | Impugnados
    """
    # 1) Orden global de listas por total de votos (desc)
    totales = (
        VotoMesaCargo.objects
        .filter(partido_postulacion__cargo_postulacion=cargo)
        .values("partido_postulacion__partido__sigla", "partido_postulacion_id")
        .annotate(v=Sum("votos"))
    )
    orden = sorted(
        [(t["partido_postulacion__partido__sigla"] or "",
          t["partido_postulacion_id"], t["v"] or 0) for t in totales],
        key=lambda x: x[2],
        reverse=True
    )
    if not orden:
        for pp in PartidoPostulacion.objects.filter(cargo_postulacion=cargo).select_related("partido"):
            orden.append((pp.partido.sigla or pp.partido.nombre_partido, pp.id, 0))

    # 2) Encabezados (una sola fila)
    headers = ["Subcomando", "Escuela", "Mesa", "Total"]
    headers.extend([sigla or "LISTA" for sigla, _ppid, _tot in orden])
    headers.extend(["Blancos", "Impugnados"])  # al final
    ws.append(headers)

    # Estilo de encabezados
    for col in range(1, len(headers) + 1):
        c = ws.cell(row=1, column=col)
        c.font = TH_BOLD
        c.alignment = CENTER
        c.fill = TH_FILL
        c.border = TH_BORDER

    ws.freeze_panes = "A2"  # solo la fila 1 es encabezado

    # 3) Precálculos
    votos_por_mesa_lista = {}
    for item in (
        VotoMesaCargo.objects
        .filter(partido_postulacion__cargo_postulacion=cargo)
        .values("mesa_id", "partido_postulacion_id")
        .annotate(v=Sum("votos"))
    ):
        votos_por_mesa_lista[(item["mesa_id"], item["partido_postulacion_id"])] = item["v"] or 0

    especiales_por_mesa = {}
    for sp in (
        VotoMesaEspecial.objects
        .filter(cargo_postulacion=cargo)
        .values("mesa_id", "tipo")
        .annotate(v=Sum("votos"))
    ):
        tipo = (sp["tipo"] or "").strip().lower()
        key = (sp["mesa_id"], tipo)
        especiales_por_mesa[key] = especiales_por_mesa.get(key, 0) + (sp["v"] or 0)

    def get_blancos(mesa_id):
        return (
            especiales_por_mesa.get((mesa_id, "blanco")) or
            especiales_por_mesa.get((mesa_id, "blancos")) or
            especiales_por_mesa.get((mesa_id, "en_blanco")) or 0
        )

    def get_impug(mesa_id):
        return (
            especiales_por_mesa.get((mesa_id, "impugnado")) or
            especiales_por_mesa.get((mesa_id, "impugnados")) or 0
        )

    # 4) Filas
    mesas_qs = (
        Mesa.objects
        .select_related("escuela", "escuela__subcomando")
        .order_by("numero_mesa", "escuela__subcomando__nombre_subcomando",
                  "escuela__nombre_escuela", "id")
    )

    ppid_list = [ppid for _sigla, ppid, _tot in orden]

    for m in mesas_qs:
        sub, esc, nro = _mesa_label(m)
        blancos_m = get_blancos(m.id)
        impug_m   = get_impug(m.id)

        # votos por lista (una sola celda por lista)
        votos_listas = [votos_por_mesa_lista.get((m.id, ppid), 0) for ppid in ppid_list]
        total_mesa = sum(votos_listas) + blancos_m + impug_m

        row = [sub, esc, nro, total_mesa]
        row.extend(votos_listas)
        row.extend([blancos_m, impug_m])  # al final
        ws.append(row)

    _autosize(ws)

@login_required
def export_mesas_por_cargo_excel(request):
    """
    Genera un .xlsx con dos solapas:
      - 'Diputados'
      - 'Concejales'
    Columnas: Subcomando | Escuela | Mesa | Total | [siglas de listas] | Blancos | Impugnados
    """
    cargo_con = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Concejales"
    ).first()
    cargo_dip = CargoPostulacion.objects.filter(
        nombre_postulacion__iexact="Diputados Provinciales"
    ).first()

    if not cargo_con or not cargo_dip:
        return HttpResponse("Cargos no encontrados", status=400)

    wb = openpyxl.Workbook()
    ws_con = wb.active
    ws_con.title = "Concejales"
    _build_sheet_mesas(ws_con, cargo_con)

    ws_dip = wb.create_sheet(title="Diputados")
    _build_sheet_mesas(ws_dip, cargo_dip)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    fecha = now().strftime("%Y%m%d_%H%M")
    response["Content-Disposition"] = (
        f'attachment; filename="total_mesas{fecha}.xlsx"'
    )
    wb.save(response)
    return response
