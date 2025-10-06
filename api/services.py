import requests
from django.conf import settings

def sync_voto_adherentes(dni: str, sexo: str, accion: str) -> tuple[bool, str | None]:
    url = f"{settings.ADHERENTES_BASE_URL}/api/v1/votos/marcar"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.ADHERENTES_SYNC_TOKEN}",
    }
    data = {"dni": dni, "sexo": sexo, "accion": accion}
    try:
        r = requests.post(url, json=data, headers=headers, timeout=5)
        if 200 <= r.status_code < 300:   # ok
            return True, None
        if r.status_code == 404:         # no existe en Adherentes => no es fatal
            return True, None
        return False, f"HTTP {r.status_code}: {r.text}"
    except Exception as e:
        return False, str(e)
    
