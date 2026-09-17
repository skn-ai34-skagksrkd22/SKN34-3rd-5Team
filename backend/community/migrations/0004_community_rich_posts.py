from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("community", "0003_community_post_api"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="communitypost",
            name="content_doc",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
