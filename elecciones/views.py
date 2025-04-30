from django.shortcuts import render, redirect
from .models import Mesa, Partido, CargoPostulacion, PartidoPostulacion
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from collections import defaultdict

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            # Redirige según el rol
            if user.role == 'operador':
                return redirect('panel_operador')
            elif user.role == 'panelista':
                return redirect('panel_panelista')  # Cuando tengas ese panel
            elif user.role == 'admin':
                return redirect('admin_dashboard')  # O lo que sea el panel para admins
            else:
                return HttpResponseForbidden("No tenés permisos para acceder.")
        else:
            return render(request, 'login.html', {'error': True})  # Aquí pasamos 'error'

    return render(request, 'login.html', {'error': False})

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


