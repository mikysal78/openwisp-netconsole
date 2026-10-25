from django.urls import path

from . import api

app_name = "openwisp_netconsole_api"

# Da includere nelle URL del progetto accanto alle altre API di OpenWISP:
#   path("api/v1/", include("openwisp_netconsole.api_urls")),
urlpatterns = [
    path("netconsole/device/<uuid:pk>/logs/", api.logs, name="logs"),
]
