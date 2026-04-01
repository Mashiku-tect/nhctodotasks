from .notifications import sync_in_app_notifications_for_user


def notification_data(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'header_notifications': [],
            'unread_notifications_count': 0,
        }

    sync_in_app_notifications_for_user(request.user)
    notifications = request.user.notifications.select_related('task')[:6]
    unread_count = request.user.notifications.filter(is_read=False).count()

    return {
        'header_notifications': notifications,
        'unread_notifications_count': unread_count,
    }
