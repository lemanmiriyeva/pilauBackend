from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from licenses.field_schema import DOC_TYPES

from organizations.permissions import (
    is_full_admin,
    is_org_admin,
)

from organizations.models import Organization

from authentication.models import User

from workflow.models import (
    ApproverPermission,
    Notification,
    OrgReviewerPermission,
    OrgStage2Setting,
    OrganizationStage1Approver,
    DocumentWorkflowConfig,
)

from workflow.serializers import (
    NotificationSerializer,
    OrgStage2SettingToggleSerializer,
    PermissionToggleSerializer,
    WorkflowConfigUpdateSerializer,
)

# ============================================================================
# DOCUMENT TYPES
# ============================================================================

DOC_TYPES_PAYLOAD = [
    {
        "key": key,
        "label": label,
    }
    for key, label in DOC_TYPES
]


# ============================================================================
# USER ROW HELPER
# ============================================================================

def _user_row(user, permissions_by_user, doc_type_keys):
    """
    Workflow permission ekranlarında istifadəçi məlumatlarını
    frontend üçün JSON serializable formada qaytarır.

    Vacib:
        department və position ForeignKey obyektidir.
        Onları birbaşa Response-a vermək olmaz.

        Səhv:
            "department": user.department

        Düzgün:
            "department": user.department.name if user.department else ""

    """

    row_permissions = permissions_by_user.get(
        user.id,
        {}
    )

    return {
        "id": user.id,

        "full_name": (
                f"{user.first_name} {user.last_name}".strip()
                or user.username
        ),

        "username": user.username,

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

        "is_org_admin": user.is_org_admin,

        "permissions": {
            dt: row_permissions.get(dt, False)
            for dt in doc_type_keys
        },
    }


# ============================================================================
# ORGANIZATION RESOLVER
# ============================================================================

def _resolve_organization_for_org_admin_screen(request):
    """
    Qurum admini:
        öz təşkilatını istifadə edir.

    Nazirlik admini:
        ?organization=<id> göndərməlidir.

    Qurum admini başqa təşkilata baxa bilməz.
    """

    requested_id = (
            request.query_params.get("organization")
            or request.data.get("organization")
    )

    user = request.user

    # ------------------------------------------------------------------------
    # FULL ADMIN
    # ------------------------------------------------------------------------

    if is_full_admin(user):

        if not requested_id:
            return None, Response(
                {
                    "detail": (
                        "Nazirlik admini üçün "
                        "'organization' parametri məcburidir."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return (
            get_object_or_404(
                Organization,
                pk=requested_id
            ),
            None,
        )

    # ------------------------------------------------------------------------
    # ORGANIZATION ADMIN
    # ------------------------------------------------------------------------

    if not is_org_admin(user):
        return None, Response(
            {
                "detail": (
                    "Bu əməliyyat yalnız "
                    "qurum adminləri üçündür."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # ------------------------------------------------------------------------
    # USER ORGANIZATION CHECK
    # ------------------------------------------------------------------------

    if not user.organization_id:
        return None, Response(
            {
                "detail": (
                    "İstifadəçinin təşkilatı "
                    "təyin olunmayıb."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ------------------------------------------------------------------------
    # OTHER ORGANIZATION CHECK
    # ------------------------------------------------------------------------

    if (
            requested_id
            and str(requested_id) != str(user.organization_id)
    ):
        return None, Response(
            {
                "detail": (
                    "Yalnız öz təşkilatınızın "
                    "icazələrini idarə edə bilərsiniz."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    return user.organization, None


# ============================================================================
# STAGE 1 PERMISSIONS
# ============================================================================

class Stage1PermissionsView(APIView):
    """
    1-ci mərhələ - Qurum yoxlaması icazələri.

    GET:

        /api/workflow/stage1-permissions/?organization=<id>

    POST:

        {
            "organization": 1,
            "user": 5,
            "doc_type": "istehsal",
            "value": true
        }
    """

    permission_classes = [
        permissions.IsAuthenticated
    ]

    doc_type_keys = [
        k for k, _ in DOC_TYPES
    ]

    # ------------------------------------------------------------------------
    # ORGANIZATION
    # ------------------------------------------------------------------------

    def _resolve_organization(self, request):

        return _resolve_organization_for_org_admin_screen(
            request
        )

    # ------------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------------

    def get(self, request):

        organization, error = self._resolve_organization(
            request
        )

        if error:
            return error

        # --------------------------------------------------------------------
        # USERS
        # --------------------------------------------------------------------

        users = (
            User.objects
            .filter(
                organization=organization,
                is_active=True,
            )
            .select_related(
                "department",
                "position",
            )
            .order_by(
                "first_name",
                "last_name",
                "username",
            )
        )

        # --------------------------------------------------------------------
        # PERMISSIONS
        # --------------------------------------------------------------------

        rows = (
            OrgReviewerPermission.objects
            .filter(
                organization=organization,
                can_review=True,
            )
        )

        permissions_by_user = {}

        for row in rows:
            permissions_by_user.setdefault(
                row.user_id,
                {}
            )[row.doc_type] = True

        # --------------------------------------------------------------------
        # RESPONSE
        # --------------------------------------------------------------------

        return Response({

            "organization": {
                "id": organization.id,
                "full_name": organization.full_name,
            },

            "doc_types": DOC_TYPES_PAYLOAD,

            "users": [
                _user_row(
                    user,
                    permissions_by_user,
                    self.doc_type_keys,
                )
                for user in users
            ],
        })

    # ------------------------------------------------------------------------
    # POST
    # ------------------------------------------------------------------------

    def post(self, request):

        organization, error = self._resolve_organization(
            request
        )

        if error:
            return error

        serializer = PermissionToggleSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        target_user = get_object_or_404(
            User,
            pk=data["user"],
            organization=organization,
        )

        OrgReviewerPermission.objects.update_or_create(
            organization=organization,
            user=target_user,
            doc_type=data["doc_type"],
            defaults={
                "can_review": data["value"],
                "granted_by": request.user,
            },
        )

        return Response({
            "detail": "Yadda saxlanıldı."
        })


# ============================================================================
# STAGE 2 PERMISSIONS
# ============================================================================

class Stage2PermissionsView(APIView):
    """
    2-ci mərhələ - Təsdiq icazələri.

    GET:

        /api/workflow/stage2-permissions/

    Optional:

        ?organization=<id>

    POST:

        {
            "user": 5,
            "doc_type": "istehsal",
            "value": true
        }
    """

    permission_classes = [
        permissions.IsAdminUser
    ]

    doc_type_keys = [
        k for k, _ in DOC_TYPES
    ]

    # ------------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------------

    def get(self, request):

        # --------------------------------------------------------------------
        # USERS
        # --------------------------------------------------------------------

        users = (
            User.objects
            .filter(
                is_active=True
            )
            .select_related(
                "department",
                "position",
                "organization",
            )
            .order_by(
                "first_name",
                "last_name",
                "username",
            )
        )

        # --------------------------------------------------------------------
        # ORGANIZATION FILTER
        # --------------------------------------------------------------------

        organization_id = request.query_params.get(
            "organization"
        )

        if organization_id:
            users = users.filter(
                organization_id=organization_id
            )

        # --------------------------------------------------------------------
        # PERMISSIONS
        # --------------------------------------------------------------------

        rows = (
            ApproverPermission.objects
            .filter(
                can_approve=True
            )
        )

        permissions_by_user = {}

        for row in rows:
            permissions_by_user.setdefault(
                row.user_id,
                {}
            )[row.doc_type] = True

        # --------------------------------------------------------------------
        # RESPONSE
        # --------------------------------------------------------------------

        return Response({

            "doc_types": DOC_TYPES_PAYLOAD,

            "users": [
                _user_row(
                    user,
                    permissions_by_user,
                    self.doc_type_keys,
                )
                for user in users
            ],
        })

    # ------------------------------------------------------------------------
    # POST
    # ------------------------------------------------------------------------

    def post(self, request):

        serializer = PermissionToggleSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        target_user = get_object_or_404(
            User,
            pk=data["user"]
        )

        ApproverPermission.objects.update_or_create(
            user=target_user,
            doc_type=data["doc_type"],
            defaults={
                "can_approve": data["value"],
                "granted_by": request.user,
            },
        )

        return Response({
            "detail": "Yadda saxlanıldı."
        })


# ============================================================================
# APPROVERS LIST
# ============================================================================

class ApproversListView(APIView):
    """
    Verilmiş sənəd kateqoriyası üzrə
    2-ci mərhələ təsdiq hüququ olan istifadəçilər.
    """

    permission_classes = [
        permissions.IsAuthenticated
    ]

    def get(self, request):
        doc_type = request.query_params.get(
            "doc_type"
        )

        if doc_type not in dict(DOC_TYPES):
            return Response(
                {
                    "detail": (
                        "doc_type düzgün göndərilməyib."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------------------------
        # APPROVER IDS
        # --------------------------------------------------------------------

        user_ids = (
            ApproverPermission.objects
            .filter(
                doc_type=doc_type,
                can_approve=True,
            )
            .values_list(
                "user_id",
                flat=True,
            )
        )

        # --------------------------------------------------------------------
        # USERS
        # --------------------------------------------------------------------

        users = (
            User.objects
            .filter(
                id__in=user_ids,
                is_active=True,
            )
            .select_related(
                "department",
                "position",
            )
            .order_by(
                "first_name",
                "last_name",
            )
        )

        # --------------------------------------------------------------------
        # RESPONSE
        # --------------------------------------------------------------------

        return Response([

            {
                "id": user.id,

                "full_name": (
                        f"{user.first_name} "
                        f"{user.last_name}".strip()
                        or user.username
                ),

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
            }

            for user in users
        ])


# ============================================================================
# ELIGIBLE MSN USERS
# ============================================================================

def _eligible_msn_users(doc_type):
    approver_ids = (
        ApproverPermission.objects
        .filter(
            doc_type=doc_type,
            can_approve=True,
        )
        .values_list(
            "user_id",
            flat=True,
        )
    )

    users = (
        User.objects
        .filter(
            Q(id__in=approver_ids)
            | Q(is_staff=True)
            | Q(is_superuser=True),

            is_active=True,
        )
        .select_related(
            "department",
            "position",
        )
        .order_by(
            "first_name",
            "last_name",
        )
    )

    return [

        {
            "id": user.id,

            "full_name": (
                    f"{user.first_name} "
                    f"{user.last_name}".strip()
                    or user.username
            ),

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

        }

        for user in users
    ]


# ============================================================================
# STAGE 1 ORGANIZATION USERS
# ============================================================================

class Stage1OrganizationUsersView(APIView):
    permission_classes = (
        permissions.IsAuthenticated,
    )

    def get(self, request):

        doc_type = request.query_params.get(
            "doc_type"
        )

        if not doc_type:
            return Response(
                {
                    "detail": "doc_type tələb olunur."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------------------------
        # WORKFLOW CONFIG
        # --------------------------------------------------------------------

        try:

            config = (
                DocumentWorkflowConfig.objects
                .get(
                    doc_type=doc_type
                )
            )

        except DocumentWorkflowConfig.DoesNotExist:

            config = None

        # --------------------------------------------------------------------
        # ORGANIZATIONS
        # --------------------------------------------------------------------

        organizations = (
            Organization.objects
            .filter(
                is_active=True
            )
            .order_by(
                "full_name"
            )
        )

        result = []

        # --------------------------------------------------------------------
        # LOOP ORGANIZATIONS
        # --------------------------------------------------------------------

        for organization in organizations:

            # ----------------------------------------------------------------
            # USERS
            # ----------------------------------------------------------------

            users = (
                User.objects
                .filter(
                    organization=organization,
                    is_active=True,
                )
                .select_related(
                    "department",
                    "position",
                )
            )

            # ----------------------------------------------------------------
            # REVIEWER IDS
            # ----------------------------------------------------------------

            approver_ids = (
                OrgReviewerPermission.objects
                .filter(
                    doc_type=doc_type,
                    can_review=True,
                    organization=organization,
                    user__organization=organization,
                )
                .values_list(
                    "user_id",
                    flat=True,
                )
            )

            # ----------------------------------------------------------------
            # ADMIN + APPROVERS
            # ----------------------------------------------------------------

            users = (
                users
                .filter(
                    Q(is_org_admin=True)
                    | Q(id__in=approver_ids)
                )
                .distinct()
            )

            # ----------------------------------------------------------------
            # USERS DATA
            # ----------------------------------------------------------------

            users_data = []

            for user in users:
                users_data.append({

                    "id": user.id,

                    "full_name": (
                            f"{user.first_name} "
                            f"{user.last_name}".strip()
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

            # ----------------------------------------------------------------
            # ORGANIZATION CONFIG
            # ----------------------------------------------------------------

            organization_config = (

                OrganizationStage1Approver.objects
                .filter(
                    workflow_config=config,
                    organization=organization,
                )
                .first()

                if config

                else None
            )

            # ----------------------------------------------------------------
            # SELECTED USERS
            # ----------------------------------------------------------------

            selected_user_ids = []

            if organization_config:
                selected_user_ids = list(
                    organization_config.users
                    .values_list(
                        "id",
                        flat=True,
                    )
                )

            # ----------------------------------------------------------------
            # RESULT
            # ----------------------------------------------------------------

            result.append({

                "organization_id": organization.id,

                "organization_name": (
                    organization.full_name
                ),

                "users": users_data,

                "selected_user_ids": (
                    selected_user_ids
                ),
            })

        return Response(result)


# ============================================================================
# WORKFLOW CONFIG
# ============================================================================

class WorkflowConfigView(APIView):
    permission_classes = [
        permissions.IsAdminUser
    ]

    # ------------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------------

    def get(self, request):

        configs_by_type = {
            config.doc_type: config
            for config in (
                DocumentWorkflowConfig.objects.all()
            )
        }

        rows = []

        for key, label in DOC_TYPES:
            config = configs_by_type.get(
                key
            )

            rows.append({

                "doc_type": key,

                "label": label,

                "stage1_mode": (
                    config.stage1_mode
                    if config
                    else "qurum"
                ),

                "stage1_user": (
                    config.stage1_user_id
                    if config
                    else None
                ),

                "stage2_enabled": (
                    config.stage2_enabled
                    if config
                    else True
                ),

                "stage2_user": (
                    config.stage2_user_id
                    if config
                    else None
                ),

                "signer_user": (
                    config.signer_user_id
                    if config
                    else None
                ),

                "eligible_users": (
                    _eligible_msn_users(key)
                ),
            })

        return Response(rows)

    # ------------------------------------------------------------------------
    # PUT
    # ------------------------------------------------------------------------

    def put(self, request):

        serializer = WorkflowConfigUpdateSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        existing = (
            DocumentWorkflowConfig.objects
            .filter(
                doc_type=data["doc_type"]
            )
            .first()
        )

        # --------------------------------------------------------------------
        # STAGE 2 ENABLED
        # --------------------------------------------------------------------

        if "stage2_enabled" in request.data:

            stage2_enabled = data[
                "stage2_enabled"
            ]

        else:

            stage2_enabled = (
                existing.stage2_enabled
                if existing
                else True
            )

        # --------------------------------------------------------------------
        # STAGE 2 USER
        # --------------------------------------------------------------------

        if "stage2_user" in request.data:

            stage2_user_id = data.get(
                "stage2_user"
            )

        else:

            stage2_user_id = (
                existing.stage2_user_id
                if existing
                else None
            )

        # --------------------------------------------------------------------
        # SIGNER USER
        # --------------------------------------------------------------------

        if "signer_user" in request.data:

            signer_user_id = data.get(
                "signer_user"
            )

        else:

            signer_user_id = (
                existing.signer_user_id
                if existing
                else None
            )

        # --------------------------------------------------------------------
        # ELIGIBLE USERS
        # --------------------------------------------------------------------

        eligible_ids = set(
            User.objects
            .filter(
                id__in=(
                    ApproverPermission.objects
                    .filter(
                        doc_type=data["doc_type"],
                        can_approve=True,
                    )
                    .values_list(
                        "user_id",
                        flat=True,
                    )
                )
            )
            .values_list(
                "id",
                flat=True,
            )
        )

        # --------------------------------------------------------------------
        # STAGE 1 MSN
        # --------------------------------------------------------------------

        if (
                data["stage1_mode"] == "msn"
                and data.get("stage1_user")
                not in eligible_ids
        ):
            return Response(
                {
                    "detail": (
                        "Seçilən istifadəçinin "
                        "bu kateqoriya üzrə "
                        "təsdiq və yoxlama "
                        "icazəsi yoxdur."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------------------------
        # STAGE 2 USER
        # --------------------------------------------------------------------

        if (
                stage2_enabled
                and stage2_user_id is not None
                and stage2_user_id not in eligible_ids
        ):
            return Response(
                {
                    "detail": (
                        "Seçilən istifadəçinin "
                        "bu kateqoriya üzrə "
                        "təsdiq və yoxlama "
                        "icazəsi yoxdur."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------------------------
        # SIGNER USER
        # --------------------------------------------------------------------

        if (
                signer_user_id is not None
                and signer_user_id not in eligible_ids
        ):
            return Response(
                {
                    "detail": (
                        "Seçilən istifadəçinin "
                        "bu kateqoriya üzrə "
                        "imzalama hüququ "
                        "yoxdur."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------------------------
        # SAVE CONFIG
        # --------------------------------------------------------------------

        config, created = (
            DocumentWorkflowConfig.objects
            .update_or_create(

                doc_type=data["doc_type"],

                defaults={

                    "stage1_mode": (
                        data["stage1_mode"]
                    ),

                    "stage1_user_id": (

                        data.get("stage1_user")

                        if data["stage1_mode"] == "msn"

                        else None
                    ),

                    "stage2_enabled": (
                        stage2_enabled
                    ),

                    "stage2_user_id": (
                        stage2_user_id
                    ),

                    "signer_user_id": (
                        signer_user_id
                    ),

                    "updated_by": (
                        request.user
                    ),
                },
            )
        )

        # --------------------------------------------------------------------
        # STAGE 1 - QURUM
        # --------------------------------------------------------------------

        if data["stage1_mode"] == "qurum":

            organization_rows = data.get(
                "organization_stage1_approvers",
                []
            )

            for row in organization_rows:
                organization_id = row.get(
                    "organization_id"
                )

                user_ids = row.get(
                    "user_ids",
                    []
                )

                organization_config, _ = (
                    OrganizationStage1Approver.objects
                    .get_or_create(

                        workflow_config=config,

                        organization_id=(
                            organization_id
                        ),
                    )
                )

                organization_config.users.set(
                    user_ids
                )

                organization_config.updated_by = (
                    request.user
                )

                organization_config.save(
                    update_fields=[
                        "updated_by",
                        "updated_at",
                    ]
                )

        # --------------------------------------------------------------------
        # STAGE 1 - MSN
        # --------------------------------------------------------------------

        else:

            OrganizationStage1Approver.objects.filter(
                workflow_config=config
            ).delete()

        # --------------------------------------------------------------------
        # RESPONSE
        # --------------------------------------------------------------------

        return Response({

            "doc_type": config.doc_type,

            "stage1_mode": (
                config.stage1_mode
            ),

            "stage1_user": (
                config.stage1_user_id
            ),

            "stage2_enabled": (
                config.stage2_enabled
            ),

            "stage2_user": (
                config.stage2_user_id
            ),

            "signer_user": (
                config.signer_user_id
            ),
        })


# ============================================================================
# ORGANIZATION STAGE 2 SETTINGS
# ============================================================================

class OrgStage2SettingsView(APIView):
    permission_classes = [
        permissions.IsAuthenticated
    ]

    # ------------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------------

    def get(self, request):

        organization, error = (
            _resolve_organization_for_org_admin_screen(
                request
            )
        )

        if error:
            return error

        rows = (
            OrgStage2Setting.objects
            .filter(
                organization=organization,
                skip_stage2=True,
            )
        )

        settings_map = {
            row.doc_type: True
            for row in rows
        }

        return Response({

            "organization": {

                "id": organization.id,

                "full_name": (
                    organization.full_name
                ),
            },

            "doc_types": DOC_TYPES_PAYLOAD,

            "settings": settings_map,
        })

    # ------------------------------------------------------------------------
    # POST
    # ------------------------------------------------------------------------

    def post(self, request):

        organization, error = (
            _resolve_organization_for_org_admin_screen(
                request
            )
        )

        if error:
            return error

        serializer = (
            OrgStage2SettingToggleSerializer(
                data=request.data
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        OrgStage2Setting.objects.update_or_create(

            organization=organization,

            doc_type=data["doc_type"],

            defaults={

                "skip_stage2": (
                    data["skip_stage2"]
                ),

                "updated_by": (
                    request.user
                ),
            },
        )

        return Response({
            "detail": "Yadda saxlanıldı."
        })


# ============================================================================
# NOTIFICATIONS
# ============================================================================

class NotificationListView(APIView):
    permission_classes = [
        permissions.IsAuthenticated
    ]

    def get(self, request):

        qs = Notification.objects.filter(
            recipient=request.user
        )

        # --------------------------------------------------------------------
        # UNREAD FILTER
        # --------------------------------------------------------------------

        if str(
                request.query_params.get(
                    "unread",
                    ""
                )
        ).lower() in (
                "1",
                "true",
                "yes",
        ):
            qs = qs.filter(
                is_read=False
            )

        # --------------------------------------------------------------------
        # UNREAD COUNT
        # --------------------------------------------------------------------

        unread_count = (
            Notification.objects
            .filter(
                recipient=request.user,
                is_read=False,
            )
            .count()
        )

        # --------------------------------------------------------------------
        # PAGINATION
        # --------------------------------------------------------------------

        try:

            page = max(
                1,
                int(
                    request.query_params.get(
                        "page",
                        1
                    )
                )
            )

            page_size = min(
                100,
                max(
                    1,
                    int(
                        request.query_params.get(
                            "page_size",
                            50
                        )
                    )
                )
            )

        except (
                TypeError,
                ValueError,
        ):

            page = 1
            page_size = 50

        # --------------------------------------------------------------------
        # TOTAL
        # --------------------------------------------------------------------

        total = qs.count()

        start = (
                        page - 1
                ) * page_size

        page_qs = qs[
            start:start + page_size
        ]

        # --------------------------------------------------------------------
        # RESPONSE
        # --------------------------------------------------------------------

        return Response({

            "unread_count": unread_count,

            "count": total,

            "page": page,

            "page_size": page_size,

            "has_next": (
                    start + page_size < total
            ),

            "results": NotificationSerializer(
                page_qs,
                many=True
            ).data,
        })


# ============================================================================
# NOTIFICATION MARK READ
# ============================================================================

class NotificationMarkReadView(APIView):
    permission_classes = [
        permissions.IsAuthenticated
    ]

    def post(self, request, pk=None):
        # --------------------------------------------------------------------
        # READ ALL
        # --------------------------------------------------------------------

        if pk in (
                None,
                0,
                "0",
        ):
            (
                Notification.objects
                .filter(
                    recipient=request.user,
                    is_read=False,
                )
                .update(
                    is_read=True
                )
            )

            return Response({
                "detail": (
                    "Bütün bildirişlər "
                    "oxunmuş kimi işarələndi."
                )
            })

        # --------------------------------------------------------------------
        # SINGLE
        # --------------------------------------------------------------------

        notification = get_object_or_404(
            Notification,
            pk=pk,
            recipient=request.user,
        )

        notification.is_read = True

        notification.save(
            update_fields=[
                "is_read"
            ]
        )

        return Response({
            "detail": (
                "Oxunmuş kimi işarələndi."
            )
        })
