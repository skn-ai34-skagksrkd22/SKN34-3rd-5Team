import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("community", "0008_unify_community_images"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="communitypost",
            name="is_hidden",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="communityreport",
            name="status",
            field=models.CharField(
                choices=[("pending", "pending"), ("held", "held"), ("hidden", "hidden")],
                default="pending",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="communityreport",
            name="handled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="communityreport",
            name="handled_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="handled_community_reports",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
