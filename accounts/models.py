# accounts/models.py
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
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

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        blank=True
    )

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["section", "role"]
# email + password only

    def __str__(self):
        return self.email
