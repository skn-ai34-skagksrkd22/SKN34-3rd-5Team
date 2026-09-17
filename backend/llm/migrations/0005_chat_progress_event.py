import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("llm", "0004_chatturn_chatmessage_status")]

    operations = [
        migrations.AlterField(
            model_name="chatturn",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "대기"),
                    ("completed", "완료"),
                    ("stopped", "중단"),
                    ("failed", "실패"),
                ],
                default="pending",
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name="ChatProgressEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence_no", models.PositiveIntegerField()),
                ("operation_id", models.UUIDField()),
                ("parent_operation_id", models.UUIDField(blank=True, null=True)),
                ("kind", models.CharField(choices=[("phase", "처리"), ("retrieval", "검색"), ("tool", "도구")], max_length=10)),
                ("status", models.CharField(choices=[("started", "시작"), ("completed", "완료"), ("failed", "실패"), ("interrupted", "중단"), ("unknown", "확인 불가")], max_length=12)),
                ("label", models.CharField(max_length=160)),
                ("tool_name", models.CharField(blank=True, max_length=80, null=True)),
                ("tool_call_id", models.CharField(blank=True, max_length=255, null=True)),
                ("arguments", models.JSONField(blank=True, null=True)),
                ("result", models.JSONField(blank=True, null=True)),
                ("truncated", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("turn", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="progress_events", to="llm.chatturn")),
            ],
            options={
                "ordering": ("sequence_no",),
                "constraints": [models.UniqueConstraint(fields=("turn", "sequence_no"), name="unique_chat_progress_sequence")],
            },
        ),
    ]
