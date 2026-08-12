"""
Butun /api/ chagirislarini yungul sekilde loglayir (path, method, status, user, ip).
Hessas emeliyyatlarin ozunun detalli AuditLog qeydi views-de authentication.utils.log_security_event
ile yaradilir - bu middleware elave, umumi bir 'kim ne vaxt hansi endpointi chagirdi' izidir.
"""


class RequestAuditMiddleware:
    SENSITIVE_PREFIXES = ("/api/auth/", "/api/permissions/", "/api/organizations/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path.startswith(self.SENSITIVE_PREFIXES) and request.method != "GET":
            try:
                from .models import AuditLog
                from authentication.utils import get_client_ip

                user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
                AuditLog.objects.create(
                    user=user,
                    action="HTTP_REQUEST",
                    ip_address=get_client_ip(request) or None,
                    path=request.path,
                    method=request.method,
                    status_code=response.status_code,
                )
            except Exception:
                pass

        return response
