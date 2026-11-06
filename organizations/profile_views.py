"""Təşkilatın təfərrüat (profil) səhifəsi üçün API-lər.

GET   /api/organizations/<id>/profile/                 - ümumi məlumat + say göstəriciləri + can_edit
GET   /api/organizations/<id>/employees/               - təşkilatın işçiləri (sistem istifadəçiləri)
POST  /api/organizations/<id>/employees/               - yeni işçi əlavə et (ilkin şifrə ilə; departament/vəzifə ilə)
PATCH /api/organizations/<id>/employees/<user_id>/     - işçini redaktə et
(nomenklatura endpoint-ləri: bax nomenclature_views.py)
GET   /api/organizations/<id>/permit-documents/?group=license|permit
GET   /api/organizations/<id>/activity-documents/      - fəaliyyətə dair sənədlər
POST  /api/organizations/<id>/activity-documents/      - sənəd yüklə (multipart: title, file)
DEL   /api/organizations/activity-documents/<pk>/
GET   /api/organizations/activity-documents/<pk>/download/

Görmək: scoped_organization_ids (Nazirlik admini hamısını, qurum admini/işçi öz əhatəsini).
Yazma hüququ (bax can_org_action): Nazirlik admini - hər təşkilatda; HƏMİN təşkilatın öz admini -
yalnız öz təşkilatında; təşkilatın digər işçiləri isə "Təşkilatlar" modulundakı icazələrinə görə:
can_create -> yeni işçi / sənəd / nomenklatura əlavə etmək, can_edit -> redaktə və silmə.
Yalnız "Baxış" icazəsi olan istifadəçi (və başqa təşkilata baxan MSN admini/rəhbər kadr) hər şeyi
görür, amma dəyişə bilmir.
"""
from django.db import IntegrityError
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.constants import DEFAULT_INITIAL_PASSWORD
from authentication.models import User

from .models import Organization, OrganizationDocument
from .permissions import is_full_admin, is_org_admin, scoped_organization_ids

# Sənəd növlərinin qruplaşdırılması (bax licenses.field_schema.DOC_TYPES)
LICENSE_DOC_TYPES = ("xususi_lisenziya", "umumi_lisenziya", "istehsal")
PERMIT_DOC_TYPES = ("idxal", "ixrac", "xususi_satis", "gomrukden_azadolma", "edvden_azadolma")

# Qurum admininin öz təşkilatında dəyişə biləcəyi sahələr (qalanı - VÖEN, status, iyerarxiya və s. -
# yalnız Nazirlik admini).
ORG_ADMIN_EDITABLE_FIELDS = {
    "full_name", "director_name", "director_phone", "director_email", "address", "email", "phone",
    "state_reg_number", "notes", "departments", "authorized_persons",
}


ORG_MODULE_KEY = "teskilatlar"


def can_org_action(user, organization, action: str) -> bool:
    """action: 'create' | 'edit'. Nazirlik admini - həmişə; öz təşkilatının admini - həmişə;
    təşkilatın digər işçisi - 'Təşkilatlar' modulunda uyğun icazəsi varsa. Başqa təşkilatın
    məlumatını Nazirlik admini xaric heç kim dəyişə bilməz."""
    if is_full_admin(user):
        return True
    if not (user and user.is_authenticated) or user.organization_id != organization.id:
        return False
    if is_org_admin(user):
        return True
    from permissions_module.models import UserModulePermission
    return UserModulePermission.objects.filter(
        user=user, module__key=ORG_MODULE_KEY, **{f"can_{action}": True},
    ).exists()


def can_edit_organization(user, organization) -> bool:
    return can_org_action(user, organization, "edit")


def get_visible_organization(request, pk) -> Organization:
    organization = get_object_or_404(Organization, pk=pk)
    org_ids = scoped_organization_ids(request.user)
    if org_ids is not None and organization.id not in org_ids:
        raise PermissionDenied("Bu təşkilatın məlumatına baxmaq hüququnuz yoxdur.")
    return organization


def _full_name(user) -> str:
    return f"{user.first_name} {user.last_name}".strip() or user.username


class OrganizationProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        from licenses.models import PermitDocument

        org = get_visible_organization(request, pk)
        docs = PermitDocument.objects.filter(organization=org)
        return Response({
            "id": org.id,
            "full_name": org.full_name,
            "code": org.code,
            "voen": org.voen,
            "state_reg_number": org.state_reg_number,
            "director_name": org.director_name,
            "director_phone": org.director_phone,
            "director_email": org.director_email,
            "address": org.address,
            "email": org.email,
            "phone": org.phone,
            "is_active": org.is_active,
            "parent": org.parent_id,
            "parent_name": org.parent.full_name if org.parent_id else None,
            "notes": org.notes,
            "created_at": org.created_at,
            "employee_count": org.users.count(),
            "license_count": docs.filter(doc_type__in=LICENSE_DOC_TYPES).count(),
            "permit_count": docs.filter(doc_type__in=PERMIT_DOC_TYPES).count(),
            "activity_document_count": org.activity_documents.count(),
            "nomenclature_count": org.nomenclatures.count(),
            "partner_count": org.partner_companies.count(),
            "subordinate_count": org.subordinates.count(),
            "equipment_count": org.fixed_assets.count(),
            "can_create": can_org_action(request.user, org, "create"),
            "can_edit": can_org_action(request.user, org, "edit"),
            "can_delete": can_org_action(request.user, org, "delete"),
            "can_edit_all_fields": is_full_admin(request.user),
        })


class EmployeeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "phone", "fin_kod", "department", "position"]
        extra_kwargs = {
            "first_name": {"required": True, "allow_blank": False},
            "last_name": {"required": True, "allow_blank": False},
            "email": {"required": True},
        }

    def validate(self, attrs):
        org = self.context["organization"]
        for key, label in (("department", "Departament"), ("position", "Vəzifə")):
            obj = attrs.get(key)
            if obj and obj.organization_id != org.id:
                raise serializers.ValidationError({key: f"{label} bu təşkilata aid deyil."})
        return attrs


class EmployeeUpdateSerializer(EmployeeCreateSerializer):
    """İşçinin redaktəsi - istifadəçi adı dəyişmir; aktivlik (is_active) əlavə olunur."""

    class Meta(EmployeeCreateSerializer.Meta):
        fields = ["first_name", "last_name", "email", "phone", "fin_kod", "department", "position", "is_active"]
        extra_kwargs = {
            "first_name": {"required": False},
            "last_name": {"required": False},
            "email": {"required": False},
        }


class OrganizationEmployeesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        org = get_visible_organization(request, pk)
        users = org.users.select_related("department", "position").order_by("first_name", "last_name", "username")
        return Response([
            {
                "id": u.id,
                "full_name": _full_name(u),
                "username": u.username,
                "email": u.email,
                "phone": u.phone,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "department": u.department.name if u.department_id else None,
                "department_id": u.department_id,
                "position": u.position.name if u.position_id else None,
                "position_id": u.position_id,
                "is_org_admin": u.is_org_admin,
                "is_active": u.is_active,
            }
            for u in users
        ])

    def post(self, request, pk):
        org = get_visible_organization(request, pk)
        if not can_org_action(request.user, org, "create"):
            raise PermissionDenied("İşçi əlavə etmək üçün 'Yaratma' icazəniz yoxdur.")
        serializer = EmployeeCreateSerializer(data=request.data, context={"organization": org})
        serializer.is_valid(raise_exception=True)
        try:
            user = User(**serializer.validated_data, organization=org)
            user.set_password(DEFAULT_INITIAL_PASSWORD)
            user.must_change_password = True  # ilk girişdə yeni şifrə təyin edəcək
            user.save()
        except IntegrityError:
            return Response({"detail": "Bu istifadəçi adı və ya e-poçt artıq mövcuddur."}, status=400)
        return Response({"id": user.id, "full_name": _full_name(user), "username": user.username}, status=201)


class OrganizationEmployeeDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk, user_id):
        org = get_visible_organization(request, pk)
        if not can_org_action(request.user, org, "edit"):
            raise PermissionDenied("İşçini redaktə etmək üçün 'Redaktə' icazəniz yoxdur.")
        employee = get_object_or_404(User, pk=user_id, organization=org)
        # Nazirlik/staff hesabları bu yolla dəyişdirilmir.
        if (employee.is_staff or employee.is_superuser) and not is_full_admin(request.user):
            raise PermissionDenied("Bu istifadəçini redaktə etmək hüququnuz yoxdur.")
        serializer = EmployeeUpdateSerializer(
            employee, data=request.data, partial=True, context={"organization": org},
        )
        serializer.is_valid(raise_exception=True)
        if employee.id == request.user.id and serializer.validated_data.get("is_active") is False:
            raise PermissionDenied("Öz hesabınızı deaktiv edə bilməzsiniz.")
        serializer.save()
        return Response({"id": employee.id, "full_name": _full_name(employee)})


class OrganizationPermitDocumentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        from licenses.field_schema import DOC_TYPES
        from licenses.models import PermitDocument

        org = get_visible_organization(request, pk)
        group = request.query_params.get("group")
        qs = PermitDocument.objects.filter(organization=org)
        if group == "license":
            qs = qs.filter(doc_type__in=LICENSE_DOC_TYPES)
        elif group == "permit":
            qs = qs.filter(doc_type__in=PERMIT_DOC_TYPES)
        labels = dict(DOC_TYPES)
        return Response([
            {
                "id": d.id,
                "number": d.number,
                "title": d.title,
                "doc_type": d.doc_type,
                "category": labels.get(d.doc_type, d.doc_type),
                "status": d.status,
                "issue_date": d.issue_date,
                "expiry_date": d.expiry_date,
                "created_at": d.created_at,
            }
            for d in qs.order_by("-created_at")[:500]
        ])


def _num(value):
    """form_data-dakı say/miqdarı rəqəmə çevirir; boş və ya yanlışdırsa None."""
    try:
        if value in (None, ""):
            return None
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


class OrganizationTurnoverView(APIView):
    """Təşkilatın dövriyyəsi: xarici (idxal/ixrac) və yerli (daxili satış) sənədlər.

    GET /api/organizations/<id>/turnover/

    İLKİN VERSİYA - təsnifat qaydası (dəqiqləşdiriləndə yalnız _classify dəyişəcək):
      - doc_type == 'idxal'  -> xarici / idxal
      - doc_type == 'ixrac'  -> xarici / ixrac
      - doc_type == 'xususi_satis' və form_data['satis_novu']:
            'idxal' / 'ixrac' -> xarici, 'daxili_satis' -> yerli
    Miqdar sahələri (tesdiq_olunan_say / faktiki_miqdar / qaliq) hələ avtomatik
    doldurulmur - yoxdursa None qaytarılır, frontend '—' göstərir.
    """
    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _classify(doc):
        fd = doc.form_data or {}
        if doc.doc_type in ("idxal", "ixrac"):
            return "xarici", doc.doc_type
        if doc.doc_type == "xususi_satis":
            kind = fd.get("satis_novu")
            if kind == "daxili_satis":
                return "yerli", "daxili_satis"
            if kind in ("idxal", "ixrac"):
                return "xarici", kind
        return None, None

    def get(self, request, pk):
        from licenses.models import PermitDocument

        org = get_visible_organization(request, pk)
        qs = PermitDocument.objects.filter(
            organization=org, doc_type__in=("idxal", "ixrac", "xususi_satis"),
        ).order_by("-created_at")[:500]

        rows = []
        for d in qs:
            scope, direction = self._classify(d)
            if not scope:
                continue
            fd = d.form_data or {}
            approved = _num(fd.get("tesdiq_olunan_say"))
            actual = _num(fd.get("faktiki_miqdar"))
            remaining = _num(fd.get("qaliq"))
            if remaining is None and approved is not None and actual is not None:
                remaining = approved - actual
            rows.append({
                "id": d.id,
                "number": d.number,
                "doc_type": d.doc_type,
                "scope": scope,                      # 'xarici' | 'yerli'
                "direction": direction,              # 'idxal' | 'ixrac' | 'daxili_satis'
                "product": fd.get("mehsul") or fd.get("malin_tesviri") or d.title or "",
                "approved_qty": approved,
                "actual_qty": actual,
                "remaining_qty": remaining,
                "status": d.status,
                "issue_date": d.issue_date,
            })

        def _sum(items, key):
            vals = [r[key] for r in items if r[key] is not None]
            return sum(vals) if vals else None

        summary = {}
        for scope in ("xarici", "yerli"):
            items = [r for r in rows if r["scope"] == scope]
            summary[scope] = {
                "count": len(items),
                "approved_qty": _sum(items, "approved_qty"),
                "actual_qty": _sum(items, "actual_qty"),
                "remaining_qty": _sum(items, "remaining_qty"),
            }
        return Response({"summary": summary, "results": rows})

def _document_payload(doc):
    return {
        "id": doc.id,
        "title": doc.title,
        "filename": doc.file.name.rsplit("/", 1)[-1] if doc.file else "",
        "created_at": doc.created_at,
        "uploaded_by": _full_name(doc.uploaded_by) if doc.uploaded_by_id else None,
    }


class OrganizationActivityDocumentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    MAX_SIZE = 15 * 1024 * 1024

    def get(self, request, pk):
        org = get_visible_organization(request, pk)
        return Response([_document_payload(d) for d in org.activity_documents.select_related("uploaded_by")])

    def post(self, request, pk):
        org = get_visible_organization(request, pk)
        if not can_org_action(request.user, org, "create"):
            raise PermissionDenied("Sənəd yükləmək üçün 'Yaratma' icazəniz yoxdur.")
        title = (request.data.get("title") or "").strip()
        upload = request.FILES.get("file")
        if not title:
            return Response({"title": "Sənədin adı tələb olunur."}, status=400)
        if not upload:
            return Response({"file": "Fayl seçilməyib."}, status=400)
        if upload.size > self.MAX_SIZE:
            return Response({"file": "Fayl 15 MB-dan böyük ola bilməz."}, status=400)
        doc = OrganizationDocument.objects.create(
            organization=org, title=title, file=upload, uploaded_by=request.user,
        )
        return Response(_document_payload(doc), status=201)


class OrganizationActivityDocumentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        doc = get_object_or_404(OrganizationDocument, pk=pk)
        org = get_visible_organization(request, doc.organization_id)
        if not can_org_action(request.user, org, "delete"):
            raise PermissionDenied("Bu sənədi silmək üçün 'Silmə' icazəniz yoxdur.")
        doc.file.delete(save=False)
        doc.delete()
        return Response(status=204)


class OrganizationActivityDocumentDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        doc = get_object_or_404(OrganizationDocument, pk=pk)
        get_visible_organization(request, doc.organization_id)
        return FileResponse(doc.file.open("rb"), as_attachment=True, filename=doc.file.name.rsplit("/", 1)[-1])


