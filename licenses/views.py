from rest_framework import permissions, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import AuthorizedPerson

from licenses.field_schema import DOC_TYPES, get_schema
from licenses.models import PermitDocument, PermitDocumentFile
from licenses.serializers import (
    PermitDocumentCreateSerializer,
    PermitDocumentDetailSerializer,
    PermitDocumentListSerializer,
)

FILE_FIELD_PREFIX = "file__"


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


class ApplicantInfoView(APIView):
    """Image 3/4 - 'Müraciətçi məlumatları' bölməsini avtomatik doldurmaq üçün
    cari istifadəçinin təşkilatı və səlahiyyətli şəxslər siyahısı."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org = request.user.organization
        if not org:
            return Response({"organization": None, "authorized_persons": []})

        persons = AuthorizedPerson.objects.filter(organization=org)
        return Response({
            "organization": {
                "id": org.id,
                "full_name": org.full_name,
                "voen": org.voen,
            },
            "authorized_persons": [
                {
                    "id": p.id, "full_name": p.full_name, "fin_kod": p.fin_kod,
                    "department": p.department, "position": p.position,
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
        doc_type = self.request.query_params.get("doc_type")
        status_param = self.request.query_params.get("status")
        search = self.request.query_params.get("search")
        if doc_type:
            qs = qs.filter(doc_type=doc_type)
        if status_param:
            qs = qs.filter(status=status_param)
        if search:
            qs = qs.filter(title__icontains=search) | qs.filter(number__icontains=search)
        return qs

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