from django.db import migrations


class Migration(migrations.Migration):
    """신고 처분(계정 정지)을 쓰지 않기로 해서 0006에서 추가한 칸을 지운다."""

    dependencies = [("accounts", "0006_member_suspension")]

    operations = [
        migrations.RemoveField(model_name="customuser", name="suspended_until"),
        migrations.RemoveField(model_name="customuser", name="suspended_permanently"),
    ]
