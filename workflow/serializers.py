from rest_framework import serializers

from licenses.field_schema import DOC_TYPES
from workflow.models import DocumentWorkflowConfig, Notification


class PermissionToggleSerializer(serializers.Serializer):
    """Bir istifadəçi + bir kateqoriya üçün tək icazə sətrini yaradır/yeniləyir."""
    user = serializers.IntegerField()
    doc_type = serializers.ChoiceField(choices=DOC_TYPES)
    value = serializers.BooleanField()


class OrgStage2SettingToggleSerializer(serializers.Serializer):
    """POST /api/workflow/stage2-settings/ body-su."""
    doc_type = serializers.ChoiceField(choices=DOC_TYPES)
    skip_stage2 = serializers.BooleanField()


class WorkflowConfigUpdateSerializer(serializers.Serializer):
    doc_type = serializers.ChoiceField(choices=DOC_TYPES)

    stage1_mode = serializers.ChoiceField(
        choices=DocumentWorkflowConfig.STAGE1_CHOICES
    )

    stage1_user = serializers.IntegerField(
        required=False,
        allow_null=True
    )

    stage1_users = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        default=list,
    )

    stage2_enabled = serializers.BooleanField(
        required=False,
        default=True
    )

    stage2_user = serializers.IntegerField(
        required=False,
        allow_null=True
    )

    def validate(self, attrs):
        if attrs["stage1_mode"] == "msn":
            if not attrs.get("stage1_user"):
                raise serializers.ValidationError({
                    "stage1_user":
                        "MSN seçildikdə 1-ci mərhələ üçün icraçı seçilməlidir."
                })

        if attrs["stage1_mode"] == "qurum":
            if not attrs.get("stage1_users"):
                raise serializers.ValidationError({
                    "stage1_users":
                        "Qurum seçildikdə ən azı bir təsdiqçi seçilməlidir."
                })

        if attrs.get("stage2_enabled", True) and not attrs.get("stage2_user"):
            raise serializers.ValidationError({
                "stage2_user":
                    "2-ci mərhələ aktiv olduqda icraçı seçilməlidir."
            })

        return attrs


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "body", "link", "is_read", "created_at"]