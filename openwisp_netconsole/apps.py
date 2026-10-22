from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NetconsoleConfig(AppConfig):
    name = "openwisp_netconsole"
    label = "openwisp_netconsole"
    verbose_name = _("Netconsole")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        self.register_menu()

    def register_menu(self):
        from openwisp_utils.admin_theme.menu import (
            MENU,
            MenuGroup,
            register_menu_group,
            register_menu_subitem,
        )

        config = {
            "label": _("Router log rotation"),
            "model": "openwisp_netconsole.RotationSettings",
            "name": "changelist",
            "icon": "ow-monitoring",
        }
        # nel gruppo «Monitoring» se c'e' (openwisp-monitoring), altrimenti da sola
        if isinstance(MENU.get(80), MenuGroup):
            register_menu_subitem(80, 20, config)
        else:
            register_menu_group(85, config)
