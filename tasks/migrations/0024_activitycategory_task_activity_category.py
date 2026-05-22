from django.db import migrations, models
import django.db.models.deletion


def seed_activity_categories(apps, schema_editor):
    Category = apps.get_model('tasks', 'Category')
    ActivityCategory = apps.get_model('tasks', 'ActivityCategory')
    Task = apps.get_model('tasks', 'Task')
    UserTask = apps.get_model('tasks', 'UserTask')

    for category in Category.objects.filter(category_members__isnull=True).distinct():
        ActivityCategory.objects.get_or_create(
            name=category.name,
            section=category.section,
        )

    self_task_map = {}
    for user_task in UserTask.objects.filter(
        assigned_by_id=models.F('assigned_to_id'),
        task__category__isnull=False,
    ).select_related('task', 'task__category', 'assigned_to'):
        self_task_map.setdefault(user_task.task_id, user_task)

    for task_id, user_task in self_task_map.items():
        task = user_task.task
        category = task.category
        if not category:
            continue

        section = getattr(user_task.assigned_to, 'section', '') or category.section
        activity_category, _ = ActivityCategory.objects.get_or_create(
            name=category.name,
            section=section,
        )
        Task.objects.filter(pk=task_id).update(activity_category_id=activity_category.id)


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0023_usertask_completion_description'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('section', models.CharField(choices=[('innovation_consultancy', 'Innovation and Consultancy Services'), ('construction_engineering', 'Construction and Engineering'), ('legal_services', 'Legal Services'), ('investment', 'Investment'), ('joint_venture', 'Joint Venture'), ('internal_audit', 'Internal Audit'), ('finance_accounting', 'Finance and Accounting Management'), ('procurement', 'Procurement Management'), ('administration', 'Administration'), ('public_affairs', 'Public Affairs and Information'), ('ict', 'Information, Communication and Technology'), ('property_management', 'Property Management'), ('human_resource', 'Human Resource Management')], max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('name', 'section')},
            },
        ),
        migrations.AddField(
            model_name='task',
            name='activity_category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='tasks.activitycategory'),
        ),
        migrations.RunPython(seed_activity_categories, migrations.RunPython.noop),
    ]
