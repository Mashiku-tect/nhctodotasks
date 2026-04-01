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

    def test_fresh_pending_task_does_not_reduce_staff_ranking_score(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("reports_performance"))

        self.assertEqual(response.status_code, 200)
        performance_data = list(response.context["performance_data"])
        alice_data = next(item for item in performance_data if item["staff"] == self.staff_one)
        bob_data = next(item for item in performance_data if item["staff"] == self.staff_two)

        self.assertEqual(alice_data["performance_score"], 100.0)
        self.assertEqual(bob_data["performance_score"], 0)

        second_task = Task.objects.create(
            title="Fresh assignment should not hurt score",
            description="",
            due_date=timezone.localdate() + timedelta(days=5),
            priority="normal",
        )
        UserTask.objects.create(
            task=second_task,
            assigned_by=self.manager,
            assigned_to=self.staff_one,
            status="pending",
        )

        response = self.client.get(reverse("reports_performance"))
        self.assertEqual(response.status_code, 200)
        performance_data = list(response.context["performance_data"])
        alice_data = next(item for item in performance_data if item["staff"] == self.staff_one)

        self.assertEqual(alice_data["performance_score"], 100.0)
        self.assertEqual(alice_data["pending_tasks"], 1)

    def test_self_tasks_are_excluded_from_shared_dashboard(self):
        self.client.force_login(self.manager)

        self_task = Task.objects.create(
            title="Private self task",
            description="",
            due_date=timezone.localdate() + timedelta(days=1),
            priority="normal",
        )
        UserTask.objects.create(
            task=self_task,
            assigned_by=self.staff_one,
            assigned_to=self.staff_one,
            status="completed",
            completed_at=timezone.now(),
        )

        response = self.client.get(reverse("reports_performance"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Self Tasks")
        self.assertNotContains(response, "Task Source")
        performance_data = list(response.context["performance_data"])
        alice_data = next(item for item in performance_data if item["staff"] == self.staff_one)
        self.assertEqual(alice_data["total_tasks"], 1)

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


class NotificationTests(TestCase):
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

    def test_staff_gets_due_soon_and_overdue_notifications(self):
        due_soon_task = Task.objects.create(
            title="Submit draft memo",
            description="",
            due_date=timezone.localdate() + timedelta(days=1),
            priority="normal",
        )
        UserTask.objects.create(
            task=due_soon_task,
            assigned_by=self.manager,
            assigned_to=self.staff_one,
            status="pending",
        )

        overdue_task = Task.objects.create(
            title="Finish old report",
            description="",
            due_date=timezone.localdate() - timedelta(days=1),
            priority="high",
        )
        UserTask.objects.create(
            task=overdue_task,
            assigned_by=self.manager,
            assigned_to=self.staff_one,
            status="in_progress",
        )

        self.client.force_login(self.staff_one)
        self.client.get(reverse("reports_performance"))

        notifications = list(self.staff_one.notifications.values_list("notification_type", flat=True))
        self.assertIn("task_due_soon", notifications)
        self.assertIn("task_overdue", notifications)

    def test_manager_gets_overdue_and_review_delay_notifications(self):
        overdue_task = Task.objects.create(
            title="Overdue assignment",
            description="",
            due_date=timezone.localdate() - timedelta(days=1),
            priority="normal",
        )
        UserTask.objects.create(
            task=overdue_task,
            assigned_by=self.manager,
            assigned_to=self.staff_one,
            status="pending",
        )

        review_task = Task.objects.create(
            title="Waiting review",
            description="",
            due_date=timezone.localdate() - timedelta(days=3),
            priority="normal",
        )
        UserTask.objects.create(
            task=review_task,
            assigned_by=self.manager,
            assigned_to=self.staff_two,
            status="completed",
            review_status="pending",
            completed_at=timezone.now() - timedelta(days=3),
        )

        self.client.force_login(self.manager)
        self.client.get(reverse("reports_performance"))

        notifications = list(self.manager.notifications.values_list("notification_type", flat=True))
        self.assertIn("assigned_task_overdue", notifications)
        self.assertIn("task_review_delay", notifications)

    def test_reassignment_and_review_actions_create_notifications(self):
        task = Task.objects.create(
            title="Network setup",
            description="",
            due_date=timezone.localdate() + timedelta(days=2),
            priority="normal",
        )
        UserTask.objects.create(
            task=task,
            assigned_by=self.manager,
            assigned_to=self.staff_one,
            status="pending",
        )

        self.client.force_login(self.manager)
        response = self.client.post(reverse("reassign_task", args=[task.id]), {"assigned_to": self.staff_two.id})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.staff_two.notifications.filter(notification_type="task_reassigned", task=task).exists())
        self.assertTrue(self.manager.notifications.filter(notification_type="task_reassigned", task=task).exists())

        response = self.client.post(reverse("review_task", args=[task.id]), {"action": "reject", "reason": "Missing file"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.staff_two.notifications.filter(notification_type="task_rejected", task=task).exists())

        response = self.client.post(reverse("review_task", args=[task.id]), {"action": "accept"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.staff_two.notifications.filter(notification_type="task_accepted", task=task).exists())
