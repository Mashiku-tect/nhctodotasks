from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
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
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return None

        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key

        timeout_seconds = getattr(settings, "SESSION_IDLE_TIMEOUT_SECONDS", 1800)
        now_ts = int(timezone.now().timestamp())
        last_activity_ts = request.session.get("last_activity_ts")

        if last_activity_ts and (now_ts - int(last_activity_ts) > timeout_seconds):
            UserSession.objects.filter(
                user=request.user,
                session_key=session_key,
            ).delete()
            logout(request)
            messages.warning(request, "You were logged out because your session was idle for too long.")
            return redirect(settings.LOGIN_URL)

        active_session = UserSession.objects.filter(user=request.user).first()
        if active_session and active_session.session_key != session_key:
            logout(request)
            messages.warning(
                request,
                "Your account was signed in from another browser or device. This session has been closed.",
            )
            return redirect(settings.LOGIN_URL)

        request.session["last_activity_ts"] = now_ts
        UserSession.objects.update_or_create(
            user=request.user,
            defaults={"session_key": session_key},
        )
        return None

    def _add_no_cache_headers(self, response):
        response["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response
