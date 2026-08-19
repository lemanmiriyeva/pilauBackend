from rest_framework import serializers

from licenses.field_schema import DOC_TYPES, get_schema
from licenses.models import ApprovalSettings, LicenseCertificate, PermitDocument, PermitDocumentFile


class ApprovalSettingsSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="get_doc_type_display", read_only=True)

    class Meta:
        model = ApprovalSettings
        fields = ["doc_type", "label", "staged_approval_enabled", "updated_at"]
        read_only_fields = ["doc_type", "label", "updated_at"]


class PermitDocumentFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermitDocumentFile
        fields = ["id", "field_key", "field_label", "file", "original_name", "uploaded_at"]


class PermitDocumentListSerializer(serializers.ModelSerializer):
    """Image 1 - siyahı cədvəli üçün."""
    category = serializers.CharField(source="get_doc_type_display", read_only=True)

    class Meta:
        model = PermitDocument
        fields = [
            "id", "number", "title", "doc_type", "category",
            "applicant_name", "issue_date", "expiry_date", "status", "approval_stage",
        ]


class PermitDocumentDetailSerializer(serializers.ModelSerializer):
    """Image 3/4 - 'Bax' düyməsi ilə açılan detal görünüşü."""
    category = serializers.CharField(source="get_doc_type_display", read_only=True)
    files = PermitDocumentFileSerializer(many=True, read_only=True)
    stage1_approved_by_name = serializers.CharField(
        source="stage1_approved_by.get_full_name", read_only=True, default=""
    )
    stage2_approved_by_name = serializers.CharField(
        source="stage2_approved_by.get_full_name", read_only=True, default=""
    )
    rejected_by_name = serializers.CharField(source="rejected_by.get_full_name", read_only=True, default="")
    certificate_id = serializers.SerializerMethodField()

    class Meta:
        model = PermitDocument
        fields = [
            "id", "doc_type", "category", "number", "title",
            "submission_mode", "is_confidential", "form_data", "files",
            "organization", "authorized_person",
            "applicant_name", "voen", "fin_kod", "department", "position", "phone", "email",
            "issue_date", "expiry_date", "status",
            "approval_stage",
            "stage1_approved_by_name", "stage1_approved_at", "stage1_comment",
            "stage2_approved_by_name", "stage2_approved_at", "stage2_comment",
            "rejected_by_name", "rejected_at", "rejection_reason",
            "certificate_id",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "number", "created_at", "updated_at"]

    def get_certificate_id(self, obj):
        # Sənəd tam təsdiqlənibsə (bax PermitDocument.approve_stage) LicenseCertificate
        # OneToOne olaraq artıq mövcuddur - "Sənədə bax" düyməsi üçün frontend-ə ötürülür.
        certificate = getattr(obj, "certificate", None)
        return certificate.id if certificate else None


class PermitDocumentCreateSerializer(serializers.ModelSerializer):
    """İki müraciət üsulunu da dəstəkləyir:
    - 'file': multipart/form-data, files[<field_key>] açarları ilə göndərilir (view-da işlənir).
    - 'form': form_data JSON obyekti kimi göndərilir.
    """

    class Meta:
        model = PermitDocument
        fields = [
            "id", "doc_type", "title", "submission_mode", "is_confidential", "form_data",
            "organization", "authorized_person",
            "applicant_name", "voen", "fin_kod", "department", "position", "phone", "email",
            "issue_date", "expiry_date", "status",
            "number",
        ]
        read_only_fields = ["id", "number"]

    def validate(self, attrs):
        doc_type = attrs.get("doc_type")
        valid_types = dict(DOC_TYPES)
        if doc_type not in valid_types:
            raise serializers.ValidationError(
                {"doc_type": f"{', '.join(repr(k) for k in valid_types)} dəyərlərindən biri olmalıdır."}
            )

        schema = get_schema(doc_type)
        form_data = attrs.get("form_data") or {}
        missing = [
            f["label"] for f in schema["form_fields"]
            if f.get("required") and not f.get("auto") and not str(form_data.get(f["key"], "")).strip()
        ]
        if missing:
            raise serializers.ValidationError({"form_data": f"Bu sahələr tələb olunur: {', '.join(missing)}"})
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


class LicenseCertificateSerializer(serializers.ModelSerializer):
    """Lisenziya tam təsdiqləndikdən sonra yaranan sənəd (bax LicenseCertificate).
    Hazırda vizual şablon olmadığı üçün 'form_data' (lisenziya anketi sahələri) və onların
    sxemini ('schema') qaytarır ki, frontend generic şəkildə göstərə bilsin."""
    doc_type = serializers.CharField(source="permit_document.doc_type", read_only=True)
    category = serializers.CharField(source="permit_document.get_doc_type_display", read_only=True)
    permit_document_id = serializers.IntegerField(source="permit_document.id", read_only=True)
    permit_number = serializers.CharField(source="permit_document.number", read_only=True)
    applicant_name = serializers.CharField(source="permit_document.applicant_name", read_only=True)
    issue_date = serializers.DateField(source="permit_document.issue_date", read_only=True)
    expiry_date = serializers.DateField(source="permit_document.expiry_date", read_only=True)
    schema = serializers.SerializerMethodField()
    completed_by_name = serializers.CharField(
        source="completed_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = LicenseCertificate
        fields = [
            "id", "number", "status", "form_data", "schema",
            "doc_type", "category", "permit_document_id", "permit_number",
            "applicant_name", "issue_date", "expiry_date",
            "completed_by_name", "completed_at", "created_at",
        ]
        read_only_fields = ["id", "number", "status", "created_at"]

    def get_schema(self, obj):
        return get_schema(obj.permit_document.doc_type)["form_fields"]