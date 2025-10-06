# api/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from elecciones.models import Marcador, MarcacionTemp

# --- API mínima: sólo mi_mesa ---

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mi_mesa(request):
    """
    Devuelve la mesa asignada al usuario en Escrutinio.
    Registro la consume en login y guarda en sesión.
    """
    try:
        marcador = request.user.mesas_habilitadas.select_related('mesa__escuela').get(activo=True)
        mesa = marcador.mesa

        historial = list(
            MarcacionTemp.objects
            .filter(user=request.user, mesa=mesa)
            .values("id", "orden", "dni")
            .order_by("-created_at")[:30]
        )

        return Response({
            "status": "ok",
            "mesa": mesa.numero_mesa,
            "escuela": mesa.escuela.nombre_escuela,
            "historial": historial,
        })
    except Marcador.DoesNotExist:
        return Response({"status": "error", "msg": "No tenés mesa asignada."}, status=403)
