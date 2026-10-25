"""Controlla che il wheel contenga tutti i file necessari a runtime."""

import sys
import zipfile

REQUIRED = [
    "openwisp_netconsole/admin.py",
    "openwisp_netconsole/api.py",
    "openwisp_netconsole/api_urls.py",
    "openwisp_netconsole/sources.py",
    "openwisp_netconsole/models.py",
    "openwisp_netconsole/migrations/__init__.py",
    "openwisp_netconsole/migrations/0001_initial.py",
    "openwisp_netconsole/locale/it/LC_MESSAGES/django.mo",
    "openwisp_netconsole/static/openwisp_netconsole/netconsole.js",
    "openwisp_netconsole/static/openwisp_netconsole/netconsole.css",
    "openwisp_netconsole/templates/admin/openwisp_netconsole/device/change_form.html",
]

names = set(zipfile.ZipFile(sys.argv[1]).namelist())
missing = [name for name in REQUIRED if name not in names]
if missing:
    sys.exit("missing from the wheel: " + ", ".join(missing))
print("wheel ok: %d files" % len(names))
