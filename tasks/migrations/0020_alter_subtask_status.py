from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0019_usertask_reassigned_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subtask',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('in_progress', 'In Progress'),
                    ('completed', 'Completed'),
                ],
                default='in_progress',
                max_length=20,
            ),
        ),
    ]
