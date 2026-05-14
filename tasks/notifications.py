import logging
import threading
from datetime import timedelta

import pytz
from django.conf import settings
from django.db import transaction
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from .models import Notification, UserTask


TANZANIA_TZ = pytz.timezone("Africa/Dar_es_Salaam")
DUE_SOON_WINDOW_DAYS = 2
REVIEW_DELAY_DAYS = 2
logger = logging.getLogger(__name__)


def local_today():
    return timezone.now().astimezone(TANZANIA_TZ).date()


def create_notification(*, user, title, message, notification_type, task=None, target_url=""):
    notification = Notification.objects.create(
        user=user,
        task=task,
        title=title,
        message=message,
        notification_type=notification_type,
        target_url=target_url,
    )

    def queue_email():
        email_thread = threading.Thread(
            target=send_notification_email,
            args=(notification,),
            daemon=True,
        )
        email_thread.start()

    transaction.on_commit(queue_email)
    return notification


def build_notification_email_body(notification):
    lines = [
        f"Hello {notification.user.username},",
        "",
        notification.title,
        notification.message,
    ]

    if notification.task:
        lines.extend([
            "",
            f"Task: {notification.task.title}",
            f"Due date: {notification.task.due_date}",
        ])

    if notification.target_url:
        full_url = build_absolute_notification_url(notification.target_url)
        if full_url:
            lines.extend([
                "",
                f"Open in system: {full_url}",
            ])

    lines.extend([
        "",
        "This email was sent automatically by NHC To Do Tasks.",
    ])
    return "\n".join(lines)


def build_absolute_notification_url(target_url):
    if not target_url:
        return ""
    if target_url.startswith("http://") or target_url.startswith("https://"):
        return target_url
    if not settings.DJANGO_SITE_BASE_URL:
        return target_url
    if target_url.startswith("/"):
        return f"{settings.DJANGO_SITE_BASE_URL}{target_url}"
    return f"{settings.DJANGO_SITE_BASE_URL}/{target_url}"


def send_notification_email(notification):
    if not settings.NOTIFICATION_EMAILS_ENABLED:
        return

    recipient_email = (getattr(notification.user, "email", "") or "").strip().lower()
    if not recipient_email:
        return

    allowed_domain = getattr(settings, "NOTIFICATION_EMAIL_ALLOWED_DOMAIN", "").strip().lower()
    if allowed_domain and not recipient_email.endswith(f"@{allowed_domain}"):
        logger.info(
            "Notification email skipped for notification_id=%s because recipient domain is not allowed: %s",
            notification.id,
            recipient_email,
        )
        return

    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.warning(
            "Notification email skipped because EMAIL_HOST_USER or EMAIL_HOST_PASSWORD is missing."
        )
        return

    try:
        send_mail(
            subject=notification.title,
            message=build_notification_email_body(notification),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Failed to send notification email for notification_id=%s to user_id=%s",
            notification.id,
            notification.user_id,
        )


def create_notification_once_per_day(
    *, user, title, message, notification_type, task=None, target_url=""
):
    today = local_today()
    exists = Notification.objects.filter(
        user=user,
        task=task,
        notification_type=notification_type,
        created_at__date=today,
    ).exists()
    if exists:
        return

    create_notification(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        task=task,
        target_url=target_url,
    )


def sync_in_app_notifications_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return

    today = local_today()

    if user.role == "staff":
        _sync_staff_notifications(user, today)

    if user.role == "manager" or user.is_superuser:
        _sync_manager_notifications(user, today)


def _sync_staff_notifications(user, today):
    open_assigned_tasks = (
        UserTask.objects.filter(assigned_to=user)
        .exclude(assigned_by=user)
        .exclude(status__in=["completed", "rejected"])
        .select_related("task", "assigned_by")
    )

    due_soon_cutoff = today + timedelta(days=DUE_SOON_WINDOW_DAYS)
    due_soon_tasks = open_assigned_tasks.filter(
        task__due_date__gte=today,
        task__due_date__lte=due_soon_cutoff,
    )
    for user_task in due_soon_tasks:
        days_left = (user_task.task.due_date - today).days
        if days_left == 0:
            timing = "today"
        elif days_left == 1:
            timing = "tomorrow"
        else:
            timing = f"in {days_left} days"

        create_notification_once_per_day(
            user=user,
            title="Task due soon",
            message=f'"{user_task.task.title}" is due {timing}.',
            notification_type="task_due_soon",
            task=user_task.task,
            target_url=reverse("task_detail", args=[user_task.task.id]),
        )

    overdue_tasks = open_assigned_tasks.filter(task__due_date__lt=today)
    for user_task in overdue_tasks:
        create_notification_once_per_day(
            user=user,
            title="Task overdue",
            message=f'"{user_task.task.title}" is overdue and needs attention.',
            notification_type="task_overdue",
            task=user_task.task,
            target_url=reverse("task_detail", args=[user_task.task.id]),
        )


def _sync_manager_notifications(user, today):
    assigned_tasks = (
        UserTask.objects.filter(assigned_by=user)
        .exclude(assigned_to=user)
        .select_related("task", "assigned_to")
    )

    overdue_tasks = assigned_tasks.filter(task__due_date__lt=today).exclude(
        status__in=["completed", "rejected"]
    )
    for user_task in overdue_tasks:
        create_notification_once_per_day(
            user=user,
            title="Assigned task overdue",
            message=(
                f'"{user_task.task.title}" assigned to '
                f"{user_task.assigned_to.username} is overdue."
            ),
            notification_type="assigned_task_overdue",
            task=user_task.task,
            target_url=reverse("task_detail", args=[user_task.task.id]),
        )

    review_delay_cutoff = today - timedelta(days=REVIEW_DELAY_DAYS)
    review_delay_tasks = assigned_tasks.filter(
        status="completed",
        review_status="pending",
        completed_at__date__lte=review_delay_cutoff,
    )
    for user_task in review_delay_tasks:
        create_notification_once_per_day(
            user=user,
            title="Review pending too long",
            message=(
                f'"{user_task.task.title}" has been waiting for review since '
                f"{user_task.completed_at.astimezone(TANZANIA_TZ).date()}."
            ),
            notification_type="task_review_delay",
            task=user_task.task,
            target_url=reverse("review_task", args=[user_task.task.id]),
        )
