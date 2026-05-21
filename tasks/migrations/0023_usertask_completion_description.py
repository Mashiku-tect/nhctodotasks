from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0022_alter_usertask_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='usertask',
            name='completion_description',
            field=models.TextField(blank=True),
        ),
    ]
