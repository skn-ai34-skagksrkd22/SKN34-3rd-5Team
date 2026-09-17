from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("travel", "0004_seed_course_samples")]

    operations = [migrations.AddField(
        model_name="course", name="content_doc", field=models.JSONField(blank=True, null=True),
    )]
