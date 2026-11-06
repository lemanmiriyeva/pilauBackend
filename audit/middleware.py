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
        # Operator jurnalı üçün JSON gövdəsini view-dan ƏVVƏL oxuyuruq (Django onu keşləyir, DRF sonra da oxuya bilir).
        body_bytes = None
        try:
            from .operator_log import LOGGED_PREFIXES, MAX_BODY_BYTES, SAFE_METHODS
            if (request.method not in SAFE_METHODS and request.path.startswith(LOGGED_PREFIXES)
                    and request.META.get("CONTENT_TYPE", "").startswith("application/json")
                    and int(request.META.get("CONTENT_LENGTH") or 0) <= MAX_BODY_BYTES):
                body_bytes = request.body
        except Exception:
            body_bytes = None

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

        # MSN operatorlarının fəaliyyət jurnalı (bax audit/operator_log.py)
        try:
            from .operator_log import log_operator_request
            log_operator_request(request, response, body_bytes)
        except Exception:
            pass

        return response