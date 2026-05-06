import ssl

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPEmailBackend
from django.utils.functional import cached_property


class EmailBackend(DjangoSMTPEmailBackend):
    @cached_property
    def ssl_context(self):
        ssl_context = ssl.create_default_context()

        certfile = getattr(settings, "EMAIL_SSL_CERTFILE", None)
        keyfile = getattr(settings, "EMAIL_SSL_KEYFILE", None)
        ca_cert_path = getattr(settings, "EMAIL_TLS_CA_CERT_PATH", "").strip()
        validate_certs = getattr(settings, "EMAIL_VALIDATE_CERTS", True)

        if certfile or keyfile:
            ssl_context.load_cert_chain(certfile, keyfile)

        if ca_cert_path:
            ssl_context.load_verify_locations(cafile=ca_cert_path)

        if not validate_certs:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        return ssl_context
