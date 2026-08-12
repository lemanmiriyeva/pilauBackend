from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import User
from authentication.utils import get_client_ip, log_security_event

from .models import Module, UserModulePermission, get_visible_module_tree
from .serializers import (
    GrantPermissionsSerializer,
    ModuleSerializer,
    UserModulePermissionSerializer,
)


class MyModulesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(get_visible_module_tree(request.user))


class ModuleListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ModuleSerializer
    queryset = Module.objects.all()


class UserPermissionListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserModulePermissionSerializer

    def get_queryset(self):
        user_id = self.request.query_params.get("user")
        qs = UserModulePermission.objects.select_related("module", "user")
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs


class GrantPermissionsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = GrantPermissionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        target_user = get_object_or_404(User, id=data["user"])
        results = []

        for item in data["modules"]:
            module = get_object_or_404(Module, id=item["module"])
            perm, _ = UserModulePermission.objects.update_or_create(
                user=target_user,
                module=module,
                defaults={
                    "can_view": bool(item.get("can_view", False)),
                    "can_edit": bool(item.get("can_edit", False)),
                    "can_approve": bool(item.get("can_approve", False)),
                    "granted_by": request.user,
                },
            )
            results.append(perm)

        log_security_event(
            "PERMISSIONS_GRANTED", user=request.user, ip=get_client_ip(request),
            extra=f"target_user={target_user.username} modules={[r.module.key for r in results]}",
        )

        return Response(
            UserModulePermissionSerializer(results, many=True).data,
            status=status.HTTP_200_OK,
        )