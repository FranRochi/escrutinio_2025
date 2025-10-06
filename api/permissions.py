# api/permissions.py
from elecciones.models import Marcador

def usuario_puede_mesa(user, mesa_id: int) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    # operadores y admins pueden (telegrama / supervisión)
    if getattr(user, 'role', '') in ('admin', 'operador'):
        return True
    # marcadores: solo sus mesas habilitadas
    if getattr(user, 'role', '') == 'marcador':
        return Marcador.objects.filter(user=user, mesa_id=mesa_id, activo=True).exists()
    # otros roles (panelista, etc.) no marcan
    return False
