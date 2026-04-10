from django.db import migrations, models


def seed_usernames(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    existing_usernames = set(
        User.objects.exclude(username__isnull=True)
        .exclude(username__exact="")
        .values_list("username", flat=True)
    )

    for user in User.objects.order_by("id"):
        if user.username:
            continue

        local_part = (user.email or "").split("@")[0].strip().lower()
        base_username = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in local_part) or f"user{user.id}"
        candidate = base_username
        suffix = 1

        while candidate in existing_usernames:
            candidate = f"{base_username}{suffix}"
            suffix += 1

        user.username = candidate
        user.save(update_fields=["username"])
        existing_usernames.add(candidate)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_user_section"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="username",
            field=models.CharField(blank=True, max_length=150, null=True, unique=True),
        ),
        migrations.RunPython(seed_usernames, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(max_length=150, unique=True),
        ),
    ]
