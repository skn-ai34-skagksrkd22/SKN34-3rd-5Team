from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="TvingSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("resource_kind", models.CharField(choices=[("daily", "Daily"), ("month", "Month"), ("team", "Team"), ("athlete", "Athlete")], max_length=16)),
                ("resource_key", models.CharField(max_length=16)),
                ("payload", models.JSONField()),
                ("source_fetched_at", models.DateTimeField()),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [models.Index(fields=["resource_kind", "resource_key"], name="tving_resource_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("resource_kind", "resource_key"), name="uq_tving_snapshot_resource"),
                    models.CheckConstraint(condition=models.Q(models.Q(("resource_key__regex", r"^\d{4}-\d{2}-\d{2}$"), ("resource_kind", "daily")), models.Q(("resource_key__regex", r"^\d{4}-\d{2}$"), ("resource_kind", "month")), models.Q(("resource_key__regex", r"^(SS|KT|LG|HT|OB|NC|HH|LT|SK|WO)$"), ("resource_kind", "team")), models.Q(("resource_key__regex", r"^\d{4,12}$"), ("resource_kind", "athlete")), _connector="OR"), name="ck_tving_snapshot_identity"),
                ],
            },
        )
    ]
