from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import User
from licenses.field_schema import DOC_TYPES
from organizations.models import Organization
from organizations.permissions import is_full_admin, is_org_admin, scoped_organization_ids

from workflow.models import ApproverPermission, DocumentWorkflowConfig, Notification, OrgReviewerPermission
from workflow.serializers import NotificationSerializer, PermissionToggleSerializer, WorkflowConfigUpdateSerializer

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


class Stage1PermissionsView(APIView):
    """1-ci mərhələ - Qurum yoxlaması icazələri.

    GET  /api/workflow/stage1-permissions/?organization=<id>
        - Qurum admini: 'organization' göndərməsə belə öz təşkilatı istifadə olunur, başqa
          təşkilat göndərsə 403 (yalnız öz təşkilatına baxa bilər).
        - Nazirlik admini (staff/superuser): istənilən 'organization' göndərə bilər (məcburidir).
    POST eyni body: {"organization": <id>, "user": <id>, "doc_type": "istehsal", "value": true}
        - Tək bir icazə sətrini yaradır/yeniləyir (checkbox toggle).
    """
    permission_classes = [permissions.IsAuthenticated]
    doc_type_keys = [k for k, _ in DOC_TYPES]

    def _resolve_organization(self, request):
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
    user_ids = ApproverPermission.objects.filter(
        doc_type=doc_type, can_approve=True
    ).values_list("user_id", flat=True)
    users = User.objects.filter(id__in=user_ids, is_active=True).order_by("first_name", "last_name")
    return [
        {
            "id": u.id,
            "full_name": (f"{u.first_name} {u.last_name}".strip() or u.username),
            "department": u.department,
            "position": u.position,
        } for u in users
    ]


class WorkflowConfigView(APIView):
    """Sənəd növü üzrə mərhələli təsdiq axınının marşrutlanması (1-ci mərhələ: Qurum/MSN,
    2-ci mərhələ: həmişə MSN). Yalnız Nazirlik admini görə/dəyişə bilər.

    GET  /api/workflow/workflow-config/
        Bütün doc_type-lar üçün cari konfiqurasiyanı (yoxdursa defolt 'qurum') VƏ hər biri
        üçün seçilə bilən MSN icraçılarının siyahısını (ApproverPermission-a əsasən) qaytarır.
    PUT  /api/workflow/workflow-config/
        Body: {"doc_type": "istehsal", "stage1_mode": "qurum"|"msn",
               "stage1_user": <id|null>, "stage2_user": <id>}
        Tək bir doc_type-ın axınını yaradır/yeniləyir.
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
                "stage2_user": config.stage2_user_id if config else None,
                "eligible_users": _eligible_msn_users(key),
            })
        return Response(rows)

    def put(self, request):
        serializer = WorkflowConfigUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

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
        if data.get("stage2_user") not in eligible_ids:
            return Response(
                {"detail": "Seçilən istifadəçinin bu kateqoriya üzrə təsdiq və yoxlama icazəsi yoxdur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config, _ = DocumentWorkflowConfig.objects.update_or_create(
            doc_type=data["doc_type"],
            defaults={
                "stage1_mode": data["stage1_mode"],
                "stage1_user_id": data.get("stage1_user") if data["stage1_mode"] == "msn" else None,
                "stage2_user_id": data.get("stage2_user"),
                "updated_by": request.user,
            },
        )
        return Response({
            "doc_type": config.doc_type,
            "stage1_mode": config.stage1_mode,
            "stage1_user": config.stage1_user_id,
            "stage2_user": config.stage2_user_id,
        })


class NotificationListView(APIView):
    """GET /api/workflow/notifications/ - cari istifadəçinin son bildirişləri + oxunmamış sayı."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user)[:50]
        return Response({
            "unread_count": Notification.objects.filter(recipient=request.user, is_read=False).count(),
            "results": NotificationSerializer(qs, many=True).data,
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