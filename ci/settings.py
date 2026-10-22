# Impostazioni minime per i controlli della CI (makemigrations --check):
# niente admin, che richiederebbe openwisp-controller e GDAL.
SECRET_KEY = "ci-only"
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "openwisp_netconsole",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
USE_TZ = True
