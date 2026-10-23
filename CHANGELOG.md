# Changelog

## Unreleased

- Example playbook split into the `router_logs` role (defaults, tasks,
  handlers, templates): the playbook in the README is now a few lines.
- Example template: the device name was never set on kernels 6.x, where the
  target given to `insmod` shows up in configfs only after `mkdir cmdline0`;
  the hook now creates it, and removes it before `rmmod`, which otherwise
  fails because the configfs folder keeps the module busy.

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
