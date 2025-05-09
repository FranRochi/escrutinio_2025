from django.shortcuts import render, redirect, get_object_or_404
from .models import Mesa, Partido, CargoPostulacion, PartidoPostulacion, VotoMesaCargo, VotoMesaEspecial, ResumenMesa
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseForbidden, JsonResponse
from collections import defaultdict
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            # Redirigir según el rol del usuario
            if user.role == 'operador':
                response = redirect('/panel_operador')
            elif user.role == 'panelista':
                response = redirect('/panel-panelista/')
            elif user.role == 'admin':
                response = redirect('/admin/')  # o lo que tengas para admin
            else:
                return render(request, 'login.html', {'error': True, 'mensaje': 'Rol desconocido'})

            response.set_cookie('jwt_token', access_token)
            return response

        else:
            return render(request, 'login.html', {'error': True})
    
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

@api_view(['GET'])
@permission_classes([AllowAny])
def obtener_datos_mesa(request):
    numero_mesa = request.GET.get('numero_mesa', None)
    if not numero_mesa:
        return JsonResponse({'error': 'Número de mesa no proporcionado'}, status=400)

    try:
        mesa = Mesa.objects.get(numero_mesa=numero_mesa)
        
        # Verificación si la mesa ya fue escrutada
        if mesa.escrutada:
            return JsonResponse({'error': 'Esta mesa ya fue escrutada'}, status=400)

        # Si no ha sido escrutada, devolver la información de escuela y circuito
        escuela = mesa.escuela.nombre_escuela
        circuito = mesa.circuito.numero_circuito
        data = {
            'id': mesa.id,
            'escuela': escuela,
            'circuito': circuito
        }
        return JsonResponse(data)
    
    except Mesa.DoesNotExist:
        return JsonResponse({'error': 'Mesa no encontrada'}, status=404)

@login_required
def panel_operador(request):
    if request.user.role != 'operador':
        return HttpResponseForbidden("No tenés permiso para acceder a este panel.")

    mesas = Mesa.objects.all()
    partidos = Partido.objects.all()
    cargos = CargoPostulacion.objects.all()

    # Mapeo de partidos a sus candidaturas por cargo
    partidos_map = []
    for partido in partidos:
        candidatura_por_cargo = {}
        for candidatura in PartidoPostulacion.objects.filter(partido=partido):
            candidatura_por_cargo[candidatura.cargo_postulacion.id] = candidatura
        partidos_map.append({
            'partido': partido,
            'candidaturas': candidatura_por_cargo
        })

    # Tipos de votos especiales (puede estar hardcodeado)
    tipos_voto_especial = ['nulo', 'blanco', 'recurrido', 'impugnado', 'comando']

    context = {
        'mesas': mesas,
        'partidos': partidos,
        'cargos': cargos,
        'partidos_map': partidos_map,
        'tipos_voto_especial': tipos_voto_especial,
    }

    return render(request, 'panel_operador/panel_operador.html', context)

def es_operador(user):
    return user.groups.filter(name="operarios").exists()

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def guardar_votos(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            numero_mesa = data.get('mesa_id')
            votos_cargo = data.get('votos_cargo')
            votos_especiales = data.get('votos_especiales')
            resumen_mesa = data.get('resumen_mesa')

            mesa = Mesa.objects.get(numero_mesa=numero_mesa)

            for voto in votos_cargo:
                partido_postulacion_id = voto['partido_postulacion_id']
                votos = voto['votos']
                partido_postulacion = PartidoPostulacion.objects.get(id=partido_postulacion_id)
                VotoMesaCargo.objects.create(
                    mesa=mesa,
                    partido_postulacion=partido_postulacion,
                    votos=votos
                )

            for voto in votos_especiales:
                    try:
                        tipo = voto['tipo']
                        votos = voto['votos']
                        print(f"Registrando voto especial: tipo={tipo}, votos={votos}")  # DEBUG
                        VotoMesaEspecial.objects.update_or_create(
                            mesa=mesa,
                            tipo=tipo,
                            defaults={'votos': votos}
                        )
                    except Exception as e:
                        print(f"Error en voto especial: {e}")  # DEBUG
                        return JsonResponse({'status': 'error', 'message': f'Error al guardar voto especial: {str(e)}'})


            ResumenMesa.objects.create(
                mesa=mesa,
                electores_votaron=resumen_mesa['electores_votaron'],
                sobres_encontrados=resumen_mesa['sobres_encontrados'],
                diferencia=resumen_mesa['diferencia'],
                escrutada=resumen_mesa['escrutada']
            )

            return JsonResponse({'status': 'ok'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})


def resultados_panelista(request):
    mesas = Mesa.objects.all()
    mesas_con_votos = Mesa.objects.filter(votos_cargo__isnull=False).distinct().count()
    total_mesas = mesas.count()

    grafico_datos = defaultdict(lambda: defaultdict(int))

    porcentaje_escrutadas = round((mesas_con_votos / total_mesas) * 100, 2) if total_mesas else 0

    votos_por_partido_y_cargo = defaultdict(lambda: defaultdict(int))

    for voto in VotoMesaCargo.objects.select_related('partido_postulacion__partido', 'partido_postulacion__cargo_postulacion'):
        cargo = voto.partido_postulacion.cargo_postulacion.nombre_postulacion
        partido = voto.partido_postulacion.partido.nombre_partido
        votos_por_partido_y_cargo[cargo][partido] += voto.votos

    # Convertimos defaultdict a dict normal para pasar al template
    grafico_datos = {partido: dict(cargos) for partido, cargos in grafico_datos.items()}

    votos_por_partido_y_cargo = {cargo: dict(partidos) for cargo, partidos in votos_por_partido_y_cargo.items()}

    partidos_postulados = PartidoPostulacion.objects.all()

    resultados = []
    for mesa in mesas:
        mesa_resultado = {
            'mesa': mesa,
            'resultados_cargos': {},
            'resultados_especiales': {}
        }

        for partido_postulacion in partidos_postulados:
            votos = VotoMesaCargo.objects.filter(mesa=mesa, partido_postulacion=partido_postulacion)
            mesa_resultado['resultados_cargos'][partido_postulacion.partido.nombre_partido] = sum(voto.votos for voto in votos)

        for tipo_voto in VotoMesaEspecial.TIPO_VOTO:
            votos_especiales = VotoMesaEspecial.objects.filter(mesa=mesa, tipo=tipo_voto[0])
            mesa_resultado['resultados_especiales'][tipo_voto[1]] = sum(voto.votos for voto in votos_especiales)

        resultados.append(mesa_resultado)

    return render(request, 'panel_panelista/panel_panelista.html', {
        'resultados': resultados,
        'mesas': mesas,
        'partidos_postulados': partidos_postulados,
        'porcentaje_escrutadas': porcentaje_escrutadas,
        'votos_por_partido_y_cargo': votos_por_partido_y_cargo
    })

