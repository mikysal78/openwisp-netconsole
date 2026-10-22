"""Scheda «Netconsole» nella pagina del device.

Estende l'admin del device gia' registrato (quello di openwisp-monitoring, se
c'e') invece di sostituirlo: per questo l'app va messa in INSTALLED_APPS dopo
openwisp_controller e openwisp_monitoring.

Sicurezza:
- le due viste passano da admin_site.admin_view (utente staff autenticato) e
  prendono il device con get_object, cioe' dal queryset filtrato per
  organizzazione; poi serve il permesso di vedere quel device;
- le directory si ricavano dal device nel database, mai da un percorso del
  client: il client sceglie solo tra le chiavi restituite qui;
- una chiave (nome o IP) condivisa con un altro device non viene mostrata:
  netconsole-<chiave> potrebbe contenere i log dell'altro, anche di un'altra
  organizzazione (il nome di un device non e' univoco);
- il testo dei log arriva come JSON e la pagina lo inserisce con textContent.
"""

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.dateparse import parse_datetime
from django.utils.formats import localize
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from swapper import load_model

from . import logfiles, rotation
from . import settings as app_settings
from .models import RotationSettings

Device = load_model("config", "Device")

try:
    BaseDeviceAdmin = type(admin.site._registry[Device])
except KeyError as e:
    raise ImproperlyConfigured(
        "openwisp_netconsole va messo in INSTALLED_APPS dopo openwisp_controller.config "
        "(e dopo openwisp_monitoring.device, se presente)"
    ) from e

MAX_POS_LENGTH = 64


class NetconsoleDeviceAdmin(BaseDeviceAdmin):
    change_form_template = "admin/openwisp_netconsole/device/change_form.html"

    @property
    def media(self):
        return super().media + forms.Media(
            js=["openwisp_netconsole/netconsole.js"],
            css={"all": ["openwisp_netconsole/netconsole.css"]},
        )

    def get_urls(self):
        info = self.opts.app_label, self.opts.model_name
        return [
            path(
                "<uuid:pk>/netconsole/",
                self.admin_site.admin_view(self.netconsole_view),
                name="%s_%s_netconsole" % info,
            ),
            path(
                "<uuid:pk>/netconsole/download/",
                self.admin_site.admin_view(self.netconsole_download_view),
                name="%s_%s_netconsole_download" % info,
            ),
        ] + super().get_urls()

    def get_extra_context(self, pk=None):
        ctx = super().get_extra_context(pk)
        ctx["netconsole_parent_template"] = BaseDeviceAdmin.change_form_template
        if pk:
            info = self.opts.app_label, self.opts.model_name
            ctx["netconsole_url"] = reverse("admin:%s_%s_netconsole" % info, args=[pk])
            ctx["netconsole_refresh"] = int(app_settings.REFRESH)
        return ctx

    def _netconsole_device(self, request, pk):
        device = self.get_object(request, str(pk))
        if device is None or not self.has_view_permission(request, device):
            raise Http404
        return device

    def _netconsole_sources(self, device):
        """Chiavi (nome, IP) del device che non appartengono anche ad altri."""
        others = Device.objects.exclude(pk=device.pk)
        ips = []
        if app_settings.IP_FALLBACK:
            ips = [device.management_ip, device.last_ip]
        keys = []
        for kind, key in logfiles.source_keys(device.name, ips):
            if kind == "name":
                shared = others.filter(name=key).exists()
            else:
                shared = others.filter(Q(management_ip=key) | Q(last_ip=key)).exists()
            if not shared:
                keys.append((kind, key))
        return logfiles.device_sources(app_settings.LOG_DIR, keys)

    def _netconsole_source(self, request, device):
        sources = self._netconsole_sources(device)
        keys = [key for _, key in sources]
        key = request.GET.get("source", "")
        if key not in keys:
            key = keys[0] if keys else ""
        return sources, key

    def netconsole_view(self, request, pk):
        device = self._netconsole_device(request, pk)
        sources, key = self._netconsole_source(request, device)
        lines, pos, reset = [], "", True
        files = []
        if key:
            pos = request.GET.get("pos", "")[:MAX_POS_LENGTH]
            if request.GET.get("source") != key:
                pos = ""
            lines, pos, reset = logfiles.read_log(
                app_settings.LOG_DIR,
                key,
                pos,
                max_lines=app_settings.MAX_LINES,
                max_bytes=app_settings.MAX_BYTES,
            )
            info = self.opts.app_label, self.opts.model_name
            download = reverse("admin:%s_%s_netconsole_download" % info, args=[pk])
            files = [
                {
                    "name": name,
                    "size": size,
                    "url": "%s?%s" % (download, urlencode({"source": key, "file": name})),
                }
                for name, size in logfiles.list_files(app_settings.LOG_DIR, key)
            ]
        response = JsonResponse(
            {
                "sources": [{"kind": kind, "key": k} for kind, k in sources],
                "source": key,
                "pos": pos,
                "reset": reset,
                "lines": lines,
                "files": files,
            }
        )
        response["Cache-Control"] = "no-store"
        return response

    def netconsole_download_view(self, request, pk):
        device = self._netconsole_device(request, pk)
        sources, key = self._netconsole_source(request, device)
        name = request.GET.get("file", "")
        if not key or request.GET.get("source") != key:
            raise Http404
        if name not in dict(logfiles.list_files(app_settings.LOG_DIR, key)):
            raise Http404
        f = logfiles.open_file(app_settings.LOG_DIR, key, name)
        if f is None:
            raise Http404
        content_type = "application/gzip" if name.endswith(".gz") else "text/plain; charset=utf-8"
        response = FileResponse(
            f, as_attachment=True, filename="netconsole-%s-%s" % (key, name), content_type=content_type
        )
        response["Cache-Control"] = "no-store"
        return response


admin.site.unregister(Device)
admin.site.register(Device, NetconsoleDeviceAdmin)


@admin.register(RotationSettings)
class RotationSettingsAdmin(admin.ModelAdmin):
    """Una sola riga, solo per i superuser: vale per i log di tutti i router."""

    fields = ("frequency", "max_size_mb", "retention_days", "max_files", "status")
    readonly_fields = ("status",)

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def _load(self):
        """La riga unica; la prima volta nasce dai valori scritti dal playbook."""
        obj = RotationSettings.objects.filter(pk=1).first()
        if obj is None:
            obj = RotationSettings()
            try:
                values = rotation.validate(rotation.read_json(app_settings.ROTATION_FILE))
            except ValueError:
                values = {}
            for name, value in values.items():
                setattr(obj, name, value)
            obj.save()
        return obj

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_permission(request):
            raise Http404
        obj = self._load()
        info = self.opts.app_label, self.opts.model_name
        return redirect(reverse("admin:%s_%s_change" % info, args=[obj.pk]))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            rotation.write_settings(app_settings.ROTATION_FILE, obj.as_dict())
        except (OSError, ValueError) as e:
            messages.error(
                request,
                _("Settings saved in OpenWISP but not passed to the server: %(error)s") % {"error": e},
            )
        else:
            messages.info(request, _("The new settings are applied within an hour."))

    @admin.display(description=_("status on the server"))
    def status(self, obj):
        status = rotation.read_status(app_settings.ROTATION_STATUS_FILE)
        if not status:
            return _("Not applied yet: the server applies the settings every hour.")
        applied = parse_datetime(str(status.get("applied", "")))
        when = localize(localtime(applied)) if applied else "?"
        values = status.get("settings") if isinstance(status.get("settings"), dict) else {}
        frequency = dict(RotationSettings.FREQUENCY_CHOICES).get(values.get("frequency"), "?")
        text = format_html(
            "{}: {} — {} {} MB, {} {}, {} {}",
            _("Last applied"),
            when,
            frequency,
            values.get("max_size_mb", "?"),
            values.get("retention_days", "?"),
            _("days"),
            values.get("max_files", "?"),
            _("files"),
        )
        if status.get("error"):
            text = format_html(
                '{}<br><strong style="color:#c00">{}: {}</strong>', text, _("Error"), status["error"]
            )
        return text
