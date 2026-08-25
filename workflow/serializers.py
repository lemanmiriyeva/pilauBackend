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
        allow_null=True,
    )

    organization_stage1_approvers = serializers.ListField(
        required=False,
        allow_empty=True,
        child=serializers.DictField(),
    )

    stage2_enabled = serializers.BooleanField(
        required=False,
        default=True,
    )

    stage2_user = serializers.IntegerField(
        required=False,
        allow_null=True,
    )

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "body", "link", "is_read", "created_at"]

class OrganizationStage1ApproverSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField()
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,
    )