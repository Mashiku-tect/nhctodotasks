from django.conf import settings
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

    def test_message_middleware_runs_before_session_security_middleware(self):
        message_middleware = "django.contrib.messages.middleware.MessageMiddleware"
        session_security_middleware = "accounts.middleware.SessionSecurityMiddleware"

        self.assertLess(
            settings.MIDDLEWARE.index(message_middleware),
            settings.MIDDLEWARE.index(session_security_middleware),
        )

    def test_admin_requests_bypass_session_enforcement(self):
        admin_user = User.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="AdminPass123!",
            section="ict",
            role="manager",
        )
        UserSession.objects.create(user=admin_user, session_key="stale-session-key")

        self.client.force_login(admin_user)
        response = self.client.get(f"/{settings.ADMIN_URL_PREFIX}")

        self.assertNotEqual(response.status_code, 302)
        self.assertTrue(get_user(self.client).is_authenticated)


class SuperuserAccessTests(TestCase):
    def setUp(self):
        self.password = "AdminPass123!"
        self.superuser = User.objects.create_superuser(
            username="localadmin",
            email="localadmin@example.com",
            password=self.password,
            section="ict",
            role="manager",
        )

    def test_superuser_can_login_without_active_directory_configuration(self):
        response = self.client.post(reverse("login"), {
            "username": self.superuser.username,
            "password": self.password,
        })

        self.assertRedirects(response, reverse("reports_performance"))
        self.superuser.refresh_from_db()
        self.assertEqual(self.superuser.role, "manager")

    def test_superuser_cannot_use_app_user_management_views(self):
        self.client.force_login(self.superuser)

        add_user_response = self.client.get(reverse("add_user"))
        manage_users_response = self.client.get(reverse("manage_users"))

        self.assertEqual(add_user_response.status_code, 403)
        self.assertEqual(manage_users_response.status_code, 403)

    def test_superuser_role_is_forced_to_manager(self):
        user = User.objects.create_superuser(
            username="anotheradmin",
            email="anotheradmin@example.com",
            password=self.password,
            section="ict",
            role="staff",
            staff_type="senior",
        )

        self.assertEqual(user.role, "manager")
        self.assertEqual(user.staff_type, "")

    def test_superuser_sees_manager_navigation_links(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("reports_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Task")
        self.assertContains(response, "My Tasks")
        self.assertContains(response, "Assigned Tasks")
        self.assertContains(response, "Daily Digest")
        self.assertContains(response, "Django Admin")
        self.assertNotContains(response, "Add Users")
        self.assertNotContains(response, "Manage Users")
