from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import AuthorizedPerson
from organizations.permissions import scoped_organization_ids
from permissions_module.models import Module, has_module_permission

from licenses.field_schema import DOC_TYPES, get_schema
from licenses.models import ApprovalSettings, PermitDocument, PermitDocumentFile
from licenses.serializers import (
    ApprovalSettingsSerializer,
    PermitDocumentCreateSerializer,
    PermitDocumentDetailSerializer,
    PermitDocumentListSerializer,
)

FILE_FIELD_PREFIX = "file__"


def _approval_module(stage):
    """'tesdiq-merhele-1' / 'tesdiq-merhele-2' - bax seed_modules_shell.py."""
    return Module.objects.filter(key=f"tesdiq-merhele-{stage}", parent__isnull=True).first()


def _user_can_approve(user, stage) -> bool:
    if user.is_superuser:
        return True
    module = _approval_module(stage)
    return bool(module) and has_module_permission(user, module.id, "approve")


def _user_is_any_approver(user) -> bool:
    return user.is_superuser or _user_can_approve(user, 1) or _user_can_approve(user, 2)


class PermitDocumentSchemaView(APIView):
    """Frontend forması bu endpoint-dən sahə siyahısını (fayl + manual) alır.
    GET /api/licenses/permit-documents/schema/?doc_type=ixrac|idxal
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        doc_type = request.query_params.get("doc_type")
        if doc_type not in dict(DOC_TYPES):
            return Response({"detail": "doc_type 'ixrac' və ya 'idxal' olmalıdır."}, status=400)
        return Response(get_schema(doc_type))


class ApprovalSettingsView(APIView):
    """Qlobal tənzimləmə: mərhələli təsdiq açıq/qapalıdır (bax ApprovalSettings, PermitDocument.save).
    GET - istənilən authenticated istifadəçi (create formu düymə mətnini seçmək üçün oxuyur).
    PATCH - yalnız admin/superuser dəyişdirə bilər."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(ApprovalSettingsSerializer(ApprovalSettings.get_solo()).data)

    def patch(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"detail": "Bu əməliyyat üçün icazəniz yoxdur."}, status=403)
        settings_obj = ApprovalSettings.get_solo()
        serializer = ApprovalSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class ApplicantInfoView(APIView):
    """Image 3/4 - 'Müraciətçi məlumatları' bölməsini avtomatik doldurmaq üçün
    cari istifadəçinin təşkilatı və səlahiyyətli şəxslər siyahısı."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org = request.user.organization
        if not org:
            return Response({"organization": None, "authorized_persons": []})

        # Meta.ordering ("person_type", "full_name") "əsas" şəxsi siyahının başına gətirir.
        persons = AuthorizedPerson.objects.filter(organization=org)
        return Response({
            "organization": {
                "id": org.id,
                "full_name": org.full_name,
                "voen": org.voen,
                "code": org.code,
            },
            "authorized_persons": [
                {
                    "id": p.id, "person_type": p.person_type, "full_name": p.full_name,
                    "fin_kod": p.fin_kod, "department": p.department, "position": p.position,
                    "email": p.email, "phone": p.phone,
                } for p in persons
            ],
        })


class PermitDocumentViewSet(viewsets.ModelViewSet):
    """İdxal/İxrac icazə sənədləri - Image 1 siyahısı və Image 2/3/4 yaratma axını."""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = PermitDocument.objects.select_related("organization", "authorized_person").prefetch_related("files")

    def get_serializer_class(self):
        if self.action == "list":
            return PermitDocumentListSerializer
        if self.action == "create":
            return PermitDocumentCreateSerializer
        return PermitDocumentDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Təhlükəsizlik: staff/superuser və mərhələli təsdiq icazəsi olanlar (approver-lər)
        # bütün təşkilatların sənədlərini görür (rəy vermək üçün lazımdır), digərləri yalnız
        # öz təşkilatının (+ alt-təşkilatlarının) sənədlərini.
        if not _user_is_any_approver(user):
            org_ids = scoped_organization_ids(user)
            if org_ids is not None:
                qs = qs.filter(organization_id__in=org_ids)

        approval_stage_param = self.request.query_params.get("approval_stage")
        if approval_stage_param:
            # Təsdiq növbəsi (bax /modullar/tesdiq/merhele-1|2) - yalnız həmin mərhələdə
            # təsdiq icazəsi olanlar görə bilər, gözləyən sənədlərlə məhdudlaşdırılır.
            if not _user_can_approve(user, approval_stage_param):
                return qs.none()
            qs = qs.filter(status="gozleyir", approval_stage=approval_stage_param)

        doc_type = self.request.query_params.get("doc_type")
        status_param = self.request.query_params.get("status")
        search = self.request.query_params.get("search")
        if doc_type:
            # Bir neçə növü vergüllə ayıraraq bir dəfəyə filtrləmək mümkündür,
            # məs. 'ixrac,idxal' - bax idxal-ixrac/page.js.
            qs = qs.filter(doc_type__in=[t.strip() for t in doc_type.split(",") if t.strip()])
        if status_param:
            qs = qs.filter(status=status_param)
        if search:
            qs = qs.filter(title__icontains=search) | qs.filter(number__icontains=search)
        return qs

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Cari mərhələni təsdiqləyir. Body: {"comment": "..."} (könüllü)."""
        document = self.get_object()
        if not _user_can_approve(request.user, document.approval_stage):
            return Response({"detail": "Bu əməliyyat üçün icazəniz yoxdur."}, status=403)
        if document.status != "gozleyir":
            return Response({"detail": "Bu sənəd artıq yoxlanılıb."}, status=400)

        document.approve_stage(request.user, request.data.get("comment", ""))
        out = PermitDocumentDetailSerializer(document, context={"request": request})
        return Response(out.data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Sənədi rədd edir. Body: {"reason": "..."} (məcburidir)."""
        document = self.get_object()
        if not _user_can_approve(request.user, document.approval_stage):
            return Response({"detail": "Bu əməliyyat üçün icazəniz yoxdur."}, status=403)
        if document.status != "gozleyir":
            return Response({"detail": "Bu sənəd artıq yoxlanılıb."}, status=400)

        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"detail": "Rədd səbəbi tələb olunur."}, status=400)

        document.reject(request.user, reason)
        out = PermitDocumentDetailSerializer(document, context={"request": request})
        return Response(out.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_confidential = str(request.data.get("is_confidential", "")).lower() in ("true", "1", "yes")
        doc_type = serializer.validated_data.get("doc_type")
        schema = get_schema(doc_type)
        labels_by_key = {f["key"]: f["label"] for f in schema["file_fields"]}

        if not is_confidential:
            missing_files = [
                f["label"] for f in schema["file_fields"]
                if f.get("required") and f"{FILE_FIELD_PREFIX}{f['key']}" not in request.FILES
            ]
            if missing_files:
                return Response(
                    {"detail": f"Bu sənədlər tələb olunur: {', '.join(missing_files)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        document = serializer.save()

        for key, uploaded_file in request.FILES.items():
            if not key.startswith(FILE_FIELD_PREFIX):
                continue
            field_key = key[len(FILE_FIELD_PREFIX):]
            PermitDocumentFile.objects.create(
                document=document, field_key=field_key,
                field_label=labels_by_key.get(field_key, field_key),
                file=uploaded_file, original_name=uploaded_file.name,
            )

        out = PermitDocumentDetailSerializer(document, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)