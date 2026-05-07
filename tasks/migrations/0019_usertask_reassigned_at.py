from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0018_dailycheckin'),
    ]

    operations = [
        migrations.AddField(
            model_name='usertask',
            name='reassigned_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
