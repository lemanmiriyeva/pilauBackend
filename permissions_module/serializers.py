from rest_framework import serializers

from .models import Module, UserModulePermission


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ["id", "parent", "key", "title", "description", "meta", "icon", "order"]


class UserModulePermissionSerializer(serializers.ModelSerializer):
    module_title = serializers.CharField(source="module.title", read_only=True)
    user_full_name = serializers.SerializerMethodField()

    class Meta:
        model = UserModulePermission
        fields = [
            "id", "user", "user_full_name", "module", "module_title",
            "can_view", "can_edit", "can_approve",
            "granted_by", "granted_at", "updated_at",
        ]
        read_only_fields = ["granted_by", "granted_at", "updated_at"]

    def get_user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username


class GrantPermissionsSerializer(serializers.Serializer):
    user = serializers.IntegerField()
    modules = serializers.ListField(child=serializers.DictField())

    def validate_modules(self, value):
        # her element: {"module": <id>, "can_view": bool, "can_edit": bool, "can_approve": bool}
        for item in value:
            if "module" not in item:
                raise serializers.ValidationError("Hər modul üçün 'module' id-si tələb olunur.")
        return value