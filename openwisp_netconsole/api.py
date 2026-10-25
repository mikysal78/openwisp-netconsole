"""API per le app (per esempio openwisp-android): ultime righe netconsole.

    GET /api/v1/netconsole/device/<uuid>/logs/?lines=200
    Authorization: Bearer <token di openwisp-users>
    -> 200 [{"kind": "name", "key": "C2600", "lines": ["...", ...]}, ...]

Gli stessi controlli della scheda nell'admin: utente staff attivo, superuser
oppure manager dell'organizzazione del device con il permesso di vederlo; i
log sono solo quelli di sources.device_sources (mai un percorso dal client).

Si accetta solo il token Bearer, mai la sessione del browser. Un device che
l'utente non puo' vedere risponde 404 come uno che non esiste.
"""

import os

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from . import logfiles, sources
from . import settings as app_settings

MAX_TOKEN_LENGTH = 128
DEFAULT_LINES = 200
# file ruotato non compresso (logrotate con delaycompress)
PREVIOUS_FILE = "netconsole.log.1"


def _token_model():
    from rest_framework.authtoken.models import Token

    return Token


def _device_model():
    from swapper import load_model

    return load_model("config", "Device")


def token_user(request):
    """Utente attivo del token Bearer (lo stesso di openwisp-users), o None."""
    kind, _, key = request.META.get("HTTP_AUTHORIZATION", "").partition(" ")
    key = key.strip()
    if kind.lower() != "bearer" or not key or len(key) > MAX_TOKEN_LENGTH:
        return None
    Token = _token_model()
    try:
        user = Token.objects.select_related("user").get(key=key).user
    except Token.DoesNotExist:
        return None
    return user if user.is_active else None


def can_view(user, device, device_model):
    if not user.is_active or not user.is_staff:
        return False
    if user.is_superuser:
        return True
    opts = device_model._meta
    perms = ["%s.%s_%s" % (opts.app_label, action, opts.model_name) for action in ("view", "change")]
    return any(user.has_perm(p) for p in perms) and user.is_manager(device.organization_id)


def _json(data, status=200):
    response = JsonResponse(data, status=status, safe=False)
    response["Cache-Control"] = "no-store"
    return response


@never_cache
@require_GET
def logs(request, pk):
    user = token_user(request)
    if user is None:
        return _json({"detail": "Invalid or missing token."}, 401)
    Device = _device_model()
    try:
        device = Device.objects.get(pk=pk)
    except Device.DoesNotExist:
        return _json({"detail": "Not found."}, 404)
    if not can_view(user, device, Device):
        return _json({"detail": "Not found."}, 404)
    try:
        lines = int(request.GET.get("lines", DEFAULT_LINES))
    except ValueError:
        lines = DEFAULT_LINES
    lines = max(1, min(lines, app_settings.MAX_LINES))
    out = []
    for kind, key in sources.device_sources(device, Device):
        out.append({"kind": kind, "key": key, "lines": tail(key, lines)})
    return _json(out)


def tail(key, lines):
    """Ultime righe; se il file corrente ne ha meno (appena ruotato, o mai
    riscritto dopo la rotazione) si completa con il file precedente."""
    text, _, _ = logfiles.read_log(
        app_settings.LOG_DIR, key, "", max_lines=lines, max_bytes=app_settings.MAX_BYTES
    )
    if len(text) >= lines:
        return text
    f = logfiles.open_file(app_settings.LOG_DIR, key, PREVIOUS_FILE)
    if f is None:
        return text
    with f:
        size = os.fstat(f.fileno()).st_size
        start = max(0, size - app_settings.MAX_BYTES)
        f.seek(start)
        data = f.read(app_settings.MAX_BYTES)
    if start > 0:
        # la prima riga e' tagliata a meta': si scarta
        data = data[data.find(b"\n") + 1 :] if b"\n" in data else b""
    previous = data.decode("utf-8", "replace").splitlines()
    return (previous + text)[-lines:]
