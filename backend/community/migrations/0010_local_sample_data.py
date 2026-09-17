"""로컬에서 만든 검토용 샘플 데이터(게시글·신고)를 새로 마이그레이션하는 DB에도 넣는다.

- 계정: test1~5, master1 은 accounts.0005 가 만든다. 여기서는 비어 있는 test2 닉네임만 채운다.
- 게시글: 팀 게시판 글 1개. 사진 파일은 옮길 수 없어서 사진 블록은 빼고 글자만 넣는다.
- 신고: test3 이 신고한 2건 (관리자 마이페이지 '신고 관리'에서 볼 수 있다).
이미 있는 데이터는 건드리지 않고, 같은 아이디가 다른 사람 계정이면 건너뛴다.
"""

from datetime import datetime

from django.db import migrations

TRANSFERRED_POST_ID = "153c4936cba745d3a3e89f07891885c4"   # community.0006 이 넣는 글
SAMPLE_POST_ID = "e25bc43f62554ec2adc6fbd683fc397b"
SAMPLE_POST_DOC = {
    "version": 1,
    "blocks": [{
        "type": "paragraph",
        "align": "left",
        "runs": [{
            "text": "Cristiano Ronaldo dos Santos Aveiro",
            "font": "sans",
            "size": 32,
            "color": "#e1131b",
            "bold": True,
            "italic": False,
            "underline": False,
        }],
    }],
}
REPORTS = (
    (TRANSFERRED_POST_ID, "inappropriate", "롤대남", "2026-09-16T08:24:25.187+00:00"),
    (SAMPLE_POST_ID, "inappropriate", "허위사실유포", "2026-09-16T08:24:44.205+00:00"),
)


def review_user(User, database, username):
    return User.objects.using(database).filter(username=username, email=f"{username}@example.test").first()


def add_local_sample_data(apps, schema_editor):
    User = apps.get_model("accounts", "CustomUser")
    Post = apps.get_model("community", "CommunityPost")
    Report = apps.get_model("community", "CommunityReport")
    database = schema_editor.connection.alias

    author = review_user(User, database, "test2")
    if author is not None and not author.nickname:
        author.nickname = "신그는날두인가"
        author.save(update_fields=["nickname"])

    if author is not None and not Post.objects.using(database).filter(source_id=SAMPLE_POST_ID).exists():
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("SELECT nextval('community_post_number_seq')")
            post_number = f"{cursor.fetchone()[0]:06d}"
        Post.objects.using(database).create(
            source_id=SAMPLE_POST_ID,
            post_number=post_number,
            board="teams",
            team_code="HH",
            owner_id=author.pk,
            author="신그는날두인가",
            title="역사상 가장 위대한 선수",
            content="Cristiano Ronaldo dos Santos Aveiro",
            content_doc=SAMPLE_POST_DOC,
            category="경기토론",
            created_at=datetime.fromisoformat("2026-09-16T08:23:16.629+00:00"),
            views=5,
        )

    reporter = review_user(User, database, "test3")
    if reporter is None:
        return
    for source_id, reason, detail, created_at in REPORTS:
        post = Post.objects.using(database).filter(source_id=source_id).first()
        if post is None:
            continue
        report, created = Report.objects.using(database).get_or_create(
            post=post, reporter=reporter, defaults={"reason": reason, "detail": detail},
        )
        if created:
            # created_at 은 auto_now_add 라 만든 뒤에 원래 신고 시각으로 맞춘다
            Report.objects.using(database).filter(pk=report.pk).update(created_at=datetime.fromisoformat(created_at))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_remove_member_suspension"),
        ("community", "0006_transfer_project_post"),
        ("community", "0009_report_moderation"),
    ]
    # 되돌려도 사용자가 손댔을 수 있는 데이터는 지우지 않는다
    operations = [migrations.RunPython(add_local_sample_data, migrations.RunPython.noop)]
