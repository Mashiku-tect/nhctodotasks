from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.test import override_settings
from django.urls import resolve, reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import ANY, patch

from accounts.models import User
from tasks.models import Task, UserTask, DailyCheckIn, Category, CategoryMember, Notification, SubTask
from tasks.notifications import send_notification_email


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
        self.assertContains(response, "Summary of Senior Staff and ICTO Staff Performance")
        self.assertNotContains(response, "Filter Report")
        self.assertNotContains(response, "Click any staff row below to open their details on the right")

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
        self.assertContains(response, '<div class="perf-score">0%</div>', html=False)

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

    def test_in_progress_tasks_are_not_counted_as_pending_in_performance_report(self):
        self.client.force_login(self.manager)

        task = Task.objects.create(
            title="Follow up vendor issue",
            description="",
            due_date=timezone.localdate() + timedelta(days=2),
            priority="normal",
        )
        UserTask.objects.create(
            task=task,
            assigned_by=self.manager,
            assigned_to=self.staff_one,
            status="in_progress",
        )

        response = self.client.get(reverse("reports_performance"))

        self.assertEqual(response.status_code, 200)
        performance_data = list(response.context["performance_data"])
        alice_data = next(item for item in performance_data if item["staff"] == self.staff_one)
        senior_group = next(group for group in response.context["grouped_performance_data"] if group["key"] == "senior")

        self.assertEqual(alice_data["pending_tasks"], 0)
        self.assertEqual(alice_data["in_progress_tasks"], 1)
        self.assertEqual(senior_group["summary"]["pending_tasks"], 0)
        self.assertEqual(senior_group["summary"]["in_progress_tasks"], 1)

    def test_rejected_tasks_are_not_double_counted_as_pending_or_overdue(self):
        self.client.force_login(self.manager)

        rejected_task = Task.objects.create(
            title="Rejected overdue task",
            description="",
            due_date=timezone.localdate() - timedelta(days=1),
            priority="normal",
        )
        UserTask.objects.create(
            task=rejected_task,
            assigned_by=self.manager,
            assigned_to=self.staff_one,
            status="pending",
            review_status="rejected",
        )

        response = self.client.get(reverse("reports_performance"))

        self.assertEqual(response.status_code, 200)
        performance_data = list(response.context["performance_data"])
        alice_data = next(item for item in performance_data if item["staff"] == self.staff_one)

        self.assertEqual(alice_data["rejected_tasks"], 1)
        self.assertEqual(alice_data["pending_tasks"], 0)
        self.assertEqual(alice_data["overdue_tasks"], 0)

    def test_manager_assigned_completed_task_needs_acceptance_before_counting_in_score(self):
        self.client.force_login(self.manager)

        review_task = Task.objects.create(
            title="Awaiting manager review",
            description="",
            due_date=timezone.localdate() + timedelta(days=1),
            priority="normal",
        )
        user_task = UserTask.objects.create(
            task=review_task,
            assigned_by=self.manager,
            assigned_to=self.staff_one,
            status="completed",
            review_status="pending",
            completed_at=timezone.now(),
        )

        response = self.client.get(reverse("reports_performance"))
        self.assertEqual(response.status_code, 200)
        performance_data = list(response.context["performance_data"])
        alice_data = next(item for item in performance_data if item["staff"] == self.staff_one)

        self.assertEqual(alice_data["completed_tasks"], 1)
        self.assertEqual(alice_data["on_time_completed"], 1)

        user_task.review_status = "accepted"
        user_task.save(update_fields=["review_status"])

        response = self.client.get(reverse("reports_performance"))
        self.assertEqual(response.status_code, 200)
        performance_data = list(response.context["performance_data"])
        alice_data = next(item for item in performance_data if item["staff"] == self.staff_one)

        self.assertEqual(alice_data["completed_tasks"], 2)
        self.assertEqual(alice_data["on_time_completed"], 2)

    def test_self_tasks_are_included_in_shared_dashboard_counts(self):
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
        performance_data = list(response.context["performance_data"])
        alice_data = next(item for item in performance_data if item["staff"] == self.staff_one)
        self.assertEqual(alice_data["total_tasks"], 2)
        self.assertEqual(alice_data["completed_tasks"], 2)

    def test_staff_detail_shows_task_descriptions_for_all_and_manager_tasks(self):
        self.client.force_login(self.manager)

        self_task = Task.objects.create(
            title="Personal follow-up",
            description="Staff created this task for own follow-up",
            due_date=timezone.localdate() + timedelta(days=1),
            priority="normal",
        )
        UserTask.objects.create(
            task=self_task,
            assigned_by=self.staff_one,
            assigned_to=self.staff_one,
            status="pending",
        )

        response = self.client.get(reverse("staff_detail", args=[self.staff_one.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Staff created this task for own follow-up")
        self.assertContains(response, "Prepare weekly report")

    def test_staff_detail_separates_own_tasks_from_manager_tasks(self):
        self.client.force_login(self.manager)

        own_task = Task.objects.create(
            title="Personal follow-up",
            description="Staff self-created item",
            due_date=timezone.localdate() + timedelta(days=1),
            priority="normal",
        )
        UserTask.objects.create(
            task=own_task,
            assigned_by=self.staff_one,
            assigned_to=self.staff_one,
            status="pending",
        )

        response = self.client.get(reverse("staff_detail", args=[self.staff_one.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["all_tasks"].values_list("task__title", flat=True)), ["Personal follow-up"])
        self.assertEqual(list(response.context["manager_tasks"].values_list("task__title", flat=True)), ["Prepare weekly report"])

    def test_staff_detail_keeps_in_progress_out_of_pending_count(self):
        self.client.force_login(self.manager)

        task = Task.objects.create(
            title="Review filed updates",
            description="",
            due_date=timezone.localdate() + timedelta(days=1),
            priority="normal",
        )
        UserTask.objects.create(
            task=task,
            assigned_by=self.manager,
            assigned_to=self.staff_one,
            status="in_progress",
        )

        response = self.client.get(reverse("staff_detail", args=[self.staff_one.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pending_count"], 0)
        self.assertEqual(response.context["in_progress_count"], 1)

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


class TaskWorkspaceSelectionTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="StrongPass123!",
            section="ict",
            role="manager",
        )
        self.staff = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="StrongPass123!",
            section="ict",
            role="staff",
        )

        self.my_task = Task.objects.create(
            title="My own task",
            description="Own description",
            due_date=timezone.localdate() + timedelta(days=2),
            priority="normal",
        )
        UserTask.objects.create(
            task=self.my_task,
            assigned_by=self.manager,
            assigned_to=self.manager,
            status="pending",
        )

        self.assigned_task = Task.objects.create(
            title="Assigned task",
            description="Assigned description",
            due_date=timezone.localdate() + timedelta(days=3),
            priority="normal",
        )
        UserTask.objects.create(
            task=self.assigned_task,
            assigned_by=self.manager,
            assigned_to=self.staff,
            status="pending",
        )

    def test_my_tasks_page_loads_selected_task_panel_context(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("my_tasks"), {"selected": self.my_task.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_task_id"], self.my_task.id)
        self.assertEqual(response.context["selected_task_context"]["task"], self.my_task)
        self.assertContains(response, "Task Detail")

    def test_assigned_tasks_page_loads_selected_task_panel_context(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("assigned_tasks"), {"selected": self.assigned_task.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_task_id"], self.assigned_task.id)
        self.assertEqual(response.context["selected_task_context"]["task"], self.assigned_task)
        self.assertContains(response, "Task Detail")

    def test_task_detail_panel_endpoint_returns_partial_for_authorized_user(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("task_detail_panel", args=[self.assigned_task.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.assigned_task.title)
        self.assertContains(response, "Task Detail")

    def test_task_detail_panel_shows_completed_delivery_for_manager_view(self):
        UserTask.objects.filter(task=self.assigned_task).update(status="completed")
        self.client.force_login(self.manager)

        response = self.client.get(reverse("task_detail_panel", args=[self.assigned_task.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Completed")


class PersonalTaskCategorySetupTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="activity_owner",
            email="activity_owner@nhc.co.tz",
            password="StrongPass123!",
            section="ict",
            role="staff",
        )

    def test_user_can_create_personal_task_category_from_setup_page(self):
        self.client.force_login(self.staff)

        response = self.client.post(reverse("task_category_setup"), {"name": "Correspondence"}, follow=True)

        self.assertEqual(response.status_code, 200)
        category = Category.objects.get(name="Correspondence")
        self.assertEqual(category.created_by, self.staff)
        self.assertContains(response, "Task category saved successfully")

    def test_my_tasks_page_shows_only_current_users_personal_categories(self):
        own_category = Category.objects.create(name="Reports", section="ict", created_by=self.staff)
        other_user = User.objects.create_user(
            username="other_owner",
            email="other_owner@nhc.co.tz",
            password="StrongPass123!",
            section="ict",
            role="staff",
        )
        Category.objects.create(name="Travel", section="ict", created_by=other_user)

        self.client.force_login(self.staff)
        response = self.client.get(reverse("my_tasks"))

        self.assertEqual(response.status_code, 200)
        categories = list(response.context["activity_categories"])
        self.assertEqual(categories, [own_category])
        self.assertContains(response, "Reports")
        self.assertNotContains(response, "Travel")


class CreateActivityWithPersonalCategoryTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="activity_staff",
            email="activity_staff@nhc.co.tz",
            password="StrongPass123!",
            section="ict",
            role="staff",
        )
        self.personal_category = Category.objects.create(
            name="Meetings",
            section="ict",
            created_by=self.staff,
        )

    def test_self_activity_creation_requires_personal_category(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("create_task"),
            {
                "description": "Weekly planning session",
                "due_date": timezone.localdate().isoformat(),
                "priority": "normal",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"error": "Please select a valid activity category."})

    def test_self_activity_creation_uses_users_personal_category(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("create_task"),
            {
                "description": "Weekly planning session",
                "due_date": timezone.localdate().isoformat(),
                "priority": "normal",
                "category_id": str(self.personal_category.id),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        created_task = Task.objects.get(description="Weekly planning session")
        self.assertEqual(created_task.category, self.personal_category)
        self.assertEqual(created_task.title, "Weekly planning session")
        self.assertTrue(
            UserTask.objects.filter(
                task=created_task,
                assigned_by=self.staff,
                assigned_to=self.staff,
            ).exists()
        )


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


class DashboardRecentTasksTests(TestCase):
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
            email="alice@nhc.co.tz",
            password="StrongPass123!",
            section="ict",
            role="staff",
        )

    def test_staff_recent_tasks_marks_overdue_assignment_as_returned_to_manager(self):
        task = Task.objects.create(
            title="Old assigned task",
            description="",
            due_date=timezone.localdate() - timedelta(days=2),
            priority="normal",
        )
        UserTask.objects.create(
            task=task,
            assigned_by=self.manager,
            assigned_to=self.staff,
            status="pending",
            review_status="pending",
        )

        self.client.force_login(self.staff)
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        recent_item = response.context["recent_tasks"][0]
        self.assertEqual(recent_item["display_status_key"], "awaiting_reassignment")
        self.assertEqual(recent_item["display_status_label"], "Returned to Manager")
        self.assertContains(response, "Returned to Manager")

    def test_manager_recent_tasks_marks_overdue_assignment_as_needs_reassignment(self):
        task = Task.objects.create(
            title="Old staff task",
            description="",
            due_date=timezone.localdate() - timedelta(days=2),
            priority="high",
        )
        UserTask.objects.create(
            task=task,
            assigned_by=self.manager,
            assigned_to=self.staff,
            status="in_progress",
            review_status="pending",
        )

        self.client.force_login(self.manager)
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        recent_item = response.context["recent_tasks"][0]
        self.assertEqual(recent_item["display_status_key"], "needs_reassignment")
        self.assertEqual(recent_item["display_status_label"], "Needs Reassignment")
        self.assertContains(response, "Needs Reassignment")

    def test_reassigned_overdue_task_returns_to_normal_recent_task_status(self):
        task = Task.objects.create(
            title="Reassigned overdue task",
            description="",
            due_date=timezone.localdate() - timedelta(days=2),
            priority="high",
        )
        user_task = UserTask.objects.create(
            task=task,
            assigned_by=self.manager,
            assigned_to=self.staff,
            status="pending",
            review_status="pending",
            reassigned_at=timezone.now(),
        )

        self.client.force_login(self.staff)
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        recent_item = response.context["recent_tasks"][0]
        self.assertEqual(recent_item["display_status_key"], user_task.status)
        self.assertEqual(recent_item["display_status_label"], user_task.get_status_display())
        self.assertFalse(recent_item["waiting_reassignment"])
        self.assertNotContains(response, "Returned to Manager")


@override_settings(
    NOTIFICATION_EMAILS_ENABLED=True,
    NOTIFICATION_EMAIL_ALLOWED_DOMAIN="nhc.co.tz",
    EMAIL_HOST_USER="smtp-user@nhc.co.tz",
    EMAIL_HOST_PASSWORD="secret",
)
class NotificationEmailDeliveryRulesTests(TestCase):
    def test_notification_email_is_skipped_for_non_nhc_recipient(self):
        user = User.objects.create_user(
            username="externaluser",
            email="external@example.com",
            password="StrongPass123!",
            section="ict",
            role="staff",
        )
        notification = Notification.objects.create(
            user=user,
            title="Task updated",
            message="A task changed.",
            notification_type="task_updated",
        )

        with patch("tasks.notifications.send_mail") as mock_send_mail:
            send_notification_email(notification)

        mock_send_mail.assert_not_called()

    def test_notification_email_uses_default_from_email_for_nhc_recipient(self):
        user = User.objects.create_user(
            username="internaluser",
            email="internal@nhc.co.tz",
            password="StrongPass123!",
            section="ict",
            role="staff",
        )
        notification = Notification.objects.create(
            user=user,
            title="Task assigned",
            message="You have a new task.",
            notification_type="task_assigned",
        )

        with override_settings(DEFAULT_FROM_EMAIL="ictsupport@nhc.co.tz"):
            with patch("tasks.notifications.send_mail") as mock_send_mail:
                send_notification_email(notification)

        mock_send_mail.assert_called_once_with(
            subject="Task assigned",
            message=ANY,
            from_email="ictsupport@nhc.co.tz",
            recipient_list=["internal@nhc.co.tz"],
            fail_silently=False,
        )


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

    def test_reassigned_task_is_marked_as_returned_to_staff_workflow(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("reassign_task", args=[self.task.id]),
            {
                "category_id": str(self.category.id),
                "assigned_to": str(self.staff_two.id),
            },
        )

        self.assertEqual(response.status_code, 302)
        user_task = UserTask.objects.get(task=self.task, assigned_to=self.staff_two)
        self.assertIsNotNone(user_task.reassigned_at)

    def test_category_users_json_only_returns_staff_from_manager_section(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("category_users_json"),
            {"category_id": self.other_category.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["users"], [])


class SubTaskCreationTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="subtask_owner",
            email="subtask_owner@example.com",
            password="StrongPass123!",
            section="ict",
            role="staff",
            staff_type="senior",
        )
        self.task = Task.objects.create(
            title="Prepare router checklist",
            description="",
            due_date=timezone.localdate() + timedelta(days=2),
            priority="normal",
        )
        UserTask.objects.create(
            task=self.task,
            assigned_by=self.staff,
            assigned_to=self.staff,
            status="pending",
        )

    def test_new_subtask_defaults_to_in_progress(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("ajax_save_subtask", args=[self.task.id]),
            {
                "description": "Start with the uplink status",
            },
        )

        self.assertEqual(response.status_code, 200)
        subtask = SubTask.objects.get(task=self.task)
        self.assertEqual(subtask.description, "Start with the uplink status")
        self.assertEqual(subtask.title, "Start with the uplink status")
        self.assertEqual(subtask.status, "in_progress")
