from rest_framework import serializers

from licenses.field_schema import DOC_TYPES


class PermissionToggleSerializer(serializers.Serializer):
    """Bir istifadəçi + bir kateqoriya üçün tək icazə sətrini yaradır/yeniləyir."""
    user = serializers.IntegerField()
    doc_type = serializers.ChoiceField(choices=DOC_TYPES)
    value = serializers.BooleanField()