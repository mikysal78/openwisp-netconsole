"""Lettura dei log netconsole salvati da rsyslog.

Nessuna dipendenza da Django: riceve solo la directory radice dei log e le
chiavi gia' scelte dall'admin (nome del device e IP), cosi' si testa da sola.

Struttura su disco (rsyslog, vedi README):

    <log_dir>/netconsole-<chiave>/netconsole.log[.N[.gz]]

dove <chiave> e' il nome del device (userdata ``ninux_node``) oppure l'IP
sorgente per i messaggi senza nome.

Sicurezza: il client non passa mai un percorso. Sceglie una chiave tra quelle
restituite da ``device_sources`` e un nome di file tra quelli elencati da
``list_files``; tutto viene ricontrollato qui (regex, directory reale dentro
la radice, niente symlink) e i file si aprono con O_NOFOLLOW.
"""

import ipaddress
import os
import re
import stat

NAME_RE = re.compile(r"^[A-Za-z0-9][-A-Za-z0-9_.]{0,63}$")
FILE_RE = re.compile(r"^netconsole\.log(\.[0-9]{1,3}(\.gz)?)?$")
CURRENT_FILE = "netconsole.log"


def is_ip(value):
    try:
        ipaddress.ip_address(value)
    except (TypeError, ValueError):
        return False
    return True


def normalize_ip(value):
    """IP in forma canonica, oppure None se non e' un IP."""
    try:
        return str(ipaddress.ip_address(value))
    except (TypeError, ValueError):
        return None


def source_keys(name, ips):
    """Chiavi candidate: prima il nome, poi gli IP (senza duplicati).

    Un nome che e' esso stesso un IP viene scartato: leggerebbe la directory
    per IP di un altro router.
    """
    keys = []
    if name and NAME_RE.match(name) and not is_ip(name):
        keys.append(("name", name))
    for ip in ips:
        ip = normalize_ip(ip)
        if ip and ("ip", ip) not in keys:
            keys.append(("ip", ip))
    return keys


def _source_dir(log_dir, key):
    """Directory reale della chiave, o None se manca o non e' sicura."""
    if not (NAME_RE.match(key) or is_ip(key)):
        return None
    root = os.path.realpath(log_dir)
    path = os.path.join(root, "netconsole-" + key)
    try:
        st = os.lstat(path)
    except OSError:
        return None
    if not stat.S_ISDIR(st.st_mode):  # anche i symlink vengono scartati qui
        return None
    if os.path.dirname(os.path.realpath(path)) != root:
        return None
    return path


def device_sources(log_dir, keys):
    """Le chiavi che hanno davvero una directory di log: [(tipo, chiave)]."""
    return [(kind, key) for kind, key in keys if _source_dir(log_dir, key)]


def list_files(log_dir, key):
    """File di log della chiave: [(nome, dimensione)], il corrente per primo."""
    path = _source_dir(log_dir, key)
    if not path:
        return []
    files = []
    for entry in os.scandir(path):
        if not FILE_RE.match(entry.name):
            continue
        try:
            st = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        if stat.S_ISREG(st.st_mode):
            files.append((entry.name, st.st_size))

    def order(item):
        parts = item[0].split(".")
        return int(parts[2]) if len(parts) > 2 else 0

    return sorted(files, key=order)


def open_file(log_dir, key, filename):
    """Apre in lettura un file elencato da list_files; None se non ammesso."""
    path = _source_dir(log_dir, key)
    if not path or not FILE_RE.match(filename):
        return None
    try:
        fd = os.open(os.path.join(path, filename), os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    f = os.fdopen(fd, "rb")
    if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
        f.close()
        return None
    return f


def _decode(data):
    return data.decode("utf-8", "replace").splitlines()


def read_log(log_dir, key, pos=None, max_lines=1000, max_bytes=512 * 1024):
    """Ultime righe del file corrente, o solo quelle nuove dopo ``pos``.

    ``pos`` e' il valore restituito dalla chiamata precedente ("inode:offset").
    Se il file e' stato ruotato o troncato si riparte dalla coda.
    Restituisce (righe, nuovo_pos, reset); reset=True quando le righe
    sostituiscono quelle mostrate invece di aggiungersi.
    """
    f = open_file(log_dir, key, CURRENT_FILE)
    if f is None:
        return [], "", True
    with f:
        st = os.fstat(f.fileno())
        size = st.st_size
        start, reset = None, True
        if pos:
            inode, _, offset = pos.partition(":")
            if inode == str(st.st_ino) and offset.isdigit():
                offset = int(offset)
                if offset <= size and size - offset <= max_bytes:
                    start, reset = offset, False
        if start is None:
            start = max(0, size - max_bytes)
        f.seek(start)
        data = f.read(min(size - start, max_bytes))
        end = start + len(data)
        if reset and start > 0:
            # la prima riga e' tagliata a meta': si scarta
            nl = data.find(b"\n")
            data = data[nl + 1 :] if nl >= 0 else b""
        # solo righe complete: quella ancora in scrittura arriva al giro dopo
        cut = data.rfind(b"\n") + 1
        end -= len(data) - cut
        lines = _decode(data[:cut])[-max_lines:]
        return lines, "%d:%d" % (st.st_ino, end), reset
