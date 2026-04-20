from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_usersession"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="staff_type",
            field=models.CharField(
                blank=True,
                choices=[("senior", "Senior"), ("icto", "ICT Officer")],
                default="",
                max_length=20,
            ),
        ),
    ]
