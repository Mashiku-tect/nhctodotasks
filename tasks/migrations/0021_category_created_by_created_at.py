from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_category_created_at(apps, schema_editor):
    Category = apps.get_model("tasks", "Category")
    Category.objects.filter(created_at__isnull=True).update(created_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tasks", "0020_alter_subtask_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="category",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="created_task_categories",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name="category",
            options={"ordering": ["name"]},
        ),
        migrations.RunPython(
            backfill_category_created_at,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="category",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
