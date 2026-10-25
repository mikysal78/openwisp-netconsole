# openwisp-netconsole

🇬🇧 English | [🇮🇹 Italiano](README.it.md)

> 📖 This repository is part of the **NINUX Basilicata** infrastructure: the step-by-step guide to rebuild all of it (Proxmox, DNS, OpenWISP, modules, firmware, app) is at **[the guide on GitHub Pages](https://mikysal78.github.io/ninux-basilicata-infra/en/)**.

[![CI](https://github.com/mikysal78/openwisp-netconsole/actions/workflows/ci.yml/badge.svg)](https://github.com/mikysal78/openwisp-netconsole/actions/workflows/ci.yml)

**Netconsole** tab on the [OpenWISP](https://openwisp.org/) device page: it shows
in real time the kernel messages that the router sends with
[netconsole](https://docs.kernel.org/networking/netconsole.html) and that rsyslog
stores on the server. It is mostly useful for hangs and kernel panics, when
syslog has no time to send anything.

Born for the [NINUX Basilicata](https://github.com/mikysal78/openwisp2) network,
where routers send netconsole to the OpenWISP server.

## Screenshots

The Netconsole tab of a Linksys WRT3200ACM whose Wi-Fi driver (mwlwifi) is
logging an error ten times a second; the rotated files are listed for
download (`netconsole.log.1` was rotated at 50 MB):

![Netconsole tab on the device page](docs/netconsole-tab-v2.png)

The router log rotation page (superusers only), with the status of the last
run on the server:

![Router log rotation page](docs/rotation-page-v2.png)

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
pip install https://github.com/mikysal78/openwisp-netconsole/releases/download/v0.2.1/openwisp_netconsole-0.2.1-py3-none-any.whl
```

or from the git tag:

```bash
pip install "openwisp-netconsole @ git+https://github.com/mikysal78/openwisp-netconsole@v0.2.1"
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
[ansible-openwisp2](https://github.com/openwisp/ansible-openwisp2) role and the
example role [`router_logs`](examples/ansible/roles/router_logs/), which sets
up the server side: rsyslog, the read-only `router-logs` group, the root
rotation script and its cron.

```bash
ansible-galaxy role install openwisp.openwisp2
cd examples/ansible
ansible-playbook -i hosts playbook.yml
```

```yaml
---
# Basic example: OpenWISP with openwisp-netconsole.
#
#   ansible-galaxy role install openwisp.openwisp2
#   ansible-playbook -i hosts playbook.yml
#
# router_logs (roles/ next to this file) sets up the server side:
# rsyslog, read-only access for OpenWISP, rotation managed from the admin
# page. All its variables are in roles/router_logs/defaults/main.yml.

- name: OpenWISP with openwisp-netconsole
  hosts: openwisp2
  become: true
  roles:
    - openwisp.openwisp2
    - router_logs
  vars:
    openwisp2_extra_python_packages:
      - "openwisp-netconsole @ https://github.com/mikysal78/openwisp-netconsole/releases/download/v0.2.1/openwisp_netconsole-0.2.1-py3-none-any.whl"
    openwisp2_extra_django_apps:
      - openwisp_netconsole
    # optional: API for apps such as openwisp-android
    openwisp2_extra_urls:
      - 'path("api/v1/", include("openwisp_netconsole.api_urls"))'
    # Optional, see the role defaults:
    # router_logs_retention_days: 15
```

The variables of `router_logs` and their defaults are in
[`defaults/main.yml`](examples/ansible/roles/router_logs/defaults/main.yml);
usually none of them needs to be changed:

| Variable | Default | Meaning |
|---|---|---|
| `router_logs_dir` | `/opt/router-logs` | where rsyslog stores the logs |
| `router_logs_group` | `router-logs` | read-only group for OpenWISP |
| `router_logs_openwisp_user` | `www-data` | user OpenWISP runs as |
| `router_logs_syslog_port` / `router_logs_netconsole_port` | `514` / `6666` | UDP inputs |
| `router_logs_frequency`, `_max_size_mb`, `_retention_days`, `_max_files` | `daily`, `50`, `30`, `30` | rotation starting values |

CI checks it with `--syntax-check`, `ansible-lint` (production profile) and
`rsyslogd -N1`, and tests the rotation script against injections, symlinks and
FIFOs. Then restrict the senders of UDP 514/6666 with the firewall.

### Template for the devices (router side)

[`examples/openwisp-template/netconsole.json`](examples/openwisp-template/netconsole.json)
is an OpenWISP template that installs a hotplug script
([`30-netconsole.sh`](examples/openwisp-template/30-netconsole.sh)) on the
routers. On every `ifup` it:

- finds the route to the server and the MAC of the next hop;
- loads netconsole in extended format (`+`), reloading it only when the
  parameters or the interface change;
- adds the `ninux_node` userdata with the device name (`{{ name }}`, checked
  again by the script), which rsyslog uses for the folder.

Import it in OpenWISP: **Templates → Add**, backend OpenWRT, type Generic, the
content of `config` in the advanced editor and `default_values` in
**Configuration variables**. Then assign it to the devices.

| Variable | Default | Meaning |
|---|---|---|
| `netconsole_server` | `192.0.2.10` (example) | IPv4 of the server running rsyslog |
| `netconsole_port` | `6666` | UDP port of the netconsole input |

Firmware requirements:

- `kmod-netconsole` (and netpoll support in the kernel);
- for the device name, a kernel with `CONFIG_NETCONSOLE_DYNAMIC=y` and
  `kmod-fs-configfs`. OpenWrt builds kmod-netconsole with `=n`
  (`package/kernel/linux/modules/netsupport.mk`), so it must be changed in
  your build. Without it the messages still arrive, in the folder named after
  the source IP.

CI checks the script with `shellcheck` and renders the template with
netjsonconfig.

## API for apps

Apps such as [openwisp-android](https://github.com/mikysal78/openwisp-android)
read the last lines of the logs with the OpenWISP API token of the user,
after `path("api/v1/", include("openwisp_netconsole.api_urls"))` is added to
the URLs of the project:

```
GET /api/v1/netconsole/device/<device uuid>/logs/?lines=200
Authorization: Bearer <token from /api/v1/users/token/>

200 [{"kind": "name", "key": "C2600", "lines": ["...", "..."]}]
```

The checks are the same as for the tab, and the logs are the same (never a
path from the client). `lines` goes from 1 to `OPENWISP_NETCONSOLE_MAX_LINES`
(default 1000; 200 if omitted). Only the Bearer token is accepted, never the browser session.
Answers: `401` missing or invalid token, `404` device missing or not allowed
(the two are not distinguished).

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
