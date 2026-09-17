"""Carry the post authored on the local site to newly migrated databases."""

from datetime import datetime

from django.db import migrations


SOURCE_ID = "153c4936cba745d3a3e89f07891885c4"
CONTENT_DOC = {
    "version": 1,
    "blocks": [{
        "type": "paragraph",
        "align": "left",
        "runs": [{
            "text": "미드 차이일까 원딜 차이일까 ",
            "font": "sans",
            "size": 16,
            "color": "#26354b",
            "bold": False,
            "italic": False,
            "underline": False,
        }],
    }],
}


def transfer_project_post(apps, schema_editor):
    User = apps.get_model("accounts", "CustomUser")
    Post = apps.get_model("community", "CommunityPost")
    database = schema_editor.connection.alias

    if Post.objects.using(database).filter(source_id=SOURCE_ID).exists():
        return
    owner = User.objects.using(database).filter(username="test1", email="test1@example.test").first()
    if owner is None:
        # The review username already belongs to a different account.
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT nextval('community_post_number_seq')")
        post_number = f"{cursor.fetchone()[0]:06d}"

    Post.objects.using(database).create(
        source_id=SOURCE_ID,
        post_number=post_number,
        board="teams",
        team_code="HH",
        owner_id=owner.pk,
        author="진성칰갈",
        title="이번에 한화 진 거 좀 아쉽지 않음?",
        content="미드 차이일까 원딜 차이일까",
        content_doc=CONTENT_DOC,
        category="경기토론",
        created_at=datetime.fromisoformat("2026-09-15T09:31:52.530273+00:00"),
        views=5,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_transfer_project_accounts"),
        ("community", "0005_communitypostimage_course"),
    ]
    operations = [migrations.RunPython(transfer_project_post, migrations.RunPython.noop)]
