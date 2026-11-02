"""Təşkilat səhifəsindəki "Modul icazələri" və "Təsdiq axını" tabları üçün API-lər.

GET/PUT /api/organizations/<id>/module-access/   - təşkilata açıq modullar (yazma: yalnız Nazirlik admini)
GET/PUT /api/organizations/<id>/approval-flow/   - sənəd növləri üzrə qurum yoxlayıcıları + MSN-i keçmə
                                                     (yazma: Nazirlik admini və HƏMİN təşkilatın admini)
"""
from django.db import transaction
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import User
from licenses.field_schema import DOC_TYPES
from permissions_module.models import (
    GlobalOrgModuleAccess, Module, OrganizationModuleAccess, OrganizationModuleSettings,
    global_module_ids, org_module_ids, org_uses_custom,
)

from .permissions import is_full_admin, is_org_admin
from .profile_views import can_org_action, get_visible_organization

HIDDEN_DOC_TYPES = {"istehsal"}  # köhnə kateqoriya
# Sənəd növü -> onun "Təsdiq" icazəsinin verildiyi modul
DOC_TYPE_MODULE = {
    "ixrac": "idxal-ixrac", "idxal": "idxal-ixrac",
    "xususi_lisenziya": "lisenziya", "umumi_lisenziya": "lisenziya",
    "xususi_satis": "xususi-satis",
    "gomrukden_azadolma": "edv-guzesti", "edvden_azadolma": "edv-guzesti",
}


def _candidates(org, users):
    """{doc_type: [user,...]} - təşkilatda həmin sənəd növünün modulu üzrə 'Təsdiq' icazəsi olanlar
    (qurum adminləri həmişə daxildir)."""
    from permissions_module.models import UserModulePermission

    allowed = org_module_ids(org)
    modules = {m.key: m.id for m in Module.objects.filter(key__in=set(DOC_TYPE_MODULE.values()))}
    approvers = {}
    for p in UserModulePermission.objects.filter(user__in=users, can_approve=True):
        approvers.setdefault(p.module_id, set()).add(p.user_id)
    out = {}
    for dt, key in DOC_TYPE_MODULE.items():
        mid = modules.get(key)
        ok_module = mid is not None and (allowed is None or mid in allowed)
        ids = approvers.get(mid, set()) if ok_module else set()
        out[dt] = [u for u in users if u.is_org_admin or u.id in ids]
    return out
STAFF_ONLY_MODULES = {"tesdiq-huquqlari"}


def _can_edit_flow(user, org) -> bool:
    """Nazirlik admini; HƏMİN təşkilatın admini; və ya təşkilatın 'Təşkilatlar' modulunda
    'Redaktə' icazəsi olan işçisi."""
    return can_org_action(user, org, "edit")


def _name(u):
    return f"{u.first_name} {u.last_name}".strip() or u.username


def _modules_payload(enabled_ids, extra):
    modules = list(Module.objects.all().order_by("order", "title"))
    return {
        **extra,
        "modules": [
            {"id": m.id, "parent": m.parent_id, "key": m.key, "title": m.title, "enabled": m.id in enabled_ids}
            for m in modules
        ],
    }


def _clean_ids(raw):
    ids = {int(i) for i in (raw or [])}
    return set(Module.objects.filter(id__in=ids).values_list("id", flat=True))


class ModuleDefaultsView(APIView):
    """Bütün qurum adminləri üçün ÜMUMİ modul konfiqurasiyası (yalnız Nazirlik admini)."""
    permission_classes = [permissions.IsAuthenticated]

    def _check(self, request):
        if not is_full_admin(request.user):
            return Response({"detail": "Bu səhifə yalnız Nazirlik adminləri üçündür."}, status=403)

    def _payload(self):
        enabled = global_module_ids()
        if not enabled:
            enabled = {m.id for m in Module.objects.all() if m.key not in STAFF_ONLY_MODULES}
        return _modules_payload(enabled, {"can_edit": True, "scope": "global"})

    def get(self, request):
        return self._check(request) or Response(self._payload())

    @transaction.atomic
    def put(self, request):
        denied = self._check(request)
        if denied:
            return denied
        ids = _clean_ids(request.data.get("module_ids"))
        GlobalOrgModuleAccess.objects.exclude(module_id__in=ids).delete()
        existing = set(GlobalOrgModuleAccess.objects.values_list("module_id", flat=True))
        GlobalOrgModuleAccess.objects.bulk_create([GlobalOrgModuleAccess(module_id=i) for i in ids - existing])
        return Response(self._payload())


class OrganizationModuleAccessView(APIView):
    """Təşkilatın modulları: ya ümumi konfiqurasiya (custom=False), ya da bu təşkilata məxsus
    fərdi siyahı (custom=True). Dəyişmək yalnız Nazirlik admini."""
    permission_classes = [permissions.IsAuthenticated]

    def _payload(self, org, request):
        custom = org_uses_custom(org)
        enabled = org_module_ids(org)
        if enabled is None:
            enabled = {m.id for m in Module.objects.all() if m.key not in STAFF_ONLY_MODULES}
        return _modules_payload(enabled, {
            "can_edit": is_full_admin(request.user), "custom": custom, "scope": "organization",
        })

    def get(self, request, pk):
        org = get_visible_organization(request, pk)
        return Response(self._payload(org, request))

    @transaction.atomic
    def put(self, request, pk):
        org = get_visible_organization(request, pk)
        if not is_full_admin(request.user):
            return Response({"detail": "Modulları yalnız Nazirlik admini dəyişə bilər."}, status=403)
        custom = bool(request.data.get("custom", True))
        if not custom:
            OrganizationModuleSettings.objects.update_or_create(organization=org, defaults={"use_custom": False})
            return Response(self._payload(org, request))
        if "module_ids" in request.data:
            ids = _clean_ids(request.data.get("module_ids"))
        else:  # fərdiyə keçid: ümumi siyahını başlanğıc kimi götür
            ids = set(org_module_ids(org) or global_module_ids())
        OrganizationModuleAccess.objects.filter(organization=org).exclude(module_id__in=ids).delete()
        existing = set(OrganizationModuleAccess.objects.filter(organization=org).values_list("module_id", flat=True))
        OrganizationModuleAccess.objects.bulk_create(
            [OrganizationModuleAccess(organization=org, module_id=i) for i in ids - existing]
        )
        OrganizationModuleSettings.objects.update_or_create(organization=org, defaults={"use_custom": True})
        return Response(self._payload(org, request))


class OrganizationApprovalFlowView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _payload(self, org, request):
        from workflow.models import DocumentWorkflowConfig, OrgReviewerPermission, OrgStage2Setting

        users = list(
            User.objects.filter(organization=org, is_active=True)
            .select_related("position", "department").order_by("first_name", "last_name", "username")
        )
        reviewers = {}
        for r in OrgReviewerPermission.objects.filter(organization=org, can_review=True):
            reviewers.setdefault(r.doc_type, []).append(r.user_id)
        skipped = set(
            OrgStage2Setting.objects.filter(organization=org, skip_stage2=True).values_list("doc_type", flat=True)
        )
        cfg = {c.doc_type: c for c in DocumentWorkflowConfig.objects.select_related("stage2_user", "signer_user")}
        admin_ids = [u.id for u in users if u.is_org_admin]
        cands = _candidates(org, users)
        items = []
        for key, label in DOC_TYPES:
            if key in HIDDEN_DOC_TYPES:
                continue
            c = cfg.get(key)
            items.append({
                "doc_type": key,
                "label": label,
                "stage1_mode": c.stage1_mode if c else "qurum",
                "stage2_enabled": c.stage2_enabled if c else True,
                "stage2_user": _name(c.stage2_user) if c and c.stage2_user else None,
                "signer": _name(c.signer_user) if c and c.signer_user else None,
                "skip_stage2": key in skipped,
                "reviewer_ids": reviewers.get(key, []),
                "candidates": [
                    {"id": u.id, "full_name": _name(u), "is_org_admin": u.is_org_admin,
                     "position": u.position.name if u.position_id else "",
                     "department": u.department.name if u.department_id else ""}
                    for u in cands.get(key, [])
                ],
            })
        return {
            "can_edit": _can_edit_flow(request.user, org),
            "admin_ids": admin_ids,
            "users": [
                {"id": u.id, "full_name": _name(u), "is_org_admin": u.is_org_admin,
                 "position": u.position.name if u.position_id else "",
                 "department": u.department.name if u.department_id else ""}
                for u in users
            ],
            "doc_types": items,
        }

    def get(self, request, pk):
        org = get_visible_organization(request, pk)
        return Response(self._payload(org, request))

    @transaction.atomic
    def put(self, request, pk):
        from workflow.models import OrgReviewerPermission, OrgStage2Setting

        org = get_visible_organization(request, pk)
        if not _can_edit_flow(request.user, org):
            return Response({"detail": "Bu təşkilatın təsdiq axınını dəyişmək hüququnuz yoxdur."}, status=403)
        valid_types = {k for k, _ in DOC_TYPES} - HIDDEN_DOC_TYPES
        for item in request.data.get("doc_types") or []:
            dt = item.get("doc_type")
            if dt not in valid_types:
                continue
            if "skip_stage2" in item:
                OrgStage2Setting.objects.update_or_create(
                    organization=org, doc_type=dt,
                    defaults={"skip_stage2": bool(item["skip_stage2"]), "updated_by": request.user},
                )
            if "reviewer_ids" in item:
                allowed_ids = {
                    u.id for u in _candidates(org, list(User.objects.filter(organization=org, is_active=True))).get(dt, [])
                }
                ids = set(
                    User.objects.filter(organization=org, is_active=True, id__in=item["reviewer_ids"] or [])
                    .values_list("id", flat=True)
                ) & allowed_ids
                OrgReviewerPermission.objects.filter(organization=org, doc_type=dt).exclude(user_id__in=ids).delete()
                for uid in ids:
                    OrgReviewerPermission.objects.update_or_create(
                        organization=org, user_id=uid, doc_type=dt,
                        defaults={"can_review": True, "granted_by": request.user},
                    )
        return Response(self._payload(org, request))
