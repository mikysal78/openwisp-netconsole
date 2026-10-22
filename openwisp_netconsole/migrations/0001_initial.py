import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RotationSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "frequency",
                    models.CharField(
                        choices=[
                            ("daily", "Every day"),
                            ("weekly", "Every week"),
                            ("monthly", "Every month"),
                        ],
                        default="daily",
                        help_text="A new file is started at this interval.",
                        max_length=8,
                        verbose_name="rotation frequency",
                    ),
                ),
                (
                    "max_size_mb",
                    models.PositiveIntegerField(
                        default=50,
                        help_text="A file larger than this is rotated earlier (checked every hour).",
                        validators=[
                            django.core.validators.MinValueValidator(5),
                            django.core.validators.MaxValueValidator(100),
                        ],
                        verbose_name="maximum size (MB)",
                    ),
                ),
                (
                    "retention_days",
                    models.PositiveIntegerField(
                        default=30,
                        help_text="Rotated files older than this are deleted.",
                        validators=[
                            django.core.validators.MinValueValidator(7),
                            django.core.validators.MaxValueValidator(90),
                        ],
                        verbose_name="retention (days)",
                    ),
                ),
                (
                    "max_files",
                    models.PositiveIntegerField(
                        default=30,
                        help_text=(
                            "Per log, at most this many rotated files are kept, even if younger than the "
                            "retention: it protects the disk when a router writes a lot."
                        ),
                        validators=[
                            django.core.validators.MinValueValidator(7),
                            django.core.validators.MaxValueValidator(60),
                        ],
                        verbose_name="maximum rotated files",
                    ),
                ),
                ("modified", models.DateTimeField(auto_now=True, verbose_name="modified")),
            ],
            options={
                "verbose_name": "router log rotation",
                "verbose_name_plural": "router log rotation",
            },
        ),
    ]
