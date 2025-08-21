import logging
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

audit = logging.getLogger("audit")

@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    ip = get_ip(request)
    audit.info(f"LOGIN usuario={user.username} ip={ip} ua={request.META.get('HTTP_USER_AGENT','')}")

@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    ip = get_ip(request)
    username = getattr(user, "username", "anon")
    audit.info(f"LOGOUT usuario={username} ip={ip} ua={request.META.get('HTTP_USER_AGENT','')}")

def get_ip(request):
    for h in ("HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"):
        v = request.META.get(h)
        if v:
            return v.split(",")[0].strip()
    return "-"
