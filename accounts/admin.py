from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User

class UserAdmin(BaseUserAdmin):
    # What fields are displayed in admin list view
    list_display = ("username", "email", "section", "role", "is_staff", "is_superuser", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active", "role")

    # The fields displayed on the user edit page
    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        (_("Personal info"), {"fields": ("section", "role")}),
        (_("Permissions"), {"fields": ("is_staff", "is_superuser", "is_active", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login",)}),
    )

    # Fields for creating a new user
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2", "section", "role", "is_staff", "is_superuser", "is_active"),
        }),
    )

    search_fields = ("username", "email", "section", "role")
    ordering = ("username",)
    filter_horizontal = ("groups", "user_permissions",)

# Register the custom user
admin.site.register(User, UserAdmin)
