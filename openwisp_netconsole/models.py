from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from . import rotation


def _limits(name):
    low, high = rotation.LIMITS[name]
    return [MinValueValidator(low), MaxValueValidator(high)]


class RotationSettings(models.Model):
    """Rotazione dei log dei router (riga unica, pk=1).

    I valori di partenza li scrive il playbook nel JSON (vedi rotation.py):
    la riga nasce dal JSON alla prima apertura della pagina.
    """

    FREQUENCY_CHOICES = (
        ("daily", _("Every day")),
        ("weekly", _("Every week")),
        ("monthly", _("Every month")),
    )
    frequency = models.CharField(
        _("rotation frequency"),
        max_length=8,
        choices=FREQUENCY_CHOICES,
        default="daily",
        help_text=_("A new file is started at this interval."),
    )
    max_size_mb = models.PositiveIntegerField(
        _("maximum size (MB)"),
        default=50,
        validators=_limits("max_size_mb"),
        help_text=_("A file larger than this is rotated earlier (checked every hour)."),
    )
    retention_days = models.PositiveIntegerField(
        _("retention (days)"),
        default=30,
        validators=_limits("retention_days"),
        help_text=_("Rotated files older than this are deleted."),
    )
    max_files = models.PositiveIntegerField(
        _("maximum rotated files"),
        default=30,
        validators=_limits("max_files"),
        help_text=_(
            "Per log, at most this many rotated files are kept, even if younger "
            "than the retention: it protects the disk when a router writes a lot."
        ),
    )
    modified = models.DateTimeField(_("modified"), auto_now=True)

    class Meta:
        verbose_name = _("router log rotation")
        verbose_name_plural = _("router log rotation")

    def __str__(self):
        return str(self._meta.verbose_name)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def as_dict(self):
        return {name: getattr(self, name) for name in ("frequency", *rotation.LIMITS)}
