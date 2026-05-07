from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .models import UserSession


class SessionSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        redirect_response = self._process_request(request)
        if redirect_response is not None:
            return self._add_no_cache_headers(redirect_response)

        response = self.get_response(request)
        return self._add_no_cache_headers(response)

    def _process_request(self, request):
        if self._is_admin_request(request):
            return None

        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return None

        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key

        timeout_seconds = getattr(settings, "SESSION_IDLE_TIMEOUT_SECONDS", 1800)
        touch_interval_seconds = getattr(settings, "USER_SESSION_TOUCH_INTERVAL_SECONDS", 300)
        track_user_sessions = getattr(settings, "ENABLE_USER_SESSION_TRACKING", False)
        now_ts = int(timezone.now().timestamp())
        last_activity_ts = request.session.get("last_activity_ts")

        if timeout_seconds > 0 and last_activity_ts and (now_ts - int(last_activity_ts) > timeout_seconds):
            if track_user_sessions:
                UserSession.objects.filter(
                    user=request.user,
                    session_key=session_key,
                ).delete()
            logout(request)
            self._warn(
                request,
                "You were logged out because your session was idle for too long.",
            )
            return redirect(settings.LOGIN_URL)

        request.session["last_activity_ts"] = now_ts
        last_touch_ts = int(request.session.get("user_session_touch_ts", 0) or 0)
        if track_user_sessions and (
            now_ts - last_touch_ts >= touch_interval_seconds
        ):
            UserSession.objects.update_or_create(
                user=request.user,
                defaults={"session_key": session_key},
            )
            request.session["user_session_touch_ts"] = now_ts
        return None

    def _warn(self, request, message):
        # Keep session protection from turning into a 500 if message middleware
        # is missing or misordered in a future config change.
        messages.warning(request, message, fail_silently=True)

    def _is_admin_request(self, request):
        admin_prefix = f"/{getattr(settings, 'ADMIN_URL_PREFIX', 'admin/')}"
        return request.path.startswith(admin_prefix)

    def _add_no_cache_headers(self, response):
        response["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response


class AssignmentRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_redirect_to_dashboard(request):
            return redirect("dashboard")

        return self.get_response(request)

    def _should_redirect_to_dashboard(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or not getattr(user, "needs_assignment", False):
            return False

        if self._is_admin_request(request):
            return False

        allowed_paths = {
            reverse("dashboard"),
            reverse("logout"),
        }
        return request.path not in allowed_paths

    def _is_admin_request(self, request):
        admin_prefix = f"/{getattr(settings, 'ADMIN_URL_PREFIX', 'admin/')}"
        return request.path.startswith(admin_prefix)
