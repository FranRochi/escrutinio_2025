from django.shortcuts import render, redirect, get_object_or_404
from .models import Mesa, Subcomando, Partido, CargoPostulacion, PartidoPostulacion, VotoMesaCargo, VotoMesaEspecial, ResumenMesa
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
            elif getattr(user, 'role', None) == 'panelista':
                return redirect('panel_dashboard')
            elif getattr(user, 'role', None) == 'admin' or user.is_superuser:
                return redirect('/admin/')
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

    user = authenticate(request, username=username, password=password)

    if user is not None:
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        return Response({'access_token': access_token})
    else:
        return Response({'error': 'Credenciales inválidas'}, status=401)


# views.py
@never_cache
@login_required
def panel_operador(request):
    if request.user.role != 'operador':
        return HttpResponseForbidden("No tenés permiso para acceder a este panel.")
    if not request.user.escuela_id:
        return HttpResponseForbidden("Tu usuario no tiene una escuela asignada.")

    # 👇 solo mesas de su escuela y pendientes
    mesas = (Mesa.objects
                  .filter(escuela_id=request.user.escuela_id)
                  .order_by('numero_mesa'))

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
        'escuela_nombre': request.user.escuela.nombre_escuela,
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

    if not (user.is_authenticated and getattr(user, "role", None) == "operador" and getattr(user, "escuela_id", None)):
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)

    # DRF ya parseó JSON en request.data (no tocar request.body)
    mesa_id = request.data.get('mesa_id')
    votos_cargo = request.data.get('votos_cargo', []) or []
    votos_especiales = request.data.get('votos_especiales', []) or []
    resumen_mesa = request.data.get('resumen_mesa', {}) or {}
    overwrite = bool(request.data.get('overwrite'))

    # Mesa válida y de la escuela del operador
    mesa = get_object_or_404(Mesa, id=mesa_id, escuela_id=user.escuela_id)

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
def mesa_datos(request, mesa_id):
    user = request.user
    if user.role != 'operador' or not user.escuela_id:
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)

    mesa = get_object_or_404(Mesa, id=mesa_id, escuela_id=user.escuela_id)

    # Resumen (si existe)
    resumen_obj = ResumenMesa.objects.filter(mesa=mesa).first()
    resumen = {
        'electores_votaron': resumen_obj.electores_votaron if resumen_obj else 0,
        'sobres_encontrados': resumen_obj.sobres_encontrados if resumen_obj else 0,
        'diferencia': resumen_obj.diferencia if resumen_obj else 0,
    }

    # Votos por agrupación
    votos_cargo = list(
        VotoMesaCargo.objects.filter(mesa=mesa)
        .values('partido_postulacion_id', 'partido_postulacion__cargo_postulacion_id', 'votos')
    )
    # Renombrar claves para que coincida con el front:
    votos_cargo = [
        {
            'partido_postulacion_id': v['partido_postulacion_id'],
            'cargo_id': v['partido_postulacion__cargo_postulacion_id'],
            'votos': v['votos'],
        }
        for v in votos_cargo
    ]

    # Votos especiales
    votos_especiales = list(
        VotoMesaEspecial.objects.filter(mesa=mesa)
        .values('cargo_postulacion_id', 'tipo', 'votos')
    )

    return JsonResponse({
        'status': 'ok',
        'escrutada': 1 if mesa.escrutada else 0,
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
    from django.db.models import Sum
    cargo_id = request.GET.get('cargo_id')
    cargo_name = (request.GET.get('cargo') or '').strip()

    cargo = None
    if cargo_id and cargo_id.isdigit():
        cargo = CargoPostulacion.objects.filter(id=int(cargo_id)).first()
    if not cargo and cargo_name:
        # Mapeo tolerante
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

    qs = (VotoMesaCargo.objects
          .select_related('partido_postulacion__partido', 'partido_postulacion__cargo_postulacion')
          .filter(partido_postulacion__cargo_postulacion=cargo)
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
                        .filter(partido_postulacion__cargo_postulacion=cargo)
                        .values('mesa_id').distinct().count())
    total_mesas = Mesa.objects.count()
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
    """
    Devuelve una tabla combinada por partido con columnas:
    votos_dip, pct_dip, votos_con, pct_con.

    Si no pasan ids, usa por nombre:
    - 'Diputados Provinciales'
    - 'Concejales'
    """
    from django.db.models import Sum, Q

    # Permite pasar ?dip_id= & con_id= (opcional)
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

    # Un solo query: sumas por partido y cargo
    qs = (VotoMesaCargo.objects
          .select_related('partido_postulacion__partido', 'partido_postulacion__cargo_postulacion')
          .filter(partido_postulacion__cargo_postulacion__in=[cargo_dip, cargo_con])
          .values('partido_postulacion__partido__pk',
                  'partido_postulacion__partido__nombre_partido',
                  'partido_postulacion__cargo_postulacion__id')
          .annotate(votos=Sum('votos')))

    # Totales por cargo para % (evitamos división por 0)
    total_dip = 0
    total_con = 0
    for r in qs:
        if r['partido_postulacion__cargo_postulacion__id'] == cargo_dip.id:
            total_dip += r['votos'] or 0
        else:
            total_con += r['votos'] or 0

    # Armado por partido
    por_partido = {}
    for r in qs:
        pid = r['partido_postulacion__partido__pk']  # Partido.pk (tu PK es numero_lista)
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

    # % por cargo
    for item in por_partido.values():
        vd, vc = item['votos_dip'], item['votos_con']
        item['pct_dip'] = round((vd * 100 / total_dip), 2) if total_dip else 0.0
        item['pct_con'] = round((vc * 100 / total_con), 2) if total_con else 0.0

    # Orden: por suma de ambos votos desc
    filas = sorted(por_partido.values(), key=lambda x: (x['votos_dip'] + x['votos_con']), reverse=True)

    # Avance mesas (global)
    total_mesas = Mesa.objects.count()
    mesas_escrutadas = (VotoMesaCargo.objects
                        .filter(Q(partido_postulacion__cargo_postulacion=cargo_dip) |
                                Q(partido_postulacion__cargo_postulacion=cargo_con))
                        .values('mesa_id').distinct().count())
    pct_mesas = round(mesas_escrutadas * 100 / total_mesas, 2) if total_mesas else 0

    return JsonResponse({
        'cargos': {
            'diputados': {'id': cargo_dip.id, 'nombre': cargo_dip.nombre_postulacion, 'total_validos': total_dip},
            'concejales': {'id': cargo_con.id, 'nombre': cargo_con.nombre_postulacion, 'total_validos': total_con},
        },
        'rows': filas,
        'mesas_escrutadas': mesas_escrutadas,
        'total_mesas': total_mesas,
        'porcentaje_mesas': pct_mesas,
        'timestamp': timezone.now().strftime('%d/%m/%Y %H:%M:%S'),
    })


@login_required
def api_metadata(request):
    """
    Meta general del proceso (todas las mesas / escrutadas con cualquier cargo).
    """
    total_mesas = Mesa.objects.count()
    mesas_con_votos = VotoMesaCargo.objects.values('mesa_id').distinct().count()
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
    # Subcomandos con nombre
    rows = (Subcomando.objects
            .annotate(
                total=Count('escuelas__mesas', distinct=True),
                escrutadas=Count('escuelas__mesas',
                                 filter=Q(escuelas__mesas__escrutada=True),
                                 distinct=True)
            )
            .order_by('nombre_subcomando'))

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

    return JsonResponse({'items': items})

#---PANEL DE GRAFICOS-----
@login_required
def panel_graficos(request):
    return render(request, "panel/panel_graficos.html")

#----PANEL DE RESULTADOS----
def panel_resultados(request):
    return render(request, 'panel/panel_resultados.html')


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
