from django.conf import settings

# Radice dei log scritti da rsyslog: <LOG_DIR>/netconsole-<nome o IP>/
LOG_DIR = getattr(settings, "OPENWISP_NETCONSOLE_LOG_DIR", "/opt/router-logs")
# Limiti di lettura per richiesta (la pagina chiede solo le righe nuove)
MAX_LINES = getattr(settings, "OPENWISP_NETCONSOLE_MAX_LINES", 1000)
MAX_BYTES = getattr(settings, "OPENWISP_NETCONSOLE_MAX_BYTES", 512 * 1024)
# Secondi tra un aggiornamento e l'altro mentre la scheda e' aperta
REFRESH = getattr(settings, "OPENWISP_NETCONSOLE_REFRESH", 5)
# Mostra anche le directory per IP (messaggi senza nome del device)
IP_FALLBACK = getattr(settings, "OPENWISP_NETCONSOLE_IP_FALLBACK", True)
# Rotazione dei log (pagina di admin): OpenWISP scrive qui i valori (directory
# sua), lo script di root li applica e scrive l'esito in un file suo
ROTATION_FILE = getattr(
    settings, "OPENWISP_NETCONSOLE_ROTATION_FILE", "/var/lib/openwisp-netconsole/rotation.json"
)
ROTATION_STATUS_FILE = getattr(
    settings, "OPENWISP_NETCONSOLE_ROTATION_STATUS_FILE", "/var/lib/router-logs-rotation/status.json"
)
