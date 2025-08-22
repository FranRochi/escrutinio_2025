# signals.py
import logging
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone  # NEW

audit = logging.getLogger("audit")

def get_ip(request):
    for h in ("HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"):
        v = request.META.get(h)
        if v:
            return v.split(",")[0].strip()
    return "-"

@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    ip = get_ip(request)
    audit.info(f"LOGIN usuario={user.username} ip={ip} ua={request.META.get('HTTP_USER_AGENT','')}")
    # NEW: marcar online
    try:
        user.last_seen = timezone.now()
        user.save(update_fields=['last_seen'])
    except Exception:
        audit.exception("No se pudo actualizar last_seen en login")

@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    ip = get_ip(request)
    username = getattr(user, "username", "anon")
    audit.info(f"LOGOUT usuario={username} ip={ip} ua={request.META.get('HTTP_USER_AGENT','')}")
    # Optional: registrar last_seen al logout también
    try:
        if user and user.is_authenticated:
            user.last_seen = timezone.now()
            user.save(update_fields=['last_seen'])
    except Exception:
        audit.exception("No se pudo actualizar last_seen en logout")
