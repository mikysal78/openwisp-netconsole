"""Quali log netconsole appartengono a un device (scheda dell'admin e API).

Le chiavi sono il nome del device e, con IP_FALLBACK, il suo IP di gestione e
l'ultimo IP. Una chiave condivisa con un altro device non viene usata:
netconsole-<chiave> potrebbe contenere i log dell'altro, anche di un'altra
organizzazione (il nome di un device non e' univoco).
"""

from django.db.models import Q

from . import logfiles
from . import settings as app_settings


def device_sources(device, device_model):
    """[(tipo, chiave)] con una directory di log, solo di questo device."""
    others = device_model.objects.exclude(pk=device.pk)
    ips = []
    if app_settings.IP_FALLBACK:
        ips = [device.management_ip, device.last_ip]
    keys = []
    for kind, key in logfiles.source_keys(device.name, ips):
        if kind == "name":
            shared = others.filter(name=key).exists()
        else:
            shared = others.filter(Q(management_ip=key) | Q(last_ip=key)).exists()
        if not shared:
            keys.append((kind, key))
    return logfiles.device_sources(app_settings.LOG_DIR, keys)
