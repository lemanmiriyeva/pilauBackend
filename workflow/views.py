from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from licenses.field_schema import DOC_TYPES
from organizations.permissions import is_full_admin, is_org_admin

from workflow.models import ApproverPermission, Notification, OrgReviewerPermission, OrgStage2Setting, \
    OrganizationStage1Approver
from workflow.serializers import NotificationSerializer, OrgStage2SettingToggleSerializer, PermissionToggleSerializer, WorkflowConfigUpdateSerializer
from authentication.models import User
from organizations.models import Organization
from workflow.models import (
    DocumentWorkflowConfig,
)

DOC_TYPES_PAYLOAD = [{"key": key, "label": label} for key, label in DOC_TYPES]


def _user_row(user, permissions_by_user, doc_type_keys):
    row_permissions = permissions_by_user.get(user.id, {})
    return {
        "id": user.id,
        "full_name": (f"{user.first_name} {user.last_name}".strip() or user.username),
        "username": user.username,
        "department": user.department,
        "position": user.position,
        "is_org_admin": user.is_org_admin,
        "permissions": {dt: row_permissions.get(dt, False) for dt in doc_type_keys},
    }


def _resolve_organization_for_org_admin_screen(request):
    """Qurum admini üçün öz təşkilatını, Nazirlik admini üçün ?organization= parametrini həll
    edir. Stage1PermissionsView və OrgStage2SettingsView eyni qaydanı paylaşır."""
    requested_id = request.query_params.get("organization") or request.data.get("organization")
    user = request.user

    if is_full_admin(user):
        if not requested_id:
            return None, Response(
                {"detail": "Nazirlik admini üçün 'organization' parametri məcburidir."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return get_object_or_404(Organization, pk=requested_id), None

    if not is_org_admin(user):
        return None, Response(
            {"detail": "Bu əməliyyat yalnız qurum adminləri üçündür."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if not user.organization_id:
        return None, Response({"detail": "İstifadəçinin təşkilatı təyin olunmayıb."}, status=400)
    if requested_id and str(requested_id) != str(user.organization_id):
        return None, Response(
            {"detail": "Yalnız öz təşkilatınızın icazələrini idarə edə bilərsiniz."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return user.organization, None


class Stage1PermissionsView(APIView):
    """1-ci mərhələ - Qurum yoxlaması icazələri.

    GET  /api/workflow/stage1-permissions/?organization=<id>
        - Qurum admini: 'organization' göndərməsə belə öz təşkilatı istifadə olunur, başqa
          təşkilat göndərsə 403 (yalnız öz təşkilatına baxa bilər).
        - Nazirlik admini (staff/superuser): istənilən 'organization' göndərə bilər (məcburidir).
    POST eyni body: {"organization": <id>, "user": <id>, "doc_type": "istehsal", "value": true}
        - Tək bir icazə sətrini yaradır/yeniləyir (checkbox toggle). Multi-select effekti
          frontend-də hər istifadəçi/kateqoriya kəsişməsi üçün ayrı-ayrı bu endpoint-i çağırmaqla
          yaranır (bax PermissionGrid komponenti) - bir təşkilatda istənilən sayda istifadəçi
          eyni kateqoriya üzrə işarələnə bilər.
    """
    permission_classes = [permissions.IsAuthenticated]
    doc_type_keys = [k for k, _ in DOC_TYPES]

    def _resolve_organization(self, request):
        return _resolve_organization_for_org_admin_screen(request)

    def get(self, request):
        organization, error = self._resolve_organization(request)
        if error:
            return error

        users = User.objects.filter(organization=organization, is_active=True).order_by(
            "first_name", "last_name", "username"
        )
        rows = OrgReviewerPermission.objects.filter(organization=organization, can_review=True)
        permissions_by_user = {}
        for row in rows:
            permissions_by_user.setdefault(row.user_id, {})[row.doc_type] = True

        return Response({
            "organization": {"id": organization.id, "full_name": organization.full_name},
            "doc_types": DOC_TYPES_PAYLOAD,
            "users": [_user_row(u, permissions_by_user, self.doc_type_keys) for u in users],
        })

    def post(self, request):
        organization, error = self._resolve_organization(request)
        if error:
            return error

        serializer = PermissionToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        target_user = get_object_or_404(User, pk=data["user"], organization=organization)

        OrgReviewerPermission.objects.update_or_create(
            organization=organization, user=target_user, doc_type=data["doc_type"],
            defaults={"can_review": data["value"], "granted_by": request.user},
        )
        return Response({"detail": "Yadda saxlanıldı."})


class Stage2PermissionsView(APIView):
    """2-ci mərhələ - Təsdiq icazələri (Nazirlik tərəfi, təşkilatdan asılı deyil).

    GET  /api/workflow/stage2-permissions/?organization=<id> (organization filtri istəyə bağlıdır -
        siyahını daraltmaq üçündür, verilməsə bütün aktiv istifadəçilər göstərilir)
    POST {"user": <id>, "doc_type": "istehsal", "value": true}

    Yalnız Nazirlik admini (is_staff/is_superuser) görə/dəyişə bilər.
    """
    permission_classes = [permissions.IsAdminUser]
    doc_type_keys = [k for k, _ in DOC_TYPES]

    def get(self, request):
        users = User.objects.filter(is_active=True).order_by("first_name", "last_name", "username")
        organization_id = request.query_params.get("organization")
        if organization_id:
            users = users.filter(organization_id=organization_id)

        rows = ApproverPermission.objects.filter(can_approve=True)
        permissions_by_user = {}
        for row in rows:
            permissions_by_user.setdefault(row.user_id, {})[row.doc_type] = True

        return Response({
            "doc_types": DOC_TYPES_PAYLOAD,
            "users": [_user_row(u, permissions_by_user, self.doc_type_keys) for u in users],
        })

    def post(self, request):
        serializer = PermissionToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        target_user = get_object_or_404(User, pk=data["user"])

        ApproverPermission.objects.update_or_create(
            user=target_user, doc_type=data["doc_type"],
            defaults={"can_approve": data["value"], "granted_by": request.user},
        )
        return Response({"detail": "Yadda saxlanıldı."})


class ApproversListView(APIView):
    """Verilmiş kateqoriya üzrə 2-ci mərhələ (təsdiq) hüququ olan istifadəçilərin sadə siyahısı.
    'Təsdiqdən sonrakı məsələlər' (konkret sənəddə kimə göndəriləcəyini seçmək) hazırlandıqda bu
    endpoint istifadə olunacaq - hələlik yalnız siyahını qaytarır.
    GET /api/workflow/approvers/?doc_type=istehsal
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        doc_type = request.query_params.get("doc_type")
        if doc_type not in dict(DOC_TYPES):
            return Response({"detail": "doc_type düzgün göndərilməyib."}, status=400)

        user_ids = ApproverPermission.objects.filter(
            doc_type=doc_type, can_approve=True
        ).values_list("user_id", flat=True)
        users = User.objects.filter(id__in=user_ids, is_active=True).order_by("first_name", "last_name")

        return Response([
            {
                "id": u.id,
                "full_name": (f"{u.first_name} {u.last_name}".strip() or u.username),
                "department": u.department,
                "position": u.position,
            } for u in users
        ])


def _eligible_msn_users(doc_type):
    approver_ids = ApproverPermission.objects.filter(
        doc_type=doc_type, can_approve=True
    ).values_list("user_id", flat=True)
    users = User.objects.filter(
        Q(id__in=approver_ids) | Q(is_staff=True) | Q(is_superuser=True),
        is_active=True,
    ).order_by("first_name", "last_name")
    return [
        {
            "id": u.id,
            "full_name": (f"{u.first_name} {u.last_name}".strip() or u.username),
            "department": u.department,
            "position": u.position,
        } for u in users
    ]

class Stage1OrganizationUsersView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        doc_type = request.query_params.get("doc_type")

        if not doc_type:
            return Response(
                {"detail": "doc_type tələb olunur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            config = DocumentWorkflowConfig.objects.get(
                doc_type=doc_type
            )
        except DocumentWorkflowConfig.DoesNotExist:
            # Hələ heç kim bu kateqoriya üçün "Təsdiq axını"nda heç nə saxlamayıbsa,
            # DocumentWorkflowConfig sətri yaranmır (WorkflowConfigView.get() bunu defolt
            # 'qurum' rejimi kimi göstərir) - burada da eyni fallback tətbiq olunmalıdır,
            # əks halda accordion (qurum + işçilər siyahısı) HEÇ VAXT açılmır (404).
            config = None

        organizations = (
            Organization.objects
            .filter(is_active=True)
            .order_by("full_name")
        )

        result = []

        for organization in organizations:

            users = User.objects.filter(
                organization=organization,
                is_active=True,
            )

            approver_ids = (
                OrgReviewerPermission.objects
                .filter(
                    doc_type=doc_type,
                    can_review=True,
                    organization=organization,
                    user__organization=organization,
                )
                .values_list("user_id", flat=True)
            )

            users = users.filter(
                Q(is_org_admin=True) |
                Q(id__in=approver_ids)
            ).distinct()

            users_data = []

            for user in users:
                users_data.append({
                    "id": user.id,
                    "full_name": (
                        f"{user.first_name} {user.last_name}".strip()
                        or user.username
                    ),
                    "username": user.username,
                    "is_org_admin": user.is_org_admin,
                    "department": (
                        user.department.name
                        if user.department
                        else ""
                    ),
                    "position": (
                        user.position.name
                        if user.position
                        else ""
                    ),
                })

            organization_config = (
                OrganizationStage1Approver.objects
                .filter(
                    workflow_config=config,
                    organization=organization,
                )
                .first()
                if config else None
            )

            selected_user_ids = []

            if organization_config:
                selected_user_ids = list(
                    organization_config.users.values_list(
                        "id",
                        flat=True,
                    )
                )

            result.append({
                "organization_id": organization.id,
                "organization_name": organization.full_name,
                "users": users_data,
                "selected_user_ids": selected_user_ids,
            })

        return Response(result)
class WorkflowConfigView(APIView):
    """Sənəd növü üzrə mərhələli təsdiq axınının marşrutlanması (1-ci mərhələ: Qurum/MSN,
    2-ci mərhələ: həmişə MSN). Yalnız Nazirlik admini görə/dəyişə bilər.

    GET  /api/workflow/workflow-config/
        Bütün doc_type-lar üçün cari konfiqurasiyanı (yoxdursa defolt 'qurum', stage2 aktiv)
        VƏ hər biri üçün seçilə bilən MSN icraçılarının siyahısını (ApproverPermission-a
        əsasən) qaytarır.
    PUT  /api/workflow/workflow-config/
        Body: {"doc_type": "istehsal", "stage1_mode": "qurum"|"msn",
               "stage1_user": <id|null>, "stage2_enabled": true|false, "stage2_user": <id|null>}
        Tək bir doc_type-ın axınını yaradır/yeniləyir. stage2_enabled=false olduqda
        stage2_user tələb olunmur (dəyər saxlanılır, sadəcə istifadə edilmir).
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        configs_by_type = {c.doc_type: c for c in DocumentWorkflowConfig.objects.all()}

        rows = []
        for key, label in DOC_TYPES:
            config = configs_by_type.get(key)
            rows.append({
                "doc_type": key,
                "label": label,
                "stage1_mode": config.stage1_mode if config else "qurum",
                "stage1_user": config.stage1_user_id if config else None,
                "stage2_enabled": config.stage2_enabled if config else True,
                "stage2_user": config.stage2_user_id if config else None,
                "eligible_users": _eligible_msn_users(key),

            })
        return Response(rows)

    def put(self, request):
        serializer = WorkflowConfigUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        existing = DocumentWorkflowConfig.objects.filter(doc_type=data["doc_type"]).first()

        # stage2 sahələri (stage2_enabled/stage2_user) bu sorğuda ÖZÜ göndərilməyibsə, mövcud
        # dəyərlər olduğu kimi saxlanılır. Əks halda accordion-dan yalnız 1-ci mərhələnin
        # (qurum + işçilər) yenilənməsi hər dəfə stage2_user-i də yenidən tələb edir və
        # doğrulama səhvən uğursuz olurdu ("...icazəsi yoxdur" - stage2_user default None idi).
        if "stage2_enabled" in request.data:
            stage2_enabled = data["stage2_enabled"]
        else:
            stage2_enabled = existing.stage2_enabled if existing else True

        if "stage2_user" in request.data:
            stage2_user_id = data.get("stage2_user")
        else:
            stage2_user_id = existing.stage2_user_id if existing else None

        eligible_ids = {u.id for u in User.objects.filter(
            id__in=ApproverPermission.objects.filter(
                doc_type=data["doc_type"], can_approve=True
            ).values_list("user_id", flat=True)
        )}

        if data["stage1_mode"] == "msn" and data.get("stage1_user") not in eligible_ids:
            return Response(
                {"detail": "Seçilən istifadəçinin bu kateqoriya üzrə təsdiq və yoxlama icazəsi yoxdur."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # stage2_user_id=None (hələ seçilməyib) - bu, kifayət qədər əsaslı bir aralıq vəziyyətdir
        # (məs. admin əvvəlcə yalnız 1-ci mərhələni qurur, 2-ci mərhələni sonra tənzimləyəcək) -
        # ona görə yalnız FAKTİKİ bir istifadəçi seçiləndə onun icazəsini yoxlayırıq.
        if stage2_enabled and stage2_user_id is not None and stage2_user_id not in eligible_ids:
            return Response(
                {"detail": "Seçilən istifadəçinin bu kateqoriya üzrə təsdiq və yoxlama icazəsi yoxdur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config, created = DocumentWorkflowConfig.objects.update_or_create(
            doc_type=data["doc_type"],
            defaults={
                "stage1_mode": data["stage1_mode"],
                "stage1_user_id": (
                    data.get("stage1_user")
                    if data["stage1_mode"] == "msn"
                    else None
                ),
                "stage2_enabled": stage2_enabled,
                "stage2_user_id": stage2_user_id,
                "updated_by": request.user,
            },
        )
        if data["stage1_mode"] == "qurum":

            organization_rows = data.get(
                "organization_stage1_approvers",
                []
            )

            for row in organization_rows:
                organization_id = row.get("organization_id")
                user_ids = row.get("user_ids", [])

                organization_config, _ = (
                    OrganizationStage1Approver.objects
                    .get_or_create(
                        workflow_config=config,
                        organization_id=organization_id,
                    )
                )

                organization_config.users.set(user_ids)

                organization_config.updated_by = request.user
                organization_config.save(
                    update_fields=[
                        "updated_by",
                        "updated_at",
                    ]
                )

        else:
            OrganizationStage1Approver.objects.filter(
                workflow_config=config
            ).delete()
        return Response({
            "doc_type": config.doc_type,
            "stage1_mode": config.stage1_mode,
            "stage1_user": config.stage1_user_id,
            "stage2_enabled": config.stage2_enabled,
            "stage2_user": config.stage2_user_id,
        })


class OrgStage2SettingsView(APIView):
    """Qurum admininin öz təşkilatı üçün, hər lisenziya kateqoriyasında 2-ci mərhələni (MSN son
    təsdiqi) söndürüb-söndürməyəcəyini idarə etdiyi ekran (bax OrgStage2Setting modeli və
    PermitDocument.approve_stage - buradakı dəyər həqiqətən təsdiq axınına təsir edir).

    GET  /api/workflow/stage2-settings/?organization=<id>
        Cavab: {"doc_types": [...], "settings": {"istehsal": true, ...}}
        settings[doc_type] = True o deməkdir ki, 2-ci mərhələ (MSN) SÖNDÜRÜLÜB (skip_stage2=True).
    POST {"organization": <id>, "doc_type": "istehsal", "skip_stage2": true}
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        organization, error = _resolve_organization_for_org_admin_screen(request)
        if error:
            return error

        rows = OrgStage2Setting.objects.filter(organization=organization, skip_stage2=True)
        settings_map = {row.doc_type: True for row in rows}

        return Response({
            "organization": {"id": organization.id, "full_name": organization.full_name},
            "doc_types": DOC_TYPES_PAYLOAD,
            "settings": settings_map,
        })

    def post(self, request):
        organization, error = _resolve_organization_for_org_admin_screen(request)
        if error:
            return error

        serializer = OrgStage2SettingToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        OrgStage2Setting.objects.update_or_create(
            organization=organization, doc_type=data["doc_type"],
            defaults={"skip_stage2": data["skip_stage2"], "updated_by": request.user},
        )
        return Response({"detail": "Yadda saxlanıldı."})


class NotificationListView(APIView):
    """GET /api/workflow/notifications/ - cari istifadəçinin bildirişləri + oxunmamış sayı.

    Query param-lar (ikisi də optional - bell dropdown-u parametrsiz çağırır, ilk 50-ni alır):
      ?page=1&page_size=20 - tam bildirişlər səhifəsi üçün səhifələmə
      ?unread=true         - yalnız oxunmamışları göstər
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user)
        if str(request.query_params.get("unread", "")).lower() in ("1", "true", "yes"):
            qs = qs.filter(is_read=False)

        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(100, max(1, int(request.query_params.get("page_size", 50))))
        except (TypeError, ValueError):
            page, page_size = 1, 50

        total = qs.count()
        start = (page - 1) * page_size
        page_qs = qs[start:start + page_size]

        return Response({
            "unread_count": unread_count,
            "count": total,
            "page": page,
            "page_size": page_size,
            "has_next": start + page_size < total,
            "results": NotificationSerializer(page_qs, many=True).data,
        })


class NotificationMarkReadView(APIView):
    """POST /api/workflow/notifications/<id>/read/ - tək bildirişi oxunmuş kimi işarələyir.
    POST /api/workflow/notifications/read-all/ - hamısını oxunmuş kimi işarələyir (pk=0 göndərilir)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        if pk in (None, 0, "0"):
            Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
            return Response({"detail": "Bütün bildirişlər oxunmuş kimi işarələndi."})

        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response({"detail": "Oxunmuş kimi işarələndi."})