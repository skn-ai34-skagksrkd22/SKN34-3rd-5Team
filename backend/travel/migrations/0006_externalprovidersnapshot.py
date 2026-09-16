from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("travel", "0005_course_engagement")]

    operations = [
        migrations.CreateModel(
            name="ExternalProviderSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("directions", "Directions"), ("tourism", "Tourism")], max_length=16)),
                ("key", models.CharField(max_length=255)),
                ("request", models.JSONField(default=dict)),
                ("payload", models.JSONField(default=dict)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("fetched_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ("kind", "key"),
                "constraints": [models.UniqueConstraint(fields=("kind", "key"), name="travel_external_snapshot_unique")],
            },
        ),
    ]
