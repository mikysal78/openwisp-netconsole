# Security policy

## Supported versions

Only the latest release receives security fixes.

| Version | Supported |
|---|---|
| latest 0.x | ✅ |
| older | ❌ |

## Reporting a vulnerability

**Please do not open a public issue.** Report it privately through
[GitHub private vulnerability reporting](https://github.com/mikysal78/openwisp-netconsole/security/advisories/new)
(Security → Report a vulnerability).

Include, if possible: affected version, a description of the issue and its
impact, steps to reproduce or a proof of concept, and a suggested fix.

What to expect:

- acknowledgement within **7 days**;
- an assessment and, if confirmed, a fix and a new release as soon as
  possible (target: 30 days for high/critical issues);
- a [GitHub Security Advisory](https://github.com/mikysal78/openwisp-netconsole/security/advisories)
  published with the release; a **CVE** is requested through GitHub, which is a
  CVE Numbering Authority, when the issue warrants one;
- credit in the advisory, unless you prefer to stay anonymous.

## Scope

In scope: this package (the Netconsole tab, its views and the router log
rotation page) and the way it reads files under `OPENWISP_NETCONSOLE_LOG_DIR`.

Out of scope: OpenWISP itself, rsyslog, logrotate and the router firmware
(report those to their projects), and the documented known limit that the
`ninux_node` userdata is declared by the router (see the README, "Security").

## Hardening already in place

See the "Security" section of the [README](README.md#security): access through
the admin with per-device permissions, no client-supplied paths, symlinks
rejected, keys shared with other devices hidden, log text rendered as text
only, strict limits on the rotation settings, which a root script re-validates.
