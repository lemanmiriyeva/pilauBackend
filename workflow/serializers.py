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


class OrganizationStage1ApproverEntrySerializer(serializers.Serializer):
    organization_id = serializers.IntegerField()
    user_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


class WorkflowConfigUpdateSerializer(serializers.Serializer):
    """PUT /api/workflow/workflow-config/ body-su - tək bir doc_type-ın axınını yeniləyir."""
    doc_type = serializers.ChoiceField(choices=DOC_TYPES)
    stage1_mode = serializers.ChoiceField(choices=DocumentWorkflowConfig.STAGE1_CHOICES)
    stage1_user = serializers.IntegerField(required=False, allow_null=True)
    stage2_enabled = serializers.BooleanField(required=False, default=True)
    stage2_user = serializers.IntegerField(required=False, allow_null=True)
    organization_stage1_approvers = OrganizationStage1ApproverEntrySerializer(many=True, required=False, default=list)

    def validate(self, attrs):
        if attrs["stage1_mode"] == "msn" and not attrs.get("stage1_user"):
            raise serializers.ValidationError(
                {"stage1_user": "MSN seçildikdə 1-ci mərhələ üçün icraçı seçilməlidir."}
            )

        return attrs


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "body", "link", "is_read", "created_at"]