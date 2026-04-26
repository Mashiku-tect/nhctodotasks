# accounts/models.py
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models

class CustomUserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError("Username must be set")
        if not email:
            raise ValueError("Email must be set")
        username = username.strip()
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields["role"] = "manager"
        extra_fields.setdefault("staff_type", "")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    SECTION_CHOICES = (
        ("registry", "Registry"),
        ("business_development", "Business Development"),
        ("innovation_consultancy", "Innovation and Consultancy Services"),
        ("construction_engineering", "Construction and Engineering"),
        ("legal_services", "Legal Services"),
        ("investment", "Investment"),
        ("joint_venture", "Joint Venture"),
        ("internal_audit", "Internal Audit"),
        ("finance_accounting", "Finance and Accounting Management"),
        ("procurement", "Procurement Management"),
        ("administration", "Administration"),
        ("public_affairs", "Public Affairs and Information"),
        ("ict", "Information, Communication and Technology"),
        ("property_management", "Property Management"),
        ("human_resource", "Human Resource Management"),
    )

    section = models.CharField(
        max_length=100,
        choices=SECTION_CHOICES,
        blank=True
    )

    ROLE_CHOICES = (
        ("manager", "Manager"),
        ("staff", "Staff"),
    )

    STAFF_TYPE_CHOICES = (
        ("senior", "Senior"),
        ("icto", "ICT Officer"),
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        blank=True
    )

    staff_type = models.CharField(
        max_length=20,
        choices=STAFF_TYPE_CHOICES,
        blank=True,
        default="",
    )

    objects = CustomUserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "section", "role"]
# username + password login, email retained for contact/reference

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = "manager"
            self.staff_type = ""
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


class UserSession(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="active_session",
    )
    session_key = models.CharField(max_length=40, unique=True)
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} -> {self.session_key}"
