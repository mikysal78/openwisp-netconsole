# openwisp-netconsole

[🇬🇧 English](README.md) | 🇮🇹 Italiano

[![CI](https://github.com/mikysal78/openwisp-netconsole/actions/workflows/ci.yml/badge.svg)](https://github.com/mikysal78/openwisp-netconsole/actions/workflows/ci.yml)

Scheda **Netconsole** nella pagina del device di [OpenWISP](https://openwisp.org/):
mostra in tempo reale i messaggi del kernel che il router invia con
[netconsole](https://docs.kernel.org/networking/netconsole.html) e salvati sul
server da rsyslog. Serve soprattutto per i blocchi e i kernel panic, quando il
syslog non fa in tempo a partire.

Nato per la rete [NINUX Basilicata](https://github.com/mikysal78/openwisp2),
dove i router mandano netconsole al server OpenWISP.

## Come funziona

```
router (netconsole, formato esteso + userdata ninux_node=<nome>)
   │ UDP 6666
   ▼
rsyslog  ──►  <LOG_DIR>/netconsole-<nome del device>/netconsole.log
              <LOG_DIR>/netconsole-<ip sorgente>/netconsole.log   (messaggi senza nome)
   ▲
   │ sola lettura
OpenWISP: scheda «Netconsole» del device
```

- La scheda mostra la cartella con il nome del device e quelle con il suo IP di
  gestione e il suo ultimo IP.
- Chiede al server solo le righe nuove ogni pochi secondi, mentre la scheda è
  aperta e la pagina è visibile.
- Elenca i file ruotati (`netconsole.log.1`, `.gz`…) per scaricarli.
- Si aggiunge all'admin del device già registrato (anche quello di
  openwisp-monitoring) senza sostituirlo.

## Installazione

Dalla [release](https://github.com/mikysal78/openwisp-netconsole/releases)
(wheel già compilato, con `SHA256SUMS`):

```bash
pip install https://github.com/mikysal78/openwisp-netconsole/releases/download/v0.1.1/openwisp_netconsole-0.1.1-py3-none-any.whl
```

oppure dal tag git:

```bash
pip install "openwisp-netconsole @ git+https://github.com/mikysal78/openwisp-netconsole@v0.1.1"
```

In `settings.py`, **dopo** `openwisp_controller.config` e
`openwisp_monitoring.device`:

```python
INSTALLED_APPS += ["openwisp_netconsole"]
```

Poi `collectstatic` e riavvio di OpenWISP. Con il ruolo
[ansible-openwisp2](https://github.com/openwisp/ansible-openwisp2):
`openwisp2_extra_python_packages` e `openwisp2_extra_django_apps`.

L'utente con cui gira OpenWISP (es. `www-data`) deve poter **leggere** la
directory dei log: conviene un gruppo dedicato, non `adm`.

### Playbook di esempio

Un playbook di base con il ruolo ufficiale
[ansible-openwisp2](https://github.com/openwisp/ansible-openwisp2): installa il
modulo e prepara il lato server per i log dei router (rsyslog, il gruppo
`router-logs` in sola lettura, lo script di rotazione di root e il suo cron).
È [`examples/ansible/playbook.yml`](examples/ansible/playbook.yml); i due
template che usa sono in [`examples/ansible/templates/`](examples/ansible/templates/).
La CI lo controlla con `--syntax-check`, `ansible-lint` e `rsyslogd -N1`, e
prova lo script di rotazione contro iniezioni, symlink e FIFO.

```bash
ansible-galaxy role install openwisp.openwisp2
cd examples/ansible
ansible-playbook -i hosts playbook.yml
```

```yaml
---
# Basic example: OpenWISP with openwisp-netconsole, installed with the
# official ansible-openwisp2 role, plus the server side for the router logs
# (rsyslog, read-only permissions, rotation managed from the admin page).
#
#   ansible-galaxy role install openwisp.openwisp2
#   ansible-playbook -i hosts playbook.yml
#
# The templates are in templates/ next to this file.

- name: OpenWISP with openwisp-netconsole
  hosts: openwisp2
  become: true
  roles:
    - openwisp.openwisp2
  vars:
    openwisp2_extra_python_packages:
      - "openwisp-netconsole @ https://github.com/mikysal78/openwisp-netconsole/releases/download/v0.1.1/openwisp_netconsole-0.1.1-py3-none-any.whl"
    # The role appends extra apps at the end of INSTALLED_APPS, after
    # openwisp_controller and openwisp_monitoring, as the module requires.
    openwisp2_extra_django_apps:
      - openwisp_netconsole

- name: Router logs (rsyslog, permissions, rotation)
  hosts: openwisp2
  become: true
  vars:
    router_logs_dir: /opt/router-logs
    # Read-only group for OpenWISP (www-data): not adm, which would give
    # OpenWISP access to all the system logs
    router_logs_group: router-logs
    router_logs_syslog_port: 514
    router_logs_netconsole_port: 6666
    # Rotation starting values; afterwards they are changed from the admin
    # page and running the playbook again does not overwrite them
    router_logs_frequency: daily # daily, weekly or monthly
    router_logs_max_size_mb: 50 # 5-100
    router_logs_retention_days: 30 # 7-90
    router_logs_max_files: 30 # 7-60
    # Defaults of OPENWISP_NETCONSOLE_ROTATION_FILE / _STATUS_FILE
    router_logs_rotation_settings_file: /var/lib/openwisp-netconsole/rotation.json
    router_logs_rotation_status_file: /var/lib/router-logs-rotation/status.json

  tasks:
    - name: Install rsyslog and logrotate
      ansible.builtin.apt:
        name: [rsyslog, logrotate]
        state: present

    - name: Router logs group
      ansible.builtin.group:
        name: "{{ router_logs_group }}"
        system: true

    # Group membership applies to processes started afterwards
    - name: OpenWISP (www-data) reads the router logs
      ansible.builtin.user:
        name: www-data
        groups: "{{ router_logs_group }}"
        append: true
      notify: Restart openwisp2

    - name: Router logs directory
      ansible.builtin.file:
        path: "{{ router_logs_dir }}"
        state: directory
        owner: root
        group: "{{ router_logs_group }}"
        mode: "0750"

    - name: Rsyslog configuration for the routers
      ansible.builtin.template:
        src: templates/rsyslog-router-logs.conf.j2
        dest: /etc/rsyslog.d/30-router-logs.conf
        mode: "0644"
      notify: Restart rsyslog

    - name: Rotation settings directory (written by OpenWISP)
      ansible.builtin.file:
        path: "{{ router_logs_rotation_settings_file | dirname }}"
        state: directory
        owner: www-data
        group: www-data
        mode: "0755"

    - name: Rotation status directory (written by root)
      ansible.builtin.file:
        path: "{{ router_logs_rotation_status_file | dirname }}"
        state: directory
        owner: root
        group: root
        mode: "0755"

    # Only if missing: after the first run the values are the ones chosen
    # on the admin page
    - name: Rotation starting values
      ansible.builtin.copy:
        dest: "{{ router_logs_rotation_settings_file }}"
        owner: www-data
        group: www-data
        mode: "0644"
        force: false
        content: "{{ {'frequency': router_logs_frequency,
                      'max_size_mb': router_logs_max_size_mb | int,
                      'retention_days': router_logs_retention_days | int,
                      'max_files': router_logs_max_files | int} | to_json }}\n"

    - name: Router log rotation script
      ansible.builtin.template:
        src: templates/router-logs-rotation.py.j2
        dest: /usr/local/sbin/router-logs-rotation
        owner: root
        group: root
        mode: "0755"
      notify: Generate the logrotate configuration

    - name: Hourly rotation (applies the admin values and maxsize)
      ansible.builtin.copy:
        dest: /etc/cron.d/router-logs
        mode: "0644"
        content: |
          # Managed by Ansible: do not edit
          17 * * * * root /usr/local/sbin/router-logs-rotation

  handlers:
    # Validate the whole configuration first: with an error rsyslog would
    # start ignoring the rules, the server ones included
    - name: Restart rsyslog
      ansible.builtin.shell: rsyslogd -N1 -f /etc/rsyslog.conf && systemctl restart rsyslog
      changed_when: true

    - name: Restart openwisp2 # noqa: command-instead-of-module (no community.general needed)
      ansible.builtin.command: supervisorctl restart openwisp2
      changed_when: true

    - name: Generate the logrotate configuration
      ansible.builtin.command: /usr/local/sbin/router-logs-rotation --config-only
      changed_when: true
```

Poi limitate con il firewall chi può inviare su UDP 514/6666.

### Impostazioni

| Impostazione | Default | Significato |
|---|---|---|
| `OPENWISP_NETCONSOLE_LOG_DIR` | `/opt/router-logs` | radice delle cartelle `netconsole-*` |
| `OPENWISP_NETCONSOLE_MAX_LINES` | `1000` | righe massime per richiesta |
| `OPENWISP_NETCONSOLE_MAX_BYTES` | `524288` | byte massimi letti per richiesta |
| `OPENWISP_NETCONSOLE_REFRESH` | `5` | secondi tra un aggiornamento e l'altro (minimo 2) |
| `OPENWISP_NETCONSOLE_IP_FALLBACK` | `True` | mostra anche le cartelle per IP |

### Rotazione dei log

La pagina **Monitoring → Rotazione dei log dei router**, visibile solo ai
superuser, imposta la rotazione dei log dei router: syslog e netconsole.

| Campo nella pagina | Chiave JSON | Variabile del playbook | Valori ammessi | Predefinito |
|---|---|---|---|---|
| Frequenza della rotazione | `frequency` | `router_logs_frequency` | `daily`, `weekly`, `monthly` | `daily` |
| Dimensione massima (MB) | `max_size_mb` | `router_logs_max_size_mb` | 5–100 (controllo ogni ora) | `50` |
| Conservazione (giorni) | `retention_days` | `router_logs_retention_days` | 7–90 | `30` |
| File ruotati massimi | `max_files` | `router_logs_max_files` | 7–60 (per ogni log) | `30` |

Nella pagina la frequenza compare tradotta («Ogni giorno»…), ma il valore
salvato e quello da mettere nel playbook sono sempre le parole chiave inglesi.

La rotazione la fa logrotate, come root. OpenWISP non scrive configurazioni di
sistema: salva i valori in `OPENWISP_NETCONSOLE_ROTATION_FILE`, un JSON in una
sua directory. Ogni ora lo script di root (`router-logs-rotation` nel repo
[openwisp2](https://github.com/mikysal78/openwisp2)):

- lo rilegge come input non fidato e ricontrolla gli stessi limiti;
- genera la configurazione di logrotate da un modello fisso;
- scrive l'esito in `OPENWISP_NETCONSOLE_ROTATION_STATUS_FILE`, in una
  directory di root. La pagina mostra quell'esito.

### Template per i device (lato router)

[`examples/openwisp-template/netconsole.json`](examples/openwisp-template/netconsole.json)
è un template OpenWISP che installa sui router uno script di hotplug
([`30-netconsole.sh`](examples/openwisp-template/30-netconsole.sh)). A ogni
`ifup`:

- trova la strada verso il server e il MAC del prossimo hop;
- carica netconsole in formato esteso (`+`), ricaricandolo solo se cambiano i
  parametri o l'interfaccia;
- aggiunge l'userdata `ninux_node` con il nome del device (`{{ name }}`,
  ricontrollato dallo script), che rsyslog usa per la cartella.

Per importarlo in OpenWISP: **Templates → Add**, backend OpenWRT, type
Generic, il contenuto di `config` nell'editor avanzato e `default_values` in
**Configuration variables**. Poi assegnatelo ai device.

| Variabile | Predefinito | Significato |
|---|---|---|
| `netconsole_server` | `192.0.2.10` (esempio) | IPv4 del server con rsyslog |
| `netconsole_port` | `6666` | porta UDP dell'ingresso netconsole |

Requisiti del firmware:

- `kmod-netconsole` (e il supporto netpoll nel kernel);
- per il nome del device, un kernel con `CONFIG_NETCONSOLE_DYNAMIC=y` e
  `kmod-fs-configfs`. OpenWrt compila kmod-netconsole con `=n`
  (`package/kernel/linux/modules/netsupport.mk`), quindi va cambiato nella
  vostra build. Senza, i messaggi arrivano lo stesso, nella cartella con l'IP
  sorgente.

La CI controlla lo script con `shellcheck` e genera il template con
netjsonconfig.

## Sicurezza

- **Accesso:** le viste sono dentro l'admin. Servono un utente staff
  autenticato, un device del queryset dell'utente (filtrato per
  organizzazione) e il permesso di vederlo. Altrimenti la risposta è 404.
- **Percorsi:**
  - il client non passa mai un percorso: sceglie una delle chiavi calcolate
    dal server (nome e IP del device) e uno dei file elencati;
  - chiavi e nomi dei file sono ricontrollati con espressioni regolari;
  - la cartella deve essere una directory reale dentro la radice, quindi i
    symlink sono scartati, e i file si aprono con `O_NOFOLLOW`.
- **Log di altri device:** il nome di un device in OpenWISP non è univoco, e
  un IP può passare da un router a un altro. Una chiave condivisa con un altro
  device, anche di un'altra organizzazione, non viene mostrata. Un nome che è
  esso stesso un IP viene ignorato.
- **XSS:** il testo dei log arriva come JSON e la pagina lo inserisce con
  `textContent`, mai come HTML.
- **Carico:** ogni richiesta legge al massimo `MAX_BYTES` byte e la pagina
  tiene al massimo 5000 righe. Le viste sono solo GET e non modificano nulla.
- **Rotazione:**
  - chi prendesse il controllo di OpenWISP potrebbe solo scegliere valori
    negli intervalli della tabella: non può riempire il disco né far sparire i
    log in poche ore;
  - lo script di root legge il JSON senza seguire symlink, solo se è un file
    regolare di al massimo 4 KB;
  - nella configurazione di logrotate entrano solo numeri interi e una delle
    tre frequenze ammesse. Con un valore non valido usa quelli del playbook e
    lo segnala nell'esito.
- **Limite noto:** il nome nell'userdata lo dichiara il router. Chi può
  mandare UDP alla porta di netconsole può scrivere righe nella cartella di un
  altro nodo. Limitate le sorgenti con il firewall e considerate questi log
  come diagnostica, non come prova.

## Sviluppo

```bash
pip install pytest
pytest
```

I test coprono la lettura dei file (`logfiles.py`), compresi i tentativi di
uscire dalla directory dei log, e le impostazioni di rotazione (`rotation.py`).

GitHub Actions: **CI** (a ogni push e pull request) esegue ruff, i test con
Python 3.10–3.13, il controllo che le migrazioni corrispondano ai modelli, i
controlli su JavaScript e traduzione, e compila il pacchetto verificandone il
contenuto. **Release** (a ogni tag `v*`) controlla che il tag corrisponda alla
versione, compila wheel e sdist e li allega alla release di GitHub con
`SHA256SUMS`.

## Segnalare vulnerabilità

Vedi [SECURITY.md](SECURITY.md): segnalazione privata tramite GitHub, advisory
di sicurezza e CVE per i problemi confermati. Sul repository sono attivi gli
avvisi Dependabot, la scansione dei segreti, CodeQL e `pip-audit` (nella CI).

## Licenza

GPL-3.0-or-later, come openwisp-controller.
