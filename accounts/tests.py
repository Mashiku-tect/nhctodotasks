from django.test import TestCase
from django.urls import reverse

from django.contrib.auth import get_user
from django.contrib.messages import get_messages
from django.utils import timezone

from accounts.models import User, UserSession


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

    def test_login_creates_single_active_session_record(self):
        response = self.client.post(reverse("login"), {
            "username": self.staff.username,
            "password": self.password,
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(UserSession.objects.filter(user=self.staff).exists())


class SessionSecurityTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.user = User.objects.create_user(
            username="sessionuser",
            email="sessionuser@example.com",
            password=self.password,
            section="ict",
            role="staff",
        )

    def test_previous_session_is_invalidated_when_same_user_logs_in_elsewhere(self):
        client_one = self.client_class()
        client_two = self.client_class()

        login_payload = {"username": self.user.username, "password": self.password}
        response_one = client_one.post(reverse("login"), login_payload)
        response_two = client_two.post(reverse("login"), login_payload)

        self.assertEqual(response_one.status_code, 302)
        self.assertEqual(response_two.status_code, 302)

        response = client_one.get(reverse("reports_performance"), follow=True)

        self.assertEqual(get_user(client_one).is_authenticated, False)
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(any("another browser or device" in message for message in messages))

    def test_idle_session_timeout_logs_user_out(self):
        self.client.post(reverse("login"), {
            "username": self.user.username,
            "password": self.password,
        })
        session = self.client.session
        session["last_activity_ts"] = int(timezone.now().timestamp()) - 4000
        session.save()

        response = self.client.get(reverse("reports_performance"), follow=True)

        self.assertEqual(get_user(self.client).is_authenticated, False)
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(any("idle for too long" in message for message in messages))
