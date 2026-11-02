from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import User
from authentication.utils import get_client_ip, log_security_event

from organizations.permissions import IsStaffOrOrgAdmin, is_org_admin, scoped_organization_ids

from .models import (
    Module, UserModulePermission, _is_unrestricted, org_module_ids, effective_permissions, filter_grantable_modules, get_visible_module_tree,
)
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

    def get_queryset(self):
        user = self.request.user
        qs = Module.objects.all()
        org_param = self.request.query_params.get("organization")
        if user.is_superuser or user.is_staff or _is_unrestricted(user):
            if not org_param:
                return qs
            # Seçilmiş təşkilata açıq modullarla məhdudlaşdır (icazə vermə ekranı üçün)
            from organizations.models import Organization
            org = Organization.objects.filter(pk=org_param).first()
            ids = set(org_module_ids(org) or [])
            if not ids:
                return qs
        else:
            allowed = effective_permissions(user)
            ids = {mid for mid, v in allowed.items() if v.get("can_view")}
        # valideynləri də əlavə et ki, ağac düzgün qurulsun
        by_id = {m.id: m for m in qs}
        for mid in list(ids):
            m = by_id.get(mid)
            while m and m.parent_id:
                ids.add(m.parent_id)
                m = by_id.get(m.parent_id)
        return qs.filter(id__in=ids)


class UserPermissionListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserModulePermissionSerializer

    def get_queryset(self):
        user_id = self.request.query_params.get("user")
        qs = UserModulePermission.objects.select_related("module", "user")
        if user_id:
            qs = qs.filter(user_id=user_id)
        org_ids = scoped_organization_ids(self.request.user)
        if org_ids is not None:
            if is_org_admin(self.request.user):
                qs = qs.filter(user__organization_id__in=org_ids)
            else:
                qs = qs.filter(user=self.request.user)
        return qs


class GrantPermissionsView(APIView):
    permission_classes = [IsStaffOrOrgAdmin]

    def post(self, request):
        serializer = GrantPermissionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        target_user = get_object_or_404(User, id=data["user"])
        org_ids = scoped_organization_ids(request.user)
        if org_ids is not None and target_user.organization_id not in org_ids:
            return Response({"detail": "Bu istifadəçiyə icazə vermək hüququnuz yoxdur."}, status=status.HTTP_403_FORBIDDEN)
        results = []

        for item in filter_grantable_modules(request.user, data["modules"]):
            module = get_object_or_404(Module, id=item["module"])
            perm, _ = UserModulePermission.objects.update_or_create(
                user=target_user,
                module=module,
                defaults={
                    "can_view": bool(item.get("can_view", False)),
                    "can_create": bool(item.get("can_create", False)),
                    "can_edit": bool(item.get("can_edit", False)),
                    "can_approve": bool(item.get("can_approve", False)),
                    "can_delete": bool(item.get("can_delete", False)),
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