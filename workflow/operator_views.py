from django.utils.dateparse import parse_date
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.constants import DEFAULT_INITIAL_PASSWORD
from authentication.models import User
from workflow.models import MsnOperator, OperatorSettings
from workflow.operators import (
    _annotated_operators, _operator_row, assign_operator, build_operators_payload, can_edit_operators,
    can_view_operator_queue, can_view_operators_page, create_operator, msn_operator_candidates,
    my_operator_status, recompute_limits, set_operator_enabled,
)


class OperatorCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    fin_kod = serializers.CharField(max_length=10, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Bu istifadəçi adı artıq mövcuddur.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Bu e-poçt artıq mövcuddur.")
        return value


class OperatorListCreateView(APIView):
    """GET  /api/workflow/operators/?date=YYYY-MM-DD - operatorlar + gün üzrə statistika (Baş admin və adi admin)
    POST /api/workflow/operators/                    - operator yarat (YALNIZ Baş admin)"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not can_view_operators_page(request.user):
            raise PermissionDenied("Operatorlar səhifəsinə baxmaq icazəniz yoxdur.")
        day = parse_date(request.query_params.get("date") or "") or timezone.localdate()
        return Response(build_operators_payload(day, request.user))

    def post(self, request):
        if not can_edit_operators(request.user):
            raise PermissionDenied("Operator yaratmaq yalnız Baş admin üçün mümkündür.")
        user_id = request.data.get("user_id")
        if user_id:
            # Mövcud MSN istifadəçisini operator təyin et (şifrəsi dəyişmir)
            operator = assign_operator(user_id, request.user)
            initial_password = None
        else:
            serializer = OperatorCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            operator = create_operator(serializer.validated_data, request.user)
            initial_password = DEFAULT_INITIAL_PASSWORD
        recompute_limits()
        cfg = OperatorSettings.get()
        row = _operator_row(next(op for op in _annotated_operators(timezone.localdate()) if op.id == operator.id), cfg)
        if initial_password:
            row["initial_password"] = initial_password
        return Response(row, status=status.HTTP_201_CREATED)


class OperatorCandidatesView(APIView):
    """GET /api/workflow/operators/candidates/ - operator təyin oluna biləcək MSN istifadəçiləri (YALNIZ Baş admin)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not can_edit_operators(request.user):
            raise PermissionDenied("Operator təyin etmək yalnız Baş admin üçün mümkündür.")
        return Response([
            {
                "id": u.id,
                "full_name": f"{u.first_name} {u.last_name}".strip() or u.username,
                "username": u.username,
                "email": u.email,
                "phone": u.phone,
                "department_name": u.department.name if u.department_id else "",
                "position_name": u.position.name if u.position_id else "",
            }
            for u in msn_operator_candidates()
        ])


class OperatorDetailView(APIView):
    """PATCH  /api/workflow/operators/<id>/ {is_enabled: bool} - əl ilə aç / söndür (YALNIZ Baş admin)
    DELETE /api/workflow/operators/<id>/                    - operatorluğu götür (istifadəçi qalır)"""
    permission_classes = [permissions.IsAuthenticated]

    def _get(self, request, pk):
        if not can_edit_operators(request.user):
            raise PermissionDenied("Operatorları redaktə etmək yalnız Baş admin üçün mümkündür.")
        return MsnOperator.objects.filter(pk=pk, is_active=True).select_related("user").first()

    def patch(self, request, pk):
        operator = self._get(request, pk)
        if operator is None:
            return Response({"detail": "Operator tapılmadı."}, status=404)
        if "is_enabled" not in request.data:
            return Response({"detail": "is_enabled göndərilməlidir."}, status=400)
        raw = request.data.get("is_enabled")
        enabled = raw if isinstance(raw, bool) else str(raw).lower() in ("true", "1", "yes")
        set_operator_enabled(operator, enabled)
        return Response({"id": operator.id, "is_enabled": operator.is_enabled,
                         "disabled_reason": operator.disabled_reason})

    def delete(self, request, pk):
        operator = self._get(request, pk)
        if operator is None:
            return Response({"detail": "Operator tapılmadı."}, status=404)
        operator.is_active = False
        operator.save(update_fields=["is_active"])
        recompute_limits()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OperatorSettingsView(APIView):
    """GET/PUT /api/workflow/operators/settings/ {max_per_round} - dövr limiti (yazma: YALNIZ Baş admin)"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not can_view_operators_page(request.user):
            raise PermissionDenied("İcazəniz yoxdur.")
        cfg = OperatorSettings.get()
        return Response({"max_per_round": cfg.max_per_round, "round_number": cfg.round_number})

    def put(self, request):
        if not can_edit_operators(request.user):
            raise PermissionDenied("Limiti yalnız Baş admin dəyişə bilər.")
        try:
            value = int(request.data.get("max_per_round"))
        except (TypeError, ValueError):
            return Response({"detail": "Limit tam ədəd olmalıdır."}, status=400)
        if not 1 <= value <= 1000:
            return Response({"detail": "Limit 1 ilə 1000 arasında olmalıdır."}, status=400)
        cfg = OperatorSettings.get()
        cfg.max_per_round = value
        cfg.updated_by = request.user
        cfg.save()
        recompute_limits()
        cfg.refresh_from_db()
        return Response({"max_per_round": cfg.max_per_round, "round_number": cfg.round_number})


class OperatorQueueView(APIView):
    """GET /api/workflow/operator-queue/ - operator yoxlamasını gözləyən sənədlər (köhnədən yeniyə)
    + 'me': cari istifadəçinin limit/status paneli."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from licenses.models import PermitDocument

        if not can_view_operator_queue(request.user):
            raise PermissionDenied("Operator yoxlaması səhifəsinə icazəniz yoxdur.")
        docs = (
            PermitDocument.objects.filter(status="yoxlamada")
            .select_related("organization").order_by("submitted_at", "created_at")[:300]
        )
        return Response({
            "me": my_operator_status(request.user),
            "results": [
                {
                    "id": d.id,
                    "number": d.number,
                    "title": d.title,
                    "doc_type": d.doc_type,
                    "category": d.get_doc_type_display(),
                    "applicant_name": d.applicant_name,
                    "organization_name": d.organization.full_name if d.organization_id else "",
                    "submitted_at": d.submitted_at or d.created_at,
                    "files_count": d.files.count(),
                }
                for d in docs
            ],
        })