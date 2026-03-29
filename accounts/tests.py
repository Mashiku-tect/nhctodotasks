from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class LoginViewTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.manager = User.objects.create_user(
            username="manager1",
            email="manager1@example.com",
            password=self.password,
            section="ict",
            role="manager",
        )
        self.staff = User.objects.create_user(
            username="staff1",
            email="staff1@example.com",
            password=self.password,
            section="ict",
            role="staff",
        )

    def test_manager_login_redirects_to_dashboard(self):
        response = self.client.post(reverse("login"), {
            "username": self.manager.username,
            "password": self.password,
        })

        self.assertRedirects(response, reverse("reports_performance"))

    def test_staff_login_redirects_to_dashboard(self):
        response = self.client.post(reverse("login"), {
            "username": self.staff.username,
            "password": self.password,
        })

        self.assertRedirects(response, reverse("reports_performance"))

    def test_invalid_login_shows_error(self):
        response = self.client.post(reverse("login"), {
            "username": self.staff.username,
            "password": "wrong-password",
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        messages = list(response.context["messages"])
        self.assertTrue(any("Invalid username or password" in str(message) for message in messages))
