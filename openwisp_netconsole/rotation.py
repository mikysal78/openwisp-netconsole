"""Impostazioni di rotazione dei log dei router, scambiate con lo script di root.

OpenWISP (utente non privilegiato) non scrive mai configurazioni di sistema:
salva solo un JSON con questi valori. Lo script orario di root che esegue
logrotate lo rilegge, ricontrolla gli stessi limiti (vedi
``router-logs-rotation`` nel repo openwisp2), genera la configurazione da un
modello fisso e scrive l'esito in un file suo, che la pagina di admin mostra.

Nessuna dipendenza da Django, per poterlo testare da solo.
"""

import json
import os
import tempfile

FREQUENCIES = ("daily", "weekly", "monthly")
# nome: (minimo, massimo). Limiti stretti di proposito: chi prendesse il
# controllo di OpenWISP potrebbe solo scegliere valori in questi intervalli,
# cioe' non riempire /opt (16 GB) ne' far sparire i log in poche ore.
LIMITS = {
    "max_size_mb": (5, 100),
    "retention_days": (7, 90),
    "max_files": (7, 60),
}
MAX_FILE_SIZE = 4096


def validate(values):
    """Valori puliti, oppure ValueError: gli stessi controlli dello script."""
    if not isinstance(values, dict):
        raise ValueError("not an object")
    clean = {}
    if values.get("frequency") not in FREQUENCIES:
        raise ValueError("frequency")
    clean["frequency"] = values["frequency"]
    for name, (low, high) in LIMITS.items():
        value = values.get(name)
        # bool e' una sottoclasse di int: True non e' un numero valido
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(name)
        clean[name] = value
    return clean


def write_settings(path, values):
    """Scrive il JSON in modo atomico (file temporaneo e rename)."""
    data = json.dumps(validate(values), sort_keys=True).encode()
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".rotation-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path):
    """Legge un JSON piccolo senza seguire symlink; None se manca o non va."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    with os.fdopen(fd, "rb") as f:
        data = f.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        return None
    try:
        return json.loads(data)
    except ValueError:
        return None


def read_status(path):
    """Esito scritto dallo script di root: dict o None."""
    status = read_json(path)
    return status if isinstance(status, dict) else None
