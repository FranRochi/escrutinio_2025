#AUDITORIA LIGERA (PATH SENSIBLES)

import json
import logging
import time
from django.utils.deprecation import MiddlewareMixin

audit = logging.getLogger("audit")

SENSITIVE_PATHS = (
    "/operador/guardar-votos/",
    "/operador/mesa/",
)

def _client_ip(request):
    xfwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if xfwd:
        return xfwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "-")

def _mesa_id_from_request(request):
    # 1) si viniera como form-data
    mesa_id = request.POST.get("mesa_id") or request.GET.get("mesa_id")
    if mesa_id:
        return mesa_id
    # 2) si viene como JSON (tu caso con fetch)
    if request.META.get("CONTENT_TYPE","").startswith("application/json"):
        try:
            body = request.body  # ⚠️ seguro: Django cachea request.body
            if body:
                data = json.loads(body.decode("utf-8"))
                return str(data.get("mesa_id", "-"))
        except Exception:
            return "-"
    return "-"

class AuditMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Guardamos el start time para medir duración
        request._audit_start = time.monotonic()

        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            path = request.path
            if any(path.startswith(p) for p in SENSITIVE_PATHS):
                user = request.user.username if request.user.is_authenticated else "anon"
                ip = _client_ip(request)
                mesa_id = _mesa_id_from_request(request)
                audit.info(
                    f"REQ {request.method} path={path} usuario={user} mesa_id={mesa_id} ip={ip}"
                )
        return None

    def process_response(self, request, response):
        # Log de salida sólo para paths sensibles y métodos de escritura
        try:
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                path = request.path
                if any(path.startswith(p) for p in SENSITIVE_PATHS):
                    dur_ms = 0
                    if hasattr(request, "_audit_start"):
                        dur_ms = int((time.monotonic() - request._audit_start) * 1000)
                    user = request.user.username if getattr(request, "user", None) and request.user.is_authenticated else "anon"
                    status = getattr(response, "status_code", "-")
                    audit.info(f"RES {request.method} path={path} usuario={user} status={status} dur_ms={dur_ms}")
        finally:
            return response
