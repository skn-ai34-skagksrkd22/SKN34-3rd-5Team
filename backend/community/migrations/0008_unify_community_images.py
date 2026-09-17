import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("community", "0007_merge_draft_and_rich_content"),
        ("travel", "0006_merge_course_engagement_content_doc"),
    ]
    operations = [
        migrations.RemoveConstraint(model_name="communityimage", name="community_image_single_target"),
        migrations.AddField(
            model_name="communityimage",
            name="course",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="images", to="travel.course",
            ),
        ),
        migrations.AddConstraint(
            model_name="communityimage",
            constraint=models.CheckConstraint(
                condition=(
                    (Q(draft__isnull=True) & Q(post__isnull=True))
                    | (Q(draft__isnull=True) & Q(course__isnull=True))
                    | (Q(post__isnull=True) & Q(course__isnull=True))
                ),
                name="community_image_single_target",
            ),
        ),
    ]
