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
from django.http import HttpResponse
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

    # DRF ya parseó JSON en request.data
    mesa_id = request.data.get('mesa_id')
    votos_cargo = request.data.get('votos_cargo', []) or []
    votos_especiales = request.data.get('votos_especiales', []) or []
    resumen_mesa = request.data.get('resumen_mesa', {}) or {}
    overwrite = bool(request.data.get('overwrite'))

    # Mesa válida y de la escuela del operador
    mesa = get_object_or_404(Mesa, id=mesa_id, escuela_id=user.escuela_id)

    if not (user.is_authenticated and user.puede_editar_mesa(mesa)):
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)

    # ¿Ya estaba escrutada?
    estaba_escrutada = bool(mesa.escrutada)

    # Si está escrutada y no pidieron overwrite => 409 + log de intento
    if estaba_escrutada and not overwrite:
        audit.info(f"INTENTO_OVERWRITE usuario={user.username} mesa_id={mesa.id}")
        return JsonResponse({
            'status': 'error',
            'message': f'La mesa {mesa.numero_mesa} ya fue escrutada.'
        }, status=409)

    try:
        with transaction.atomic():
            # --- Votos por cargo (upsert) ---
            for voto in votos_cargo:
                partido_postulacion_id = voto.get('partido_postulacion_id')
                cantidad = max(_to_int(voto.get('votos'), 0), 0)

                if not partido_postulacion_id:
                    continue  # ignora items incompletos

                VotoMesaCargo.objects.update_or_create(
                    mesa=mesa,
                    partido_postulacion_id=partido_postulacion_id,
                    defaults={'votos': cantidad},
                )

            # --- Votos especiales (upsert) ---
            for voto in votos_especiales:
                tipo = str(voto.get('tipo', '')).lower().strip()
                cargo_post_id = voto.get('cargo_postulacion_id')
                cantidad = max(_to_int(voto.get('votos'), 0), 0)

                if not cargo_post_id or not tipo:
                    continue
                # si querés forzar tipos válidos, descomentá:
                # if tipo not in VALID_TIPOS_ESPECIALES: continue

                VotoMesaEspecial.objects.update_or_create(
                    mesa=mesa,
                    cargo_postulacion_id=cargo_post_id,
                    tipo=tipo,
                    defaults={'votos': cantidad}
                )

            # --- Resumen (upsert) ---
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

            # Flag de mesa
            if not mesa.escrutada:
                mesa.escrutada = True
                mesa.save(update_fields=['escrutada'])

        # -------- logs de negocio (después de commit exitoso) --------
        if not estaba_escrutada:
            audit.info(f"MESA_ESCRUTADA usuario={user.username} mesa_id={mesa.id}")
        else:
            # llegó acá con overwrite=True
            audit.info(f"MESA_EDITADA usuario={user.username} mesa_id={mesa.id}")

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        # Log técnico con stacktrace
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

    return JsonResponse({
        'status': 'ok',
        'escrutada': 1 if mesa.escrutada else 0,
        'cap': cap,
        'resumen': resumen,
        'votos_cargo': votos_cargo,
        'votos_especiales': votos_especiales,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@login_required
def mesa_datos(request, mesa_id):
    user = request.user

    # Solo operadores con escuela asignada
    if user.role != 'operador' or not user.escuela_id:
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)

    mesa = get_object_or_404(Mesa, id=mesa_id)

    # Chequear si el operador puede editar esa mesa
    if not request.user.puede_editar_mesa(mesa):
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)

    # CAP dinámico: 460 si mesa >= 9000 (extranjeros), si no 350
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

    return JsonResponse({
        'status': 'ok',
        'escrutada': 1 if mesa.escrutada else 0,
        'cap': cap,
        'resumen': resumen,
        'votos_cargo': votos_cargo,
        'votos_especiales': votos_especiales,
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

    mesas_escrutadas = (VotoMesaCargo.objects
                        .filter(partido_postulacion__cargo_postulacion=cargo,
                                mesa__in=mesas_visibles)
                        .values('mesa_id').distinct().count())
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

    # 👇 Admins y panelistas ven todas las mesas
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
        item['pct_dip'] = round((vd * 100 / total_dip), 2) if total_dip else 0.0
        item['pct_con'] = round((vc * 100 / total_con), 2) if total_con else 0.0

    filas = sorted(por_partido.values(), key=lambda x: (x['votos_dip'] + x['votos_con']), reverse=True)

    total_mesas = mesas_visibles.count()
    mesas_escrutadas = (VotoMesaCargo.objects
                        .filter(Q(partido_postulacion__cargo_postulacion=cargo_dip) |
                                Q(partido_postulacion__cargo_postulacion=cargo_con),
                                mesa__in=mesas_visibles)
                        .values('mesa_id').distinct().count())
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
    # 👇 Admins y panelistas ven todas las mesas
    if request.user.is_superuser or request.user.role in ("admin", "panelista"):
        mesas_visibles = Mesa.objects.all()
    else:
        mesas_visibles = request.user.mesas_visibles

    total_mesas = mesas_visibles.count()
    mesas_con_votos = (VotoMesaCargo.objects
                       .filter(mesa__in=mesas_visibles)
                       .values('mesa_id').distinct().count())
    pct = round(mesas_con_votos * 100 / total_mesas, 2) if total_mesas else 0
    return JsonResponse({
        'total_mesas': total_mesas,
        'mesas_escrutadas': mesas_con_votos,
        'porcentaje_escrutadas': pct,
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

from django.db.models import Sum

@login_required
def api_circuitos(request):
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

        # votos por partido en ese circuito
        votos_qs = (
            VotoMesaCargo.objects
            .filter(mesa__escuela__circuito=r)
            .values(
                "partido_postulacion__partido__nombre_partido",
                "partido_postulacion__partido__sigla"
            )
            .annotate(votos=Sum("votos"))
            .order_by("-votos")
        )

        # 👇 acá calculás el total de votos del circuito
        total_votos = sum(v["votos"] or 0 for v in votos_qs)

        partidos = []
        for v in votos_qs:
            votos = v["votos"] or 0
            ppct = (votos * 100 / total_votos) if total_votos else 0
            partidos.append({
                "sigla": v["partido_postulacion__partido__sigla"],
                "nombre": v["partido_postulacion__partido__nombre_partido"],
                "votos": votos,
                "porcentaje": round(ppct, 2)
            })

        items.append({
            'nombre': r.codigo_circuito,
            'escrutadas': esc,
            'total': total,
            'porcentaje': pct,
            'partidos': partidos,
        })

    items.sort(key=lambda x: x['nombre'])
    return JsonResponse({'items': items})


@login_required
def api_seccion_detalle(request, nombre):
    """
    Devuelve detalle de una sección:
    - votos por partido/lista con %.
    - circuitos que pertenecen a esa sección (avance escrutado).
    """
    try:
        seccion = Seccion.objects.get(nombre_seccion=nombre)
    except Seccion.DoesNotExist:
        return JsonResponse({"error": f"Sección {nombre} no encontrada"}, status=404)

    # === VOTOS POR PARTIDO EN ESA SECCIÓN ===
    votos_qs = (
        VotoMesaCargo.objects
        .filter(mesa__escuela__circuito__seccion=seccion)
        .values("partido_postulacion__partido__nombre_partido")
        .annotate(votos=Sum("votos"))
        .order_by("-votos")
    )

    total_votos = sum(v["votos"] or 0 for v in votos_qs)
    partidos = []
    for v in votos_qs:
        votos = v["votos"] or 0
        pct = (votos * 100 / total_votos) if total_votos else 0
        partidos.append({
            "nombre": v["partido_postulacion__partido__nombre_partido"],
            "votos": votos,
            "porcentaje": round(pct, 2)
        })

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
            "porcentaje": round(pct, 2)
        })

    return JsonResponse({
        "partidos": partidos,
        "circuitos": circuitos,
    })

# elecciones/views.py

@login_required
def panel_votantes(request):
    total = Adherente.objects.count()
    votaron = Adherente.objects.filter(voto=True).count()
    faltan = total - votaron

    # 👇 usuarios disponibles para exportar PDFs
    usuarios = (
        Adherente.objects
        .filter(voto=0)
        .values_list("creado_por_nombre", flat=True)
        .distinct()
        .order_by("creado_por_nombre")
    )

    return render(request, "panel/panel_votantes.html", {
        "adherentes": {
            "total": total,
            "votaron": votaron,
            "faltan": faltan,
        },
        "usuarios": usuarios,  # 👈 pasamos al template
    })


@login_required
def api_votantes(request):
    # --- Electores: SIEMPRE sobre Padron ---
    electores_total = Padron.objects.count()
    electores_votaron = Padron.objects.filter(voto=True).count()

    # --- Adherentes: SIEMPRE sobre Adherente ---
    adherentes_total = Adherente.objects.count()
    adherentes_votaron = Adherente.objects.filter(voto=True).count()

    return JsonResponse({
        "electores": {
            "total": electores_total,
            "votaron": electores_votaron,
        },
        "adherentes": {
            "total": adherentes_total,
            "votaron": adherentes_votaron,
        }
    })

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

@login_required
def api_votantes_marcados(request):
    """
    Devuelve los últimos 40 votantes marcados (voto=1) en Padron.
    Incluye escuela (texto), mesa (número) y orden.
    """
    rows = (Padron.objects
            .filter(voto=True)
            .order_by("-id")[:40])  # ✅ sin select_related

    data = []
    for r in rows:
        data.append({
            "escuela": r.escuela or "Sin asignar",  # ✅ ya es texto
            "mesa": r.mesa or "-",                  # ✅ es IntegerField
            "orden": r.orden or "-",                # ✅ es CharField
        })

    return JsonResponse({"votantes": data})

@login_required
def api_votantes_detalle(request):
    # Filtramos solo votantes (voto=1)
    qs = Padron.objects.filter(voto=True)

    nativos = qs.filter(mesa__lt=5000).count()
    extranjeros = qs.filter(mesa__gte=9000).count()
    total = nativos + extranjeros

    # --- cálculo de edades ---
    edades = {
        "16-20": qs.filter(edad__gte=16, edad__lte=20).count(),
        "21-27": qs.filter(edad__gte=21, edad__lte=27).count(),
        "28-39": qs.filter(edad__gte=28, edad__lte=39).count(),
        "40-55": qs.filter(edad__gte=40, edad__lte=55).count(),
        "56+":   qs.filter(edad__gte=56).count(),
    }
    total_edades = sum(edades.values()) or 1  # evitar división por 0

    # convertir a porcentajes
    edades_pct = {k: round(v * 100 / total_edades, 2) for k, v in edades.items()}

    data = {
        "nativos": {
            "total": nativos,
            "porcentaje": round((nativos * 100 / total), 2) if total else 0
        },
        "extranjeros": {
            "total": extranjeros,
            "porcentaje": round((extranjeros * 100 / total), 2) if total else 0
        },
        "edades": edades_pct
    }
    return JsonResponse(data)

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

