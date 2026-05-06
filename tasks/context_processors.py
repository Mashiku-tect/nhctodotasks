from django.conf import settings
from django.utils import timezone

from .notifications import sync_in_app_notifications_for_user


def _should_sync_notifications(request):
    sync_interval_seconds = getattr(settings, "NOTIFICATION_SYNC_INTERVAL_SECONDS", 300)
    if sync_interval_seconds <= 0:
        return True

    now_ts = int(timezone.now().timestamp())
    last_sync_ts = int(request.session.get("notification_sync_ts", 0) or 0)

    if now_ts - last_sync_ts < sync_interval_seconds:
        return False

    request.session["notification_sync_ts"] = now_ts
    return True


def notification_data(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'header_notifications': [],
            'unread_notifications_count': 0,
        }

    if _should_sync_notifications(request):
        sync_in_app_notifications_for_user(request.user)
    notifications = request.user.notifications.select_related('task')[:6]
    unread_count = request.user.notifications.filter(is_read=False).count()

    return {
        'header_notifications': notifications,
        'unread_notifications_count': unread_count,
    }
