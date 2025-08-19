from django.shortcuts import render, redirect, get_object_or_404
from .models import Mesa, Partido, CargoPostulacion, PartidoPostulacion, VotoMesaCargo, VotoMesaEspecial, ResumenMesa
from django.contrib.auth import authenticate, login
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
from django.db.models import Sum

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
                return redirect('panel_panelista')
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
@login_required
def panel_operador(request):
    if request.user.role != 'operador':
        return HttpResponseForbidden("No tenés permiso para acceder a este panel.")
    if not request.user.escuela_id:
        return HttpResponseForbidden("Tu usuario no tiene una escuela asignada.")

    # 👇 solo mesas de su escuela y pendientes
    mesas = (Mesa.objects
                  .filter(escuela_id=request.user.escuela_id, escrutada=False)
                  .order_by('numero_mesa'))

    partidos = Partido.objects.all().order_by('numero_lista')
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

    tipos_voto_especial = ['blanco', 'impugnado', 'comando']

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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def guardar_votos(request):
    try:
        user = request.user
        if user.role != 'operador' or not user.escuela_id:
            return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)

        # Usamos request.data (NO leer request.body para evitar el error del stream)
        mesa_id = request.data.get('mesa_id')
        votos_cargo = request.data.get('votos_cargo', [])
        votos_especiales = request.data.get('votos_especiales', [])
        resumen_mesa = request.data.get('resumen_mesa', {})

        # La mesa debe existir y pertenecer a la escuela del usuario
        mesa = get_object_or_404(Mesa, id=mesa_id, escuela_id=user.escuela_id)

        if mesa.escrutada:
            return JsonResponse({
                'status': 'error',
                'message': f'La mesa {mesa.numero_mesa} ya fue escrutada.'
            })

        # --- votos por cargo (upsert para evitar duplicado por UNIQUE (mesa, partido_postulacion))
        for voto in votos_cargo:
            partido_postulacion_id = voto.get('partido_postulacion_id')
            votos = max(int(voto.get('votos', 0)), 0)

            VotoMesaCargo.objects.update_or_create(
                mesa=mesa,
                partido_postulacion_id=partido_postulacion_id,
                defaults={'votos': votos},
            )

        # --- votos especiales (filtrar tipos válidos)
        for voto in votos_especiales:
            tipo = voto['tipo']
            cargo_post_id = voto['cargo_postulacion_id']  # <-- asegúrate de mandarlo desde el front
            cantidad = int(voto.get('votos', 0))

            VotoMesaEspecial.objects.update_or_create(
                mesa=mesa,
                cargo_postulacion_id=cargo_post_id,
                tipo=tipo,
                defaults={'votos': cantidad}
            )

        # --- resumen (upsert por si reenvían)
        ResumenMesa.objects.update_or_create(
            mesa=mesa,
            defaults={
                'electores_votaron': int(resumen_mesa.get('electores_votaron', 0)),
                'sobres_encontrados': int(resumen_mesa.get('sobres_encontrados', 0)),
                'diferencia': int(resumen_mesa.get('diferencia', 0)),
                'escrutada': True,
            }
        )

        mesa.escrutada = True
        mesa.save(update_fields=['escrutada'])

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)



@login_required
def resultados_panelista(request):
    # habilitá panelistas y admins/súper
    if request.user.role not in ('panelista', 'admin') and not request.user.is_superuser:
        return HttpResponseForbidden("No tenés permiso para acceder a este panel.")

    # 👇 sin filtro por escuela: ve TODO
    mesas = Mesa.objects.all()
    mesas_con_votos = Mesa.objects.filter(votos_cargo__isnull=False).distinct().count()
    total_mesas = mesas.count()
    porcentaje_escrutadas = round((mesas_con_votos / total_mesas) * 100, 2) if total_mesas else 0

    # Agregados por cargo y por partido (para gráficos/tablas)
    votos_por_partido_y_cargo = {}
    qs = (VotoMesaCargo.objects
          .select_related('partido_postulacion__partido', 'partido_postulacion__cargo_postulacion')
          .values('partido_postulacion__cargo_postulacion__nombre_postulacion',
                  'partido_postulacion__partido__nombre_partido')
          .annotate(total=Sum('votos'))
          .order_by())

    for row in qs:
        cargo = row['partido_postulacion__cargo_postulacion__nombre_postulacion']
        partido = row['partido_postulacion__partido__nombre_partido']
        votos_por_partido_y_cargo.setdefault(cargo, {})[partido] = row['total']

    partidos_postulados = PartidoPostulacion.objects.select_related('partido', 'cargo_postulacion').all()

    # (opcional) matriz por mesa para la tabla detallada
    resultados = []
    for mesa in mesas:
        mesa_resultado = {
            'mesa': mesa,
            'resultados_cargos': {},
            'resultados_especiales': {}
        }

        for pp in partidos_postulados:
            total = (VotoMesaCargo.objects
                     .filter(mesa=mesa, partido_postulacion=pp)
                     .aggregate(s=Sum('votos'))['s'] or 0)
            mesa_resultado['resultados_cargos'][pp.partido.nombre_partido] = total

        for code, label in VotoMesaEspecial.TIPO_VOTO:
            total = (VotoMesaEspecial.objects
                     .filter(mesa=mesa, tipo=code)
                     .aggregate(s=Sum('votos'))['s'] or 0)
            mesa_resultado['resultados_especiales'][label] = total

        resultados.append(mesa_resultado)

    ahora = datetime.now()
    fecha_actual = ahora.strftime("%d/%m/%Y")
    hora_actual = ahora.strftime("%H:%M:%S")

    return render(request, 'panel_panelista.html', {
        'resultados': resultados,
        'mesas': mesas,
        'partidos_postulados': partidos_postulados,
        'porcentaje_escrutadas': porcentaje_escrutadas,
        'votos_por_partido_y_cargo': votos_por_partido_y_cargo,
        'fecha_actual': fecha_actual,
        'hora_actual': hora_actual
    })


