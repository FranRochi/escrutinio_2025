from django.shortcuts import render, redirect
from .models import Mesa, Partido, CargoPostulacion, PartidoPostulacion
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from collections import defaultdict
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Hacer login
            login(request, user)

            # Generar el token JWT
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            # Guardar el token en sessionStorage
            # Aquí lo puedes enviar al frontend para que lo almacenes
            response = redirect('/panel_operador')  # Redirigir al panel
            response.set_cookie('jwt_token', access_token)  # También se puede guardar en una cookie

            return response  # Redirigir al panel del operador

        else:
            return render(request, 'login.html', {'error': True})
    
    # Si la solicitud es GET, renderizar el formulario de login
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
        escuela = mesa.escuela.nombre_escuela
        circuito = mesa.circuito.numero_circuito
        data = {
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
