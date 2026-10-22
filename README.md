# openwisp-netconsole

🇬🇧 English | [🇮🇹 Italiano](README.it.md)

[![CI](https://github.com/mikysal78/openwisp-netconsole/actions/workflows/ci.yml/badge.svg)](https://github.com/mikysal78/openwisp-netconsole/actions/workflows/ci.yml)

**Netconsole** tab on the [OpenWISP](https://openwisp.org/) device page: it shows
in real time the kernel messages that the router sends with
[netconsole](https://docs.kernel.org/networking/netconsole.html) and that rsyslog
stores on the server. It is mostly useful for hangs and kernel panics, when
syslog has no time to send anything.

Born for the [NINUX Basilicata](https://github.com/mikysal78/openwisp2) network,
where routers send netconsole to the OpenWISP server.

## How it works

```
router (netconsole, extended format + userdata ninux_node=<name>)
   │ UDP 6666
   ▼
rsyslog  ──►  <LOG_DIR>/netconsole-<device name>/netconsole.log
              <LOG_DIR>/netconsole-<source ip>/netconsole.log   (messages without a name)
   ▲
   │ read-only
OpenWISP: device "Netconsole" tab
```

- The tab shows the folder named after the device and the ones named after its
  management IP and last IP.
- It asks the server only for the new lines every few seconds, while the tab is
  open and the page is visible.
- It lists the rotated files (`netconsole.log.1`, `.gz`…) for download.
- It extends the device admin already registered (including the
  openwisp-monitoring one) without replacing it.

## Installation

From the [release](https://github.com/mikysal78/openwisp-netconsole/releases)
(built wheel, with `SHA256SUMS`):

```bash
pip install https://github.com/mikysal78/openwisp-netconsole/releases/download/v0.1.1/openwisp_netconsole-0.1.1-py3-none-any.whl
```

or from the git tag:

```bash
pip install "openwisp-netconsole @ git+https://github.com/mikysal78/openwisp-netconsole@v0.1.1"
```

In `settings.py`, **after** `openwisp_controller.config` and
`openwisp_monitoring.device`:

```python
INSTALLED_APPS += ["openwisp_netconsole"]
```

Then run `collectstatic` and restart OpenWISP. With the
[ansible-openwisp2](https://github.com/openwisp/ansible-openwisp2) role:
`openwisp2_extra_python_packages` and `openwisp2_extra_django_apps`.

The user OpenWISP runs as (e.g. `www-data`) must be able to **read** the log
directory: a dedicated group is better than `adm`.

### Example playbook

A basic playbook with the official
[ansible-openwisp2](https://github.com/openwisp/ansible-openwisp2) role: it
installs the module and sets up the server side for the router logs (rsyslog,
the read-only `router-logs` group, the root rotation script and its cron). It
is [`examples/ansible/playbook.yml`](examples/ansible/playbook.yml); the two
templates it uses are in [`examples/ansible/templates/`](examples/ansible/templates/).
CI checks it with `--syntax-check`, `ansible-lint` and `rsyslogd -N1`, and
tests the rotation script against injections, symlinks and FIFOs.

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

Then restrict the senders of UDP 514/6666 with the firewall.

### Settings

| Setting | Default | Meaning |
|---|---|---|
| `OPENWISP_NETCONSOLE_LOG_DIR` | `/opt/router-logs` | root of the `netconsole-*` folders |
| `OPENWISP_NETCONSOLE_MAX_LINES` | `1000` | maximum lines per request |
| `OPENWISP_NETCONSOLE_MAX_BYTES` | `524288` | maximum bytes read per request |
| `OPENWISP_NETCONSOLE_REFRESH` | `5` | seconds between refreshes (minimum 2) |
| `OPENWISP_NETCONSOLE_IP_FALLBACK` | `True` | also show the folders named after IPs |

### Log rotation

The **Monitoring → Router log rotation** page, visible to superusers only, sets
the rotation of the router logs: syslog and netconsole.

| Value | Range | Default |
|---|---|---|
| frequency | every day, week or month | every day |
| maximum size | 5–100 MB (checked every hour) | 50 MB |
| retention | 7–90 days | 30 days |
| maximum rotated files per log | 7–60 | 30 |

Rotation is done by logrotate, as root. OpenWISP never writes system
configuration: it saves the values in `OPENWISP_NETCONSOLE_ROTATION_FILE`, a
JSON file in its own directory. Every hour the root script
(`router-logs-rotation` in the [openwisp2](https://github.com/mikysal78/openwisp2)
repo):

- reads it again as untrusted input and checks the same limits;
- generates the logrotate configuration from a fixed template;
- writes the outcome to `OPENWISP_NETCONSOLE_ROTATION_STATUS_FILE`, in a root
  directory. The page shows that outcome.

### Router and rsyslog

On the router netconsole must be loaded in extended format (`+` in the
parameters) and the target needs the `ninux_node` userdata with the device
name. Userdata requires a kernel with `CONFIG_NETCONSOLE_DYNAMIC=y` (OpenWrt
builds it with `=n`). Example script and rsyslog configuration:
[openwisp2](https://github.com/mikysal78/openwisp2) (template
`openwisp-templates/netconsole.json`, `templates/rsyslog-router-logs.conf.j2`).

## Security

- **Access:** the views live inside the admin. They require an authenticated
  staff user, a device in the user's queryset (filtered by organization) and
  the permission to view it. Otherwise the response is 404.
- **Paths:**
  - the client never sends a path: it picks one of the keys computed by the
    server (device name and IPs) and one of the listed files;
  - keys and file names are checked again with regular expressions;
  - the folder must be a real directory inside the root, so symlinks are
    rejected, and files are opened with `O_NOFOLLOW`.
- **Logs of other devices:** device names in OpenWISP are not unique, and an
  IP can move from one router to another. A key shared with another device,
  even from another organization, is not shown. A name that is itself an IP is
  ignored.
- **XSS:** the log text arrives as JSON and the page inserts it with
  `textContent`, never as HTML.
- **Load:** each request reads at most `MAX_BYTES` bytes and the page keeps at
  most 5000 lines. The views are GET only and change nothing.
- **Rotation:**
  - whoever took control of OpenWISP could only pick values within the
    ranges in the table: they can neither fill the disk nor make the logs
    disappear within hours;
  - the root script reads the JSON without following symlinks, only if it is
    a regular file of at most 4 KB;
  - only integers and one of the three allowed frequencies end up in the
    logrotate configuration. With an invalid value it uses the playbook ones
    and reports it in the outcome.
- **Known limit:** the name in the userdata is declared by the router. Anyone
  who can send UDP to the netconsole port can write lines into another node's
  folder. Restrict the sources with the firewall and treat these logs as
  diagnostics, not as evidence.

## Development

```bash
pip install pytest
pytest
```

The tests cover file reading (`logfiles.py`), including attempts to escape the
log directory, and the rotation settings (`rotation.py`).

GitHub Actions: **CI** (every push and pull request) runs ruff, the tests on
Python 3.10–3.13, the check that migrations match the models, the JavaScript
syntax and translation checks, and builds the package verifying its contents.
**Release** (on every `v*` tag) checks that the tag matches the version, builds
wheel and sdist and attaches them to the GitHub release with `SHA256SUMS`.

## Reporting vulnerabilities

See [SECURITY.md](SECURITY.md): private reporting through GitHub, security
advisories and CVE for confirmed issues. Dependabot alerts, secret scanning,
CodeQL and `pip-audit` (in CI) are enabled on the repository.

## License

GPL-3.0-or-later, like openwisp-controller.
