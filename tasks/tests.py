from datetime import timedelta

from django.test import TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from accounts.models import User
from tasks.models import Task, UserTask


class StaffPerformanceReportTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager_ict",
            email="manager_ict@example.com",
            password="StrongPass123!",
            section="ict",
            role="manager",
        )
        self.staff_one = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="StrongPass123!",
            section="ict",
            role="staff",
        )
        self.staff_two = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="StrongPass123!",
            section="ict",
            role="staff",
        )
        self.other_section_staff = User.objects.create_user(
            username="charles",
            email="charles@example.com",
            password="StrongPass123!",
            section="finance_accounting",
            role="staff",
        )

        today = timezone.localdate()

        task_one = Task.objects.create(
            title="Prepare weekly report",
            description="",
            due_date=today + timedelta(days=2),
            priority="normal",
        )
        UserTask.objects.create(
            task=task_one,
            assigned_by=self.manager,
            assigned_to=self.staff_one,
            status="completed",
            completed_at=timezone.now(),
        )

        task_two = Task.objects.create(
            title="Update stock register",
            description="",
            due_date=today + timedelta(days=3),
            priority="high",
        )
        UserTask.objects.create(
            task=task_two,
            assigned_by=self.manager,
            assigned_to=self.staff_two,
            status="pending",
        )

        other_task = Task.objects.create(
            title="Finance reconciliation",
            description="",
            due_date=today + timedelta(days=4),
            priority="normal",
        )
        UserTask.objects.create(
            task=other_task,
            assigned_by=self.other_section_staff,
            assigned_to=self.other_section_staff,
            status="pending",
        )

    def test_staff_dashboard_shows_colleagues_in_same_section(self):
        self.client.force_login(self.staff_one)

        response = self.client.get(reverse("reports_performance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.staff_one.username)
        self.assertContains(response, self.staff_two.username)
        self.assertNotContains(response, self.other_section_staff.username)

    def test_manager_dashboard_shows_only_their_section(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("reports_performance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.staff_one.username)
        self.assertContains(response, self.staff_two.username)
        self.assertNotContains(response, self.other_section_staff.username)

    def test_task_routes_are_not_conflicting(self):
        task = Task.objects.create(
            title="Separate routes check",
            description="",
            due_date=timezone.localdate() + timedelta(days=1),
            priority="normal",
        )
        UserTask.objects.create(
            task=task,
            assigned_by=self.staff_one,
            assigned_to=self.staff_one,
            status="pending",
        )

        detail_url = reverse("task_detail", args=[task.id])
        do_url = reverse("do_task", args=[task.id])

        self.assertEqual(detail_url, f"/tasks/tasks/{task.id}/")
        self.assertEqual(do_url, f"/tasks/tasks/{task.id}/do/")
        self.assertEqual(resolve(detail_url).view_name, "task_detail")
        self.assertEqual(resolve(do_url).view_name, "do_task")
