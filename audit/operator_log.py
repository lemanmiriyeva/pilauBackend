"""MSN operatorlarının fəaliyyət jurnalı.

Operatorun /api/licenses/ və /api/organizations/ (təşkilat, nomenklatura, sənədlər...) altındakı
sorğuları oxunaqlı 'fəaliyyət' qeydinə çevrilir:
  - dəyişdirən sorğular (POST/PUT/PATCH/DELETE) həmişə yazılır (uğursuz cəhdlər də, status kodu ilə);
  - baxış (GET) yalnız konkret obyektə (yolunda nömrə olan) yazılır, siyahı sorğuları yox;
    eyni obyektə 5 dəqiqə ərzində təkrar baxış bir dəfə yazılır (səs-küyün qarşısı).
Sorğu gövdəsi (JSON) həssas açarlar maskalanaraq 'detail'-də saxlanılır. Fayl yükləmələrinin
(multipart) məzmunu yazılmır.
"""
import json
import re
from datetime import timedelta

from django.utils import timezone

LOGGED_PREFIXES = ("/api/licenses/", "/api/organizations/")
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
GET_DEDUP_MINUTES = 5
MAX_BODY_BYTES = 20000
MAX_DETAIL_CHARS = 2500
SENSITIVE_KEYS = ("password", "token", "otp", "secret", "code", "pin")

RE_PERMIT = re.compile(r"^/api/licenses/permit-documents/(?:(?P<id>\d+)/(?:(?P<sub>[a-z\-]+)/)?)?$")
RE_CERT = re.compile(r"^/api/licenses/certificates/(?:(?P<id>\d+)/(?:(?P<sub>[a-z\-]+)/)?)?$")
RE_ORG_ITEM = re.compile(
    r"^/api/organizations/(?P<res>nomenclature|equipment|subordinates|activity-documents)/(?P<id>\d+)/(?:(?P<sub>[a-z\-]+)/)?$"
)
RE_ORG_SUB = re.compile(
    r"^/api/organizations/(?P<org>\d+)/(?:(?P<res>[a-z\-]+)/)?(?:(?P<sid>\d+)/)?(?:(?P<sub>[a-z\-]+)/)?$"
)

ORG_RESOURCE_LABELS = {
    "profile": "Təşkilat profili", "employees": "İşçilər", "nomenclature": "Nomenklatura",
    "permit-documents": "İcazə sənədləri", "turnover": "Dövriyyə", "activity-documents": "Fəaliyyət sənədləri",
    "subordinates": "Tabeliyindəkilər", "equipment": "Texnika / avadanlıq", "module-access": "Modul girişi",
    "approval-flow": "Təsdiq axını",
}
VERBS = {"GET": "baxdı", "POST": "əlavə etdi", "PUT": "dəyişdi", "PATCH": "dəyişdi", "DELETE": "sildi"}


def classify(method: str, path: str, body: dict, response_data) -> dict | None:
    """Sorğunu (obyekt növü, id, təşkilat, əməliyyat kodu, etiket) formasına salır; tanınmırsa None."""
    verb = VERBS.get(method, method.lower())

    m = RE_PERMIT.match(path)
    if m:
        sub = m.group("sub") or ""
        doc_id = int(m.group("id")) if m.group("id") else None
        if doc_id is None and method == "POST":
            code, label = "permit.create", "Yeni sənəd yaratdı"
        elif sub == "approve":
            code, label = "permit.approve", "Sənədi təsdiq etdi"
        elif sub == "reject":
            code, label = "permit.reject", "Sənədi rədd etdi"
        elif sub == "operator-review":
            decision = (body or {}).get("decision")
            code = "permit.operator_review"
            label = {"ugurlu": "Sənədi yoxladı: uğurlu", "imtina": "Sənədi yoxladı: imtina"}.get(decision, "Sənədi yoxladı")
        elif sub == "upload-files":
            code, label = "permit.upload_files", "Sənədə fayl yüklədi"
        elif sub:
            code, label = f"permit.{sub}", f"Sənəd ({sub}): {verb}"
        else:
            code, label = f"permit.{method.lower()}", f"Sənədə {verb}" if method == "GET" else f"Sənədi {verb}"
        if doc_id is None and isinstance(response_data, dict):
            doc_id = response_data.get("id")
        return {"object_type": "permit_document", "object_id": doc_id, "org_id": None, "code": code, "label": label}

    m = RE_CERT.match(path)
    if m:
        sub = m.group("sub") or ""
        cid = int(m.group("id")) if m.group("id") else None
        return {"object_type": "certificate", "object_id": cid, "org_id": None,
                "code": f"certificate.{sub or method.lower()}",
                "label": f"Sertifikat{' (' + sub + ')' if sub else ''}: {verb}"}

    m = RE_ORG_ITEM.match(path)
    if m:
        res, sub = m.group("res"), m.group("sub") or ""
        rlabel = ORG_RESOURCE_LABELS.get(res, res)
        otype = "nomenclature" if res == "nomenclature" else "organization"
        extra = " (endirdi)" if sub == "download" else (f" ({sub})" if sub else "")
        return {"object_type": otype, "object_id": int(m.group("id")), "org_id": None,
                "code": f"{res}.{sub or method.lower()}", "label": f"{rlabel} qeydi{extra}: {'endirdi' if sub == 'download' else verb}"}

    m = RE_ORG_SUB.match(path)
    if m:
        res, sub = m.group("res") or "", m.group("sub") or ""
        org_id = int(m.group("org"))
        if res == "nomenclature":
            otype, rlabel = "nomenclature", "Nomenklatura"
        else:
            otype, rlabel = "organization", ORG_RESOURCE_LABELS.get(res, res) if res else "Təşkilat"
        sid = int(m.group("sid")) if m.group("sid") else None
        if not res:
            label = f"Təşkilat məlumatlarına {verb}" if method == "GET" else f"Təşkilat məlumatlarını {verb}"
            code = f"organization.{method.lower()}"
        else:
            label = f"{rlabel}{' (' + sub + ')' if sub else ''}: {verb}"
            code = f"{res}.{sub or method.lower()}"
        # Nomenklatura siyahısı (konkret qeyd yox): object_id boş, təşkilat 'organization' sahəsindədir
        return {"object_type": otype, "object_id": sid if otype == "nomenclature" else org_id,
                "org_id": org_id, "code": code, "label": label}
    return None


def _redact(value, depth=0):
    if depth > 4:
        return "..."
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if any(s in str(k).lower() for s in SENSITIVE_KEYS):
                out[k] = "***"
            else:
                out[k] = _redact(v, depth + 1)
        return out
    if isinstance(value, list):
        return [_redact(v, depth + 1) for v in value[:30]]
    if isinstance(value, str) and len(value) > 300:
        return value[:300] + "..."
    return value


def _parse_body(body_bytes):
    if not body_bytes:
        return {}
    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {"_list": data}


def _object_info(info: dict) -> tuple:
    """(object_label, organization_id) - bazadan oxunaqlı ad tapır (alınmasa boş)."""
    otype, oid, org_id = info["object_type"], info["object_id"], info["org_id"]
    label = ""
    try:
        if otype == "permit_document" and oid:
            from licenses.models import PermitDocument
            d = PermitDocument.objects.filter(pk=oid).only("number", "doc_type", "organization_id").first()
            if d:
                label, org_id = f"{d.get_doc_type_display()} № {d.number}", d.organization_id
        elif otype == "certificate" and oid:
            from licenses.models import LicenseCertificate
            c = LicenseCertificate.objects.filter(pk=oid).select_related("permit_document").first()
            if c:
                label, org_id = f"Sertifikat № {c.number}", c.permit_document.organization_id
        elif otype == "nomenclature" and oid:
            from organizations.models import OrganizationNomenclature
            n = OrganizationNomenclature.objects.filter(pk=oid).first()
            if n:
                label, org_id = str(n), n.organization_id
        elif otype == "nomenclature" and org_id:
            from organizations.models import Organization
            o = Organization.objects.filter(pk=org_id).only("full_name").first()
            if o:
                label = f"Nomenklatura - {o.full_name}"
        elif otype == "organization" and (org_id or oid):
            from organizations.models import Organization
            o = Organization.objects.filter(pk=org_id or oid).only("full_name").first()
            if o:
                label, org_id = o.full_name, o.pk
    except Exception:
        pass
    return label[:255], org_id


def log_operator_request(request, response, body_bytes):
    """Middleware-dən çağırılır. Operator deyilsə və ya sorğu tanınmırsa heç nə yazmır."""
    path = request.path
    if not path.startswith(LOGGED_PREFIXES):
        return
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return

    from workflow.models import MsnOperator
    if not MsnOperator.objects.filter(user=user, is_active=True).exists():
        return

    from audit.models import OperatorActivity
    from authentication.utils import get_client_ip

    method = request.method
    if method in ("HEAD", "OPTIONS"):
        return
    body = _parse_body(body_bytes)
    data = getattr(response, "data", None)
    info = classify(method, path, body, data if isinstance(data, dict) else None)
    if info is None:
        return
    # GET: yalnız konkret obyektə baxış (siyahı sorğuları yox)
    if method == "GET" and not (info["object_id"] or info["org_id"]):
        return
    # Baxış cəhdi uğursuzdursa: icazə verilməyən (401/403) cəhdlər audit üçün yazılır, 404 və s. yox
    if method == "GET" and response.status_code >= 400 and response.status_code not in (401, 403):
        return

    object_label, org_id = _object_info(info)

    if method == "GET":
        since = timezone.now() - timedelta(minutes=GET_DEDUP_MINUTES)
        if OperatorActivity.objects.filter(
            operator=user, action=info["code"], object_type=info["object_type"],
            object_id=info["object_id"], method="GET", created_at__gte=since,
        ).exists():
            return

    label = info["label"]
    if response.status_code >= 400:
        label += f" — uğursuz ({response.status_code})"

    detail = {}
    if body:
        detail["request"] = _redact(body)
    elif method not in ("GET",) and request.META.get("CONTENT_TYPE", "").startswith("multipart"):
        detail["request"] = {"multipart": True}
    if request.GET:
        detail["query"] = _redact(request.GET.dict())
    if len(json.dumps(detail, default=str)) > MAX_DETAIL_CHARS:
        detail = {"_truncated": True, "request_keys": list(body.keys())[:40]}

    full_name = f"{user.first_name} {user.last_name}".strip() or user.username
    OperatorActivity.objects.create(
        operator=user, operator_username=user.username, operator_name=full_name,
        action=info["code"], action_label=label[:255],
        object_type=info["object_type"], object_id=info["object_id"], object_label=object_label,
        organization_id=org_id, method=method, path=path[:255], status_code=response.status_code,
        ip_address=get_client_ip(request) or None, detail=detail,
    )