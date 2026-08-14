from rest_framework import serializers

from licenses.field_schema import DOC_TYPES, get_schema
from licenses.models import PermitDocument, PermitDocumentFile


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
            "applicant_name", "issue_date", "expiry_date", "status",
        ]


class PermitDocumentDetailSerializer(serializers.ModelSerializer):
    """Image 3/4 - 'Bax' düyməsi ilə açılan detal görünüşü."""
    category = serializers.CharField(source="get_doc_type_display", read_only=True)
    files = PermitDocumentFileSerializer(many=True, read_only=True)

    class Meta:
        model = PermitDocument
        fields = [
            "id", "doc_type", "category", "number", "title",
            "submission_mode", "is_confidential", "form_data", "files",
            "organization", "authorized_person",
            "applicant_name", "voen", "fin_kod", "department", "position", "phone", "email",
            "issue_date", "expiry_date", "status",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "number", "created_at", "updated_at"]


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