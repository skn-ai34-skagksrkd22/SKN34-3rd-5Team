"""Carry the project review accounts to databases created from this branch."""

from datetime import datetime

from django.db import migrations


# One-way Django password verifier copied from the local review account.
# The shared password itself is intentionally absent from source control.
COMMON_PASSWORD_HASH = (
    "pbkdf2_sha256$1500000$w0NJcaQoDVDi6hwVObB1Lh$"
    "SCJ6J650dnKMQeSBjxCUYSQg3Ycvzkgn0Qqs9gs2J78="
)

REVIEW_ACCOUNTS = (
    ("test1", "진성칰갈", "NC", "2026-09-15T06:54:36.829975+00:00", False),
    ("test2", "", "", "2026-09-15T06:54:37.109344+00:00", False),
    ("test3", "", "", "2026-09-15T06:54:37.389353+00:00", False),
    ("test4", "", "", "2026-09-15T06:54:37.674930+00:00", False),
    ("test5", "", "", "2026-09-15T06:54:37.987114+00:00", False),
    ("master1", "", "", "2026-09-15T07:16:07.136931+00:00", True),
)


def transfer_project_accounts(apps, schema_editor):
    User = apps.get_model("accounts", "CustomUser")
    database = schema_editor.connection.alias

    for username, nickname, team_code, joined_at, is_staff in REVIEW_ACCOUNTS:
        expected_email = f"{username}@example.test"
        user = User.objects.using(database).filter(username=username).first()
        if user is not None and user.email != expected_email:
            # A matching username with another email belongs to someone else.
            continue

        fields = {
            "email": expected_email,
            "password": COMMON_PASSWORD_HASH,
            "nickname": nickname,
            "team_code": team_code,
            "is_active": True,
            "is_staff": is_staff,
            "is_superuser": False,
        }
        if user is None:
            User.objects.using(database).create(
                username=username,
                date_joined=datetime.fromisoformat(joined_at),
                **fields,
            )
        else:
            User.objects.using(database).filter(pk=user.pk).update(**fields)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_enable_demo_users")]
    operations = [migrations.RunPython(transfer_project_accounts, migrations.RunPython.noop)]
