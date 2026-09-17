from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_transfer_project_accounts")]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="suspended_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customuser",
            name="suspended_permanently",
            field=models.BooleanField(default=False),
        ),
    ]
