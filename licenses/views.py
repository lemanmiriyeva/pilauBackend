from datetime import timedelta

from django.db import models
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncMonth, TruncYear
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import AuthorizedPerson
from organizations.permissions import scoped_organization_ids

from licenses.certificate_pdf import build_certificate_pdf
from licenses.field_schema import DOC_TYPES, get_schema
from licenses.models import ApprovalSettings, LicenseCertificate, PermitDocument, PermitDocumentFile
from licenses.serializers import (
    ApprovalSettingsSerializer,
    LicenseCertificateSerializer,
    PermitDocumentCreateSerializer,
    PermitDocumentDetailSerializer,
    PermitDocumentListSerializer,
    SignCertificateSerializer,
)
from workflow.models import DocumentWorkflowConfig, OrgReviewerPermission
from workflow.notify import notify_certificate_ready, notify_stage1_reviewers, notify_stage2_reviewer

FILE_FIELD_PREFIX = "file__"

DOC_TYPES_PAYLOAD = [{"key": key, "label": label} for key, label in DOC_TYPES]
_GRANULARITY_TRUNC = {"day": TruncDate, "month": TruncMonth, "year": TruncYear}

# doc_type (licenses.field_schema.DOC_TYPES açarı) -> permissions_module.Module.key.
# İxrac və idxal eyni "idxal-ixrac" modulunun altındadır (bax seed_modules_shell.py).
DOC_TYPE_MODULE_KEY = {
    "ixrac": "idxal-ixrac",
    "idxal": "idxal-ixrac",
    "istehsal": "istehsal",
    "xususi_satis": "xususi-satis",
    "edv_guzest": "edv-guzesti",
}


def _can_create_doc_type(user, doc_type: str) -> bool:
    """İstifadəçinin bu sənəd növü üçün 'Yaratma' (can_create) icazəsi olub-olmadığını yoxlayır.
    Tam admin/qurum admini/istənilən mərhələdə təsdiq hüququ olanlar üçün məhdudiyyət yoxdur -
    bu, yalnız 'İcazələr'də konkret modul üzrə açıq şəkildə can_create verilmiş adi işçilər
    üçün əlavə maneədir (bax permissions_module - "hansı modulda create edə bilər")."""
    if user.is_superuser or user.is_staff or getattr(user, "is_org_admin", False):
        return True
    from permissions_module.models import Module, has_module_permission

    module_key = DOC_TYPE_MODULE_KEY.get(doc_type)
    if not module_key:
        return True
    module = Module.objects.filter(key=module_key).first()
    if not module:
        return True
    return has_module_permission(user, module.id, "create")


def _workflow_configs():
    return {c.doc_type: c for c in DocumentWorkflowConfig.objects.all()}


def _user_can_approve_document(user, document, config=None) -> bool:
    """Konkret sənədin hazırkı mərhələsini bu istifadəçi təsdiqləyə/rədd edə bilərmi?

    Marşrutlama DocumentWorkflowConfig-dən gəlir (bax 'Təsdiq axını' ekranı):
      - 1-ci mərhələ, rejim='qurum' (defolt): sənədin öz təşkilatının admini.
      - 1-ci mərhələ, rejim='msn': yalnız config.stage1_user.
      - 2-ci mərhələ: yalnız config.stage2_user (həmişə MSN tərəfindən təyin olunur).
    """
    if user.is_superuser:
        return True
    if config is None:
        config = DocumentWorkflowConfig.objects.filter(doc_type=document.doc_type).first()

    if document.approval_stage == 1:
        if config and config.stage1_mode == "msn":
            return bool(config.stage1_user_id) and config.stage1_user_id == user.id
        return user.id in OrgReviewerPermission.eligible_user_ids(document.organization_id, document.doc_type)

    return bool(config) and config.stage2_user_id == user.id


def _user_is_any_approver(user) -> bool:
    """Sənədlərin siyahısını (bütün təşkilatlar üzrə) görməli olan istifadəçidirmi - yəni
    hər hansı sənəd növü üzrə 1-ci (MSN rejimi) və ya 2-ci mərhələ icraçısı təyin edilibmi."""
    if user.is_superuser or user.is_staff:
        return True
    return DocumentWorkflowConfig.objects.filter(
        models.Q(stage1_user=user) | models.Q(stage2_user=user)
    ).exists()


class LicenseCertificateView(viewsets.ReadOnlyModelViewSet):
    """Lisenziya tam təsdiqləndikdən (2-ci mərhələ) sonra avtomatik yaranan rəsmi sənəd qeydi.
    Görüntü hazırda generic-dir (bax LicenseCertificateSerializer.schema) - real vizual şablon
    təqdim ediləndə buradan render ediləcək.

    GET  /api/licenses/certificates/            - cari istifadəçinin görə bildiyi sənədlər
    GET  /api/licenses/certificates/<id>/        - tək sənəd (schema + form_data ilə)
    POST /api/licenses/certificates/<id>/complete/ - 'Tamamlandı' düyməsi. Sənəd bunsuz da
         yaradılıb (bax PermitDocument.approve_stage) - bu, sadəcə istifadəçinin sənədi
         nəzərdən keçirib təsdiqlədiyini qeyd edir, LicenseCertificate-i YENİDƏN YARATMIR.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LicenseCertificateSerializer
    queryset = LicenseCertificate.objects.select_related("permit_document", "permit_document__organization")

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Superuser / staff -> bütün sertifikatlar
        if user.is_superuser or user.is_staff:
            return qs

        # Approver -> bütün sertifikatlar
        if _user_is_any_approver(user):
            return qs

        # 'Sənədlərim' - qurum admini olub-olmamasından asılı olmayaraq HƏR İSTİFADƏÇİ yalnız
        # ÖZ yaratdığı sənədlərdən yaranan sertifikatları görür (təşkilatın digər sənədləri
        # üçün bax PermitDocumentViewSet - istehsal/idxal-ixrac/xüsusi-satış/ƏDV-güzəşt
        # siyahıları təşkilat üzrə geniş əhatəlidir, amma 'Sənədlərim' fərqli, şəxsi bir görünüşdür).
        return qs.filter(permit_document__created_by=user)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        certificate = self.get_object()
        if certificate.status != "tamamlandi":
            certificate.mark_completed(request.user)
        return Response(LicenseCertificateSerializer(certificate).data)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """Sənədi PDF formatında qaytarır (bax licenses.certificate_pdf).
        ?download=1 versə 'Content-Disposition: attachment', əks halda brauzerdə (iframe)
        birbaşa göstərilə bilən 'inline' cavab qaytarılır."""
        certificate = self.get_object()
        pdf_bytes = build_certificate_pdf(certificate)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        disposition = "attachment" if request.query_params.get("download") else "inline"
        response["Content-Disposition"] = f'{disposition}; filename="{certificate.number}.pdf"'
        return response

    @action(detail=True, methods=["post"])
    def sign(self, request, pk=None):
        """Sənədi SİM İmza / Asan İmza ilə imzalayır.

        !!! MOCK - real şlüz inteqrasiya EDİLMƏYİB !!! Hazırda yalnız telefon nömrəsini
        doğrulayıb sənədi imzalanmış kimi işarələyir. Real inteqrasiya üçün lazımdır:
          - SİM İmza: mobil operatorun (Azercell/Bakcell/Nar) SOAP/REST şlüzü, təşkilat
            üçün əldə edilmiş API təsdiqi/sertifikat.
          - Asan İmza: DTX-in Asan İmza API-si (https://asanimza.az), müraciət olunmuş
            inteqrasiya sazişi + client sertifikatı.
        Hər iki halda əsl axın asinxrondur (istifadəçi telefonunda PIN təsdiqləyir, bu
        müddətdə status 'pending' olur, sonra webhook/polling ilə yekunlaşır) - bu action
        hazırda həmin gözləmə addımını simulyasiya etmədən birbaşa uğurlu nəticə qaytarır.
        """
        certificate = self.get_object()
        serializer = SignCertificateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from django.utils import timezone
        certificate.is_signed = True
        certificate.signature_method = data["method"]
        certificate.signed_phone = data["phone"]
        certificate.signed_at = timezone.now()
        certificate.save(update_fields=["is_signed", "signature_method", "signed_phone", "signed_at"])

        return Response(LicenseCertificateSerializer(certificate).data)


class PermitDocumentSchemaView(APIView):
    """Frontend forması bu endpoint-dən sahə siyahısını (fayl + manual) alır.
    GET /api/licenses/permit-documents/schema/?doc_type=<DOC_TYPES-dən biri>
    (bax: licenses/field_schema.py -> DOC_TYPES)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        doc_type = request.query_params.get("doc_type")
        if doc_type not in dict(DOC_TYPES):
            valid = ", ".join(dict(DOC_TYPES).keys())
            return Response({"detail": f"doc_type bunlardan biri olmalıdır: {valid}."}, status=400)
        return Response(get_schema(doc_type))


class ApprovalSettingsView(APIView):
    """Hər lisenziya kateqoriyası üçün AYRICA tənzimlənən keçid: mərhələli təsdiq açıq/qapalıdır
    (bax ApprovalSettings, PermitDocument.save). Bir kateqoriyanı söndürmək digərlərinə təsir etmir.

    GET  ?doc_type=istehsal  - yalnız həmin kateqoriyanın vəziyyəti (sənəd yaratma səhifəsi
                                düymə mətnini seçmək üçün istifadə edir).
    GET  (parametrsiz)       - BÜTÜN kateqoriyaların siyahısı (Təsdiq axını səhifəsindəki
                                switcher-lər üçün).
    PATCH {"doc_type": "istehsal", "staged_approval_enabled": false} - yalnız admin/superuser.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        doc_type = request.query_params.get("doc_type")
        if doc_type:
            if doc_type not in dict(DOC_TYPES):
                return Response({"detail": "doc_type düzgün göndərilməyib."}, status=400)
            return Response(ApprovalSettingsSerializer(ApprovalSettings.get_for(doc_type)).data)

        current = ApprovalSettings.all_as_dict()
        return Response([
            {"doc_type": dt, "label": label, "staged_approval_enabled": current[dt]}
            for dt, label in DOC_TYPES
        ])

    def patch(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"detail": "Bu əməliyyat üçün icazəniz yoxdur."}, status=403)

        doc_type = request.data.get("doc_type")
        if doc_type not in dict(DOC_TYPES):
            return Response({"detail": "doc_type düzgün göndərilməyib."}, status=400)

        settings_obj = ApprovalSettings.get_for(doc_type)
        serializer = ApprovalSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class ApplicantInfoView(APIView):
    """Image 3/4 - 'Müraciətçi məlumatları' bölməsini avtomatik doldurmaq üçün
    cari istifadəçinin təşkilatı və səlahiyyətli şəxslər siyahısı."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org = request.user.organization
        if not org:
            return Response({"organization": None, "authorized_persons": []})

        # Meta.ordering ("person_type", "full_name") "əsas" şəxsi siyahının başına gətirir.
        persons = AuthorizedPerson.objects.filter(organization=org)
        return Response({
            "organization": {
                "id": org.id,
                "full_name": org.full_name,
                "voen": org.voen,
                "code": org.code,
            },
            "authorized_persons": [
                {
                    "id": p.id, "person_type": p.person_type, "full_name": p.full_name,
                    "fin_kod": p.fin_kod, "department": p.department, "position": p.position,
                    "email": p.email, "phone": p.phone,
                } for p in persons
            ],
        })


class PermitDocumentViewSet(viewsets.ModelViewSet):
    """İdxal/İxrac icazə sənədləri - Image 1 siyahısı və Image 2/3/4 yaratma axını."""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = PermitDocument.objects.select_related("organization", "authorized_person").prefetch_related("files")

    def get_serializer_class(self):
        if self.action == "list":
            return PermitDocumentListSerializer
        if self.action == "create":
            return PermitDocumentCreateSerializer
        return PermitDocumentDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # 1. Superuser / staff -> bütün sənədləri görür
        if user.is_superuser or user.is_staff:
            pass

        # 2. Approver -> bütün təşkilatların sənədlərini görür
        elif _user_is_any_approver(user):
            pass

        # 3. Qurum admini VƏ adi işçi -> öz təşkilatına (VƏ alt-təşkilatlarına) məxsus bütün
        # sənədləri görür - bura onların öz yaratdıqları sənədlər də daxildir, çünki öz
        # sənədlərinin təşkilatı da eyni təşkilatdır. Fərqli olan yalnız 'Sənədlərim'
        # (bax LicenseCertificateView) - o, YALNIZ istifadəçinin öz yaratdıqlarını göstərir.
        # Təşkilatı olmayan istifadəçi (nadir hal) yalnız öz yaratdıqlarını görür.
        else:
            org_ids = scoped_organization_ids(user)
            qs = qs.filter(organization_id__in=org_ids) if org_ids else qs.filter(created_by=user)

        # ---------------------------------------------------------
        # Approval stage filter
        # ---------------------------------------------------------
        approval_stage_param = self.request.query_params.get("approval_stage")

        if approval_stage_param:
            try:
                stage = int(approval_stage_param)
            except (TypeError, ValueError):
                return qs.none()

            qs = qs.filter(
                status="gozleyir",
                approval_stage=stage
            )

            if not user.is_superuser and not user.is_staff:
                configs = _workflow_configs()

                allowed_ids = [
                    doc.id
                    for doc in qs
                    if _user_can_approve_document(
                        user,
                        doc,
                        configs.get(doc.doc_type)
                    )
                ]

                qs = qs.filter(id__in=allowed_ids)

        # ---------------------------------------------------------
        # Digər filterlər
        # ---------------------------------------------------------
        doc_type = self.request.query_params.get("doc_type")
        status_param = self.request.query_params.get("status")
        search = self.request.query_params.get("search")

        if doc_type:
            qs = qs.filter(
                doc_type__in=[
                    t.strip()
                    for t in doc_type.split(",")
                    if t.strip()
                ]
            )

        if status_param:
            qs = qs.filter(status=status_param)

        if search:
            qs = qs.filter(
                models.Q(title__icontains=search) |
                models.Q(number__icontains=search)
            )

        return qs

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Cari mərhələni təsdiqləyir. Body: {"comment": "..."} (könüllü)."""
        document = self.get_object()
        if not _user_can_approve_document(request.user, document):
            return Response({"detail": "Bu əməliyyat üçün icazəniz yoxdur."}, status=403)
        if document.status != "gozleyir":
            return Response({"detail": "Bu sənəd artıq yoxlanılıb."}, status=400)

        certificate = document.approve_stage(request.user, request.data.get("comment", ""))
        if document.status == "gozleyir" and document.approval_stage == 2:
            notify_stage2_reviewer(document)
        elif document.status == "aktiv" and certificate:
            notify_certificate_ready(document, certificate)
        out = PermitDocumentDetailSerializer(document, context={"request": request})
        return Response(out.data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Sənədi rədd edir. Body: {"reason": "..."} (məcburidir)."""
        document = self.get_object()
        if not _user_can_approve_document(request.user, document):
            return Response({"detail": "Bu əməliyyat üçün icazəniz yoxdur."}, status=403)
        if document.status != "gozleyir":
            return Response({"detail": "Bu sənəd artıq yoxlanılıb."}, status=400)

        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"detail": "Rədd səbəbi tələb olunur."}, status=400)

        document.reject(request.user, reason)
        out = PermitDocumentDetailSerializer(document, context={"request": request})
        return Response(out.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_type = serializer.validated_data.get("doc_type")
        if not _can_create_doc_type(request.user, doc_type):
            return Response(
                {"detail": "Bu kateqoriyada yeni sənəd yaratmaq üçün icazəniz yoxdur."},
                status=status.HTTP_403_FORBIDDEN,
            )

        is_confidential = str(request.data.get("is_confidential", "")).lower() in ("true", "1", "yes")
        schema = get_schema(doc_type)
        labels_by_key = {f["key"]: f["label"] for f in schema["file_fields"]}

        if not is_confidential:
            missing_files = [
                f["label"] for f in schema["file_fields"]
                if f.get("required") and f"{FILE_FIELD_PREFIX}{f['key']}" not in request.FILES
            ]
            if missing_files:
                return Response(
                    {"detail": f"Bu sənədlər tələb olunur: {', '.join(missing_files)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        document = serializer.save()

        if document.status == "gozleyir":
            notify_stage1_reviewers(document)
        elif document.status == "aktiv":
            # Bu kateqoriyada mərhələli təsdiq söndürülüb - sənəd yaradılan kimi aktiv olur,
            # ona görə sertifikat da elə burada (təsdiq addımı olmadığı üçün) yaradılır.
            certificate, _ = LicenseCertificate.objects.get_or_create(
                permit_document=document, defaults={"form_data": document.form_data}
            )
            notify_certificate_ready(document, certificate)

        for key, uploaded_file in request.FILES.items():
            if not key.startswith(FILE_FIELD_PREFIX):
                continue
            field_key = key[len(FILE_FIELD_PREFIX):]
            PermitDocumentFile.objects.create(
                document=document, field_key=field_key,
                field_label=labels_by_key.get(field_key, field_key),
                file=uploaded_file, original_name=uploaded_file.name,
            )

        out = PermitDocumentDetailSerializer(document, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

class LicenseStatsOverviewView(APIView):
    """Hesabatlar -> Statistik məlumatlar səhifəsi üçün.

    GET /api/licenses/stats/overview/?doc_type=istehsal&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&granularity=day|month|year

    - doc_type boş/göndərilməyibsə - BÜTÜN kateqoriyalar üzrə ümumi məlumat qaytarılır (əlavə
      olaraq 'by_doc_type' bölgüsü ilə - kateqoriyalar arası müqayisə üçün).
    - date_from/date_to göndərilməyibsə defolt son 12 ay istifadə olunur.
    - granularity vaxt oxunun necə qruplaşacağını təyin edir (gün/ay/il üzrə sənəd sayı).
    - Nəticə axtaran istifadəçinin əhatəsinə görə süzülür (bax scoped_organization_ids -
      Nazirlik admini/təsdiq icraçıları hamısını, qurum admini/işçi yalnız öz təşkilatının
      (və alt-təşkilatlarının) sənədlərini görür) - eyni qayda PermitDocumentViewSet-dədir.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        doc_type = (request.query_params.get("doc_type") or "").strip()
        granularity = request.query_params.get("granularity") or "month"
        if granularity not in _GRANULARITY_TRUNC:
            granularity = "month"

        valid_types = dict(DOC_TYPES)
        if doc_type and doc_type not in valid_types:
            return Response({"detail": "doc_type düzgün deyil."}, status=status.HTTP_400_BAD_REQUEST)

        today = timezone.localdate()
        date_from = parse_date(request.query_params.get("date_from") or "") or (today - timedelta(days=365))
        date_to = parse_date(request.query_params.get("date_to") or "") or today
        if date_from > date_to:
            date_from, date_to = date_to, date_from

        qs = PermitDocument.objects.filter(
            created_at__date__gte=date_from, created_at__date__lte=date_to,
        )
        if doc_type:
            qs = qs.filter(doc_type=doc_type)

        org_ids = scoped_organization_ids(user)
        if org_ids is not None:
            qs = qs.filter(organization_id__in=org_ids)

        total = qs.count()

        status_breakdown = {
            row["status"]: row["c"]
            for row in qs.values("status").annotate(c=Count("id")).order_by()
        }

        trunc = _GRANULARITY_TRUNC[granularity]
        series = [
            {
                "period": row["period"].isoformat() if hasattr(row["period"], "isoformat") else str(row["period"]),
                "count": row["c"],
            }
            for row in qs.annotate(period=trunc("created_at")).values("period").annotate(c=Count("id")).order_by("period")
        ]

        by_organization = [
            {
                "organization_id": row["organization_id"],
                "organization_name": row["organization__full_name"] or "Təşkilat təyin olunmayıb",
                "count": row["c"],
            }
            for row in (
                qs.values("organization_id", "organization__full_name")
                  .annotate(c=Count("id"))
                  .order_by("-c")
            )
        ]

        by_doc_type = []
        if not doc_type:
            dt_map = dict(DOC_TYPES)
            by_doc_type = [
                {"doc_type": row["doc_type"], "label": dt_map.get(row["doc_type"], row["doc_type"]), "count": row["c"]}
                for row in qs.values("doc_type").annotate(c=Count("id")).order_by("-c")
            ]

        return Response({
            "doc_type": doc_type or None,
            "label": valid_types.get(doc_type) if doc_type else "Bütün növlər",
            "doc_types": DOC_TYPES_PAYLOAD,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "granularity": granularity,
            "total": total,
            "status_breakdown": status_breakdown,
            "series": series,
            "by_organization": by_organization,
            "by_doc_type": by_doc_type,
        })