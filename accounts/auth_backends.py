import os

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

try:
    from ldap3 import ALL, Connection, Server
    from ldap3.core.exceptions import LDAPException
    from ldap3.utils.conv import escape_filter_chars
except ImportError:  # pragma: no cover - handled at runtime if dependency is missing
    ALL = Connection = Server = LDAPException = None

    def escape_filter_chars(value):
        return value


UserModel = get_user_model()


class ActiveDirectoryBackend(BaseBackend):
    """
    Authenticate users against Active Directory and then map them to the
    project's local User model so role/section permissions still work.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        username = (username or "").strip()
        password = password or ""

        if not username or not password:
            self._set_request_error(request, "Username and password are required.")
            return None

        if Connection is None:
            self._set_request_error(
                request,
                "Active Directory login is not available because the LDAP library is not installed.",
            )
            return None

        settings = self._load_settings()
        required_keys = [
            "server_uri",
            "port",
            "base_dn",
            "bind_user",
            "bind_password",
            "username_attr",
            "timeout",
        ]
        missing = [key for key in required_keys if not settings.get(key)]
        if missing:
            self._set_request_error(
                request,
                "Active Directory login is not configured on this server.",
            )
            return None

        service_conn = None
        user_conn = None

        try:
            server = Server(
                settings["server_uri"],
                port=int(settings["port"]),
                get_info=ALL,
            )

            service_conn = Connection(
                server,
                user=settings["bind_user"],
                password=settings["bind_password"],
                auto_bind=True,
                receive_timeout=int(settings["timeout"]),
            )

            safe_username = escape_filter_chars(username)
            search_filter = f"({settings['username_attr']}={safe_username})"

            found = service_conn.search(
                search_base=settings["base_dn"],
                search_filter=search_filter,
                attributes=["distinguishedName", "mail", "userPrincipalName"],
                size_limit=1,
            )
            if not found or not service_conn.entries:
                self._set_request_error(request, "User not found in Active Directory.")
                return None

            entry = service_conn.entries[0]
            user_dn = entry.entry_dn

            user_conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
                receive_timeout=int(settings["timeout"]),
            )

            if not user_conn.bound:
                self._set_request_error(request, "Invalid username or password.")
                return None

            email = self._pick_email(entry, username, settings["email_domain"])
            user = self._get_or_build_local_user(username=username, email=email, settings=settings)
            if not user:
                self._set_request_error(
                    request,
                    "Your account is valid in Active Directory but is not registered in this system. Contact ICT/Admin.",
                )
                return None

            if not user.is_active:
                self._set_request_error(request, "This account is inactive.")
                return None

            updated_fields = []
            if email and user.email != email:
                user.email = email
                updated_fields.append("email")

            if updated_fields:
                user.save(update_fields=updated_fields)

            self._clear_request_error(request)
            return user

        except LDAPException:
            self._set_request_error(
                request,
                "Could not connect to Active Directory. Please try again or contact ICT.",
            )
            return None
        except Exception:
            self._set_request_error(
                request,
                "Active Directory authentication failed. Please contact ICT.",
            )
            return None
        finally:
            if user_conn is not None:
                user_conn.unbind()
            if service_conn is not None:
                service_conn.unbind()

    def get_user(self, user_id):
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None

    def _get_or_build_local_user(self, *, username, email, settings):
        try:
            return UserModel.objects.get(username__iexact=username)
        except UserModel.DoesNotExist:
            if not settings["auto_create"]:
                return None

            user = UserModel(
                username=username,
                email=email or f"{username}@{settings['email_domain']}",
                section=settings["default_section"],
                role=settings["default_role"],
                is_active=True,
            )
            user.set_unusable_password()
            user.save()
            return user

    def _pick_email(self, entry, username, email_domain):
        mail = getattr(entry, "mail", None)
        if mail and mail.value:
            return mail.value

        upn = getattr(entry, "userPrincipalName", None)
        if upn and upn.value:
            return upn.value

        return f"{username}@{email_domain}"

    def _load_settings(self):
        return {
            "server_uri": os.environ.get("AD_SERVER_URI", "ldap://nhctz.com"),
            "port": os.environ.get("AD_PORT", "389"),
            "base_dn": os.environ.get("AD_BASE_DN", "DC=nhctz,DC=com"),
            "bind_user": os.environ.get("AD_BIND_USER", ""),
            "bind_password": os.environ.get("AD_BIND_PASSWORD", ""),
            "username_attr": os.environ.get("AD_USERNAME_ATTR", "sAMAccountName"),
            "timeout": os.environ.get("AD_TIMEOUT", "10"),
            "auto_create": os.environ.get("AD_AUTO_CREATE_USERS", "False").lower() == "true",
            "default_section": os.environ.get("AD_DEFAULT_SECTION", ""),
            "default_role": os.environ.get("AD_DEFAULT_ROLE", "staff"),
            "email_domain": os.environ.get("AD_EMAIL_DOMAIN", "nhctz.com"),
        }

    def _set_request_error(self, request, message):
        if request is not None:
            request.ad_auth_error = message

    def _clear_request_error(self, request):
        if request is not None and hasattr(request, "ad_auth_error"):
            delattr(request, "ad_auth_error")


class LocalSuperuserBackend(BaseBackend):
    """
    Allow Django-local password login only for superusers so the admin
    account is not locked out. All normal users must pass through AD.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        username = (username or "").strip()
        password = password or ""

        if not username or not password:
            return None

        try:
            user = UserModel.objects.get(username__iexact=username)
        except UserModel.DoesNotExist:
            return None

        if not user.is_superuser:
            return None

        if not user.is_active:
            if request is not None:
                request.ad_auth_error = "This account is inactive."
            return None

        if user.check_password(password):
            return user

        return None

    def get_user(self, user_id):
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
