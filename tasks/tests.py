from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from accounts.models import User
from tasks.models import Task, UserTask, DailyCheckIn, Category, CategoryMember


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
            staff_type="senior",
        )
        self.staff_two = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="StrongPass123!",
            section="ict",
            role="staff",
            staff_type="icto",
        )
        self.other_section_staff = User.objects.create_user(
            username="charles",
            email="charles@example.com",
            password="StrongPass123!",
            section="finance_accounting",
            role="staff",
            staff_type="senior",
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

    def test_staff_dashboard_hides_header_and_filters(self):
        self.client.force_login(self.staff_one)

        response = self.client.get(reverse("reports_performance"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Staff Performance")
        self.assertNotContains(response, "Filter Report")
        self.assertNotContains(response, "Ranking is based only on manager-assigned tasks")

    def test_staff_dashboard_hides_other_staff_zero_percent_badge_only(self):
        self.client.force_login(self.staff_one)

        response = self.client.get(reverse("reports_performance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.staff_two.username)
        self.assertNotContains(response, '<div class="rate-pill">0%</div>', html=False)

    def test_staff_dashboard_keeps_own_zero_percent_badge_visible(self):
        self.client.force_login(self.staff_two)

        response = self.client.get(reverse("reports_performance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.staff_two.username)
        self.assertContains(response, '<div class="rate-pill">0%</div>', html=False)

    def test_manager_dashboard_shows_only_their_section(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("reports_performance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.staff_one.username)
        self.assertContains(response, self.staff_two.username)
        self.assertNotContains(response, self.other_section_staff.username)

    def test_dashboard_groups_staff_by_category(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("reports_performance"))

        self.assertEqual(response.status_code, 200)
        grouped = response.context["grouped_performance_data"]
        grouped_by_key = {group["key"]: group for group in grouped}

        self.assertIn("senior", grouped_by_key)
        self.assertIn("icto", grouped_by_key)
        self.assertEqual([item["staff"] for item in grouped_by_key["senior"]["items"]], [self.staff_one])
        self.assertEqual([item["staff"] for item in grouped_by_key["icto"]["items"]], [self.staff_two])

    def test_dashboard_can_filter_single_staff_category(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("reports_performance"), {"staff_type": "senior"})

        self.assertEqual(response.status_code, 200)
        performance_data = list(response.context["performance_data"])
        self.assertEqual([item["staff"] for item in performance_data], [self.staff_one])
        self.assertContains(response, "Senior")
        self.assertNotContains(response, self.staff_two.username)

    def test_fresh_pending_task_does_not_reduce_staff_ranking_score(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("reports_performance"))

        self.assertEqual(response.status_code, 200)
        performance_data = list(response.context["performance_data"])
        alice_data = next(item for item in performance_data if item["staff"] == self.staff_one)
        bob_data = next(item for item in performance_data if item["staff"] == self.staff_two)
        initial_alice_score = alice_data["performance_score"]

        self.assertGreaterEqual(initial_alice_score, 0)
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

        self.assertEqual(alice_data["performance_score"], initial_alice_score)
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

        self.assertEqual(detail_url, f"/{settings.TASKS_URL_PREFIX}tasks/{task.id}/")
        self.assertEqual(do_url, f"/{settings.TASKS_URL_PREFIX}tasks/{task.id}/do/")
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
        category = Category.objects.create(name="Networks", section="ict")
        CategoryMember.objects.create(category=category, user=self.staff_two)

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
        response = self.client.post(
            reverse("reassign_task", args=[task.id]),
            {
                "category_id": str(category.id),
                "assigned_to": str(self.staff_two.id),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.staff_two.notifications.filter(notification_type="task_reassigned", task=task).exists())
        self.assertTrue(self.manager.notifications.filter(notification_type="task_reassigned", task=task).exists())

        response = self.client.post(reverse("review_task", args=[task.id]), {"action": "reject", "reason": "Missing file"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.staff_two.notifications.filter(notification_type="task_rejected", task=task).exists())

        response = self.client.post(reverse("review_task", args=[task.id]), {"action": "accept"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.staff_two.notifications.filter(notification_type="task_accepted", task=task).exists())


class DailyAccountabilityBoardTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager_ict",
            email="manager_ict@example.com",
            password="StrongPass123!",
            section="ict",
            role="manager",
        )
        self.staff = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="StrongPass123!",
            section="ict",
            role="staff",
        )

        self.task = Task.objects.create(
            title="Prepare LAN checklist",
            description="",
            due_date=timezone.localdate() + timedelta(days=1),
            priority="high",
        )
        self.user_task = UserTask.objects.create(
            task=self.task,
            assigned_by=self.manager,
            assigned_to=self.staff,
            status="pending",
        )

        overdue_task = Task.objects.create(
            title="Old unresolved issue",
            description="",
            due_date=timezone.localdate() - timedelta(days=1),
            priority="high",
        )
        self.overdue_user_task = UserTask.objects.create(
            task=overdue_task,
            assigned_by=self.manager,
            assigned_to=self.staff,
            status="pending",
        )

    def test_staff_can_submit_daily_checkin(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("daily_board"),
            {
                "action": "submit",
                "priority_task_ids": [str(self.user_task.id)],
                "morning_focus": "Finish the network checklist",
                "progress_update": "Started verification",
                "end_of_day_summary": "Completed rack audit",
                "tomorrow_plan": "Send summary report",
                "blockers": "Need switch room key",
            },
        )

        self.assertEqual(response.status_code, 302)
        checkin = DailyCheckIn.objects.get(user=self.staff, entry_date=timezone.localdate())
        self.assertTrue(checkin.is_submitted)
        self.assertEqual(checkin.priority_tasks.count(), 1)
        self.assertEqual(checkin.priority_tasks.first(), self.user_task)

    def test_manager_digest_shows_staff_submission(self):
        checkin = DailyCheckIn.objects.create(
            user=self.staff,
            entry_date=timezone.localdate(),
            morning_focus="Finish the network checklist",
            progress_update="Halfway done",
            blockers="Waiting for access",
            is_submitted=True,
            submitted_at=timezone.now(),
        )
        checkin.priority_tasks.add(self.user_task)

        self.client.force_login(self.manager)
        response = self.client.get(reverse("daily_digest"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.staff.username)
        self.assertContains(response, "Submitted")
        self.assertContains(response, "Waiting for access")

    def test_daily_board_hides_overdue_tasks_from_priority_selection(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("daily_board"))

        self.assertEqual(response.status_code, 200)
        open_task_titles = [usertask.task.title for usertask in response.context["open_tasks"]]
        self.assertIn(self.task.title, open_task_titles)
        self.assertNotIn(self.overdue_user_task.task.title, open_task_titles)

    def test_empty_daily_submit_is_rejected(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("daily_board"),
            {"action": "submit"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        checkin = DailyCheckIn.objects.get(user=self.staff, entry_date=timezone.localdate())
        self.assertFalse(checkin.is_submitted)
        messages = list(response.context["messages"])
        self.assertTrue(any("Add at least one update" in str(message) for message in messages))

    def test_manager_can_open_daily_checkin_detail(self):
        checkin = DailyCheckIn.objects.create(
            user=self.staff,
            entry_date=timezone.localdate(),
            morning_focus="Finish the network checklist",
            progress_update="Halfway done",
            is_submitted=True,
            submitted_at=timezone.now(),
        )
        checkin.priority_tasks.add(self.user_task)

        self.client.force_login(self.manager)
        response = self.client.get(reverse("daily_checkin_detail", args=[self.staff.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.staff.username)
        self.assertContains(response, "Finish the network checklist")


class ReassignTaskCategoryTests(TestCase):
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

        self.category = Category.objects.create(name="Networks", section="ict")
        CategoryMember.objects.create(category=self.category, user=self.staff_two)

        self.other_category = Category.objects.create(name="Finance Ops", section="finance_accounting")
        CategoryMember.objects.create(category=self.other_category, user=self.other_section_staff)

        self.task = Task.objects.create(
            title="Recover internet link",
            description="",
            due_date=timezone.localdate() - timedelta(days=1),
            priority="high",
        )
        UserTask.objects.create(
            task=self.task,
            assigned_by=self.manager,
            assigned_to=self.staff_one,
            status="pending",
        )

    def test_manager_can_reassign_using_selected_category(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("reassign_task", args=[self.task.id]),
            {
                "category_id": str(self.category.id),
                "assigned_to": str(self.staff_two.id),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.category, self.category)
        self.assertTrue(
            UserTask.objects.filter(
                task=self.task,
                assigned_to=self.staff_two,
                assigned_by=self.manager,
            ).exists()
        )

    def test_category_users_json_only_returns_staff_from_manager_section(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("category_users_json"),
            {"category_id": self.other_category.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["users"], [])

    def test_staff_detail_can_render_embedded_panel_for_dashboard(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("staff_detail", args=[self.staff_one.id]),
            {"panel": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.staff_one.username)
        self.assertContains(response, "All Tasks")
