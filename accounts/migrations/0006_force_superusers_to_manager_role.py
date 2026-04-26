from django.db import migrations


def force_superusers_to_manager_role(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_superuser=True).update(role="manager", staff_type="")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_user_staff_type"),
    ]

    operations = [
        migrations.RunPython(
            force_superusers_to_manager_role,
            migrations.RunPython.noop,
        ),
    ]
