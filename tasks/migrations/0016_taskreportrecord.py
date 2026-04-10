from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_task_report_records(apps, schema_editor):
    UserTask = apps.get_model('tasks', 'UserTask')
    TaskReportRecord = apps.get_model('tasks', 'TaskReportRecord')

    for ut in UserTask.objects.select_related('task', 'assigned_by', 'assigned_to', 'task__category'):
        task = ut.task
        assigned_by = ut.assigned_by
        assigned_to = ut.assigned_to
        TaskReportRecord.objects.update_or_create(
            source_usertask_id=ut.id,
            defaults={
                'source_task_id': task.id,
                'task_title': task.title,
                'task_description': task.description or '',
                'category_name': task.category.name if task.category else '',
                'section': getattr(assigned_to, 'section', '') or getattr(assigned_by, 'section', ''),
                'priority': task.priority,
                'due_date': task.due_date,
                'assigned_by': assigned_by,
                'assigned_to': assigned_to,
                'assigned_by_username': getattr(assigned_by, 'username', '') if assigned_by else '',
                'assigned_to_username': getattr(assigned_to, 'username', '') if assigned_to else '',
                'status': ut.status,
                'review_status': ut.review_status,
                'is_self_task': bool(assigned_by and assigned_to and assigned_by.id == assigned_to.id),
                'task_created_at': task.created_at,
                'task_updated_at': task.updated_at,
                'completed_at': ut.completed_at or task.completed_at,
                'completed_by_username': getattr(task.completed_by, 'username', '') if task.completed_by else '',
                'deleted_at': None,
            }
        )


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0015_notification'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskReportRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_usertask_id', models.PositiveIntegerField(unique=True)),
                ('source_task_id', models.PositiveIntegerField(db_index=True)),
                ('task_title', models.CharField(max_length=255)),
                ('task_description', models.TextField(blank=True)),
                ('category_name', models.CharField(blank=True, max_length=100)),
                ('section', models.CharField(blank=True, max_length=100)),
                ('priority', models.CharField(blank=True, max_length=20)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('assigned_by_username', models.CharField(blank=True, max_length=150)),
                ('assigned_to_username', models.CharField(blank=True, max_length=150)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('overdue', 'Overdue'), ('rejected', 'Rejected'), ('accepted', 'Accepted')], default='pending', max_length=20)),
                ('review_status', models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('is_self_task', models.BooleanField(default=False)),
                ('task_created_at', models.DateTimeField(blank=True, null=True)),
                ('task_updated_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('completed_by_username', models.CharField(blank=True, max_length=150)),
                ('last_synced_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_report_records_assigned', to=settings.AUTH_USER_MODEL)),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_report_records_received', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-task_created_at', '-last_synced_at'],
            },
        ),
        migrations.RunPython(backfill_task_report_records, migrations.RunPython.noop),
    ]
