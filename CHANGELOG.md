# Changelog

## 0.2.0

- API for apps: `GET /api/v1/netconsole/device/<uuid>/logs/?lines=200` with
  the OpenWISP token (`Authorization: Bearer <token>`) returns the last lines
  of the netconsole logs of the device, after the same checks as the tab. Used
  by [openwisp-android](https://github.com/mikysal78/openwisp-android).
  Include `openwisp_netconsole.api_urls` under `api/v1/` to enable it. Only
  the Bearer token is accepted (never the browser session), and a device the
  user cannot see answers 404 like a missing one.
- Example playbook split into the `router_logs` role (defaults, tasks,
  handlers, templates): the playbook in the README is now a few lines.
- Example template: the device name was never set on kernels 6.x, where the
  target given to `insmod` shows up in configfs only after a `mkdir`. With
  `CONFIG_NETCONSOLE_DYNAMIC=y` the hook now creates its own `ninux` target in
  configfs and reconfigures it on every route change, without reloading the
  module; without it, parameters are still given to `insmod`.
- Example template: the hook checks netconsole again by itself every 5 minutes
  (every minute while it fails): at boot the server may be unreachable, and
  VPN interfaces recreated after boot disable the target without a new ifup.
- Example template: raise the console log level to the OpenWrt default when a
  bootloader passes `loglevel=1` (e.g. Zyxel), otherwise netconsole only
  gets emergency messages.

## 0.1.2

- Screenshots in the README (`docs/`).
- Netconsole tab: space between "Download:" and the file list.
- Example OpenWISP template for the devices (`examples/openwisp-template/`):
  hotplug script with the `ninux_node` userdata, server and port as template
  variables; CI runs shellcheck and renders it with netjsonconfig.
- Example playbook (README and `examples/ansible/`) with generic rsyslog and
  rotation script templates; CI checks it (syntax, ansible-lint, rsyslogd -N1)
  and tests the rotation script against injections, symlinks and FIFOs.
- CI: vulnerabilities of the OpenWISP stack reported by pip-audit as a
  warning in the job summary instead of failing the build.

## 0.1.1

- Rotation page: the frequency in the server status is shown with its label
  ("Every day") instead of the raw value.
- Security: `SECURITY.md` (private reporting, advisories, CVE), Dependabot,
  CodeQL and `pip-audit` in CI.

## 0.1.0

- Netconsole tab on the device page and router log rotation page.
