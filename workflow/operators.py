"""MSN operatorları: yoxlama (uğurlu / imtina), iş bölgüsü (dövr limiti) və statistika.

Rollar:
  - Baş admin      -> is_superuser. Hər şeyi görür və edir (operator yaradır, limit seçir, operatoru
                      söndürür/açır, özü də sənəd yoxlaya bilər - limitə tabe deyil).
  - Adi admin      -> is_staff (superuser olmayan). Operatorlar səhifəsini YALNIZ görür.
  - Operator       -> MsnOperator qeydi. Yalnız 'yoxlamada' olan sənədləri yoxlayır.

Axın: sənəd yaranır -> qurum təsdiqi (1-ci mərhələ) -> OPERATOR YOXLAMASI -> avtomatik olaraq təsdiq
hüququ olan şəxsə (2-ci mərhələ) düşür. İmtina olunsa sənəd 'Ləğv edilib' olur.

İş bölgüsü (bərabər yük):
  Baş admin 'max_per_round' (dövr limiti) seçir. Hər operator bir dövrdə ən çoxu bu qədər sənəd yoxlaya
  bilər. Limitə çatan operator DISABLE olur (yalnız Baş admin əl ilə aça bilər). Bütün (əl ilə
  söndürülməmiş) operatorlar limitə çatanda yeni dövr başlayır: sayğaclar sıfırlanır, limitə görə
  söndürülənlər avtomatik yenidən aktiv olur. Beləcə biri 10 sənəd yoxlayarkən digəri 1 yoxlamamış
  qalmır - fərq dövr limitindən çox ola bilməz.
  Baş admin operatoru əl ilə AÇANDA o, limitdən azad olur (manual_override) və Baş admin özü
  söndürənə qədər açıq qalır.
"""
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from authentication.constants import DEFAULT_INITIAL_PASSWORD
from authentication.models import User
from organizations.models import Organization
from organizations.permissions import is_full_admin, is_msn_admin
from workflow.models import MsnOperator, Notification, OperatorSettings
from workflow.notify import DOC_TYPE_LIST_ROUTE, _send_email_async, notify_stage2_reviewer


# ----------------------------------------------------------------------------
# Rollar / icazələr
# ----------------------------------------------------------------------------
def is_main_admin(user) -> bool:
    return bool(user and user.is_authenticated and user.is_superuser)


def is_operator(user) -> bool:
    return bool(
        user and user.is_authenticated
        and MsnOperator.objects.filter(user=user, is_active=True).exists()
    )


def can_view_operators_page(user) -> bool:
    return bool(is_full_admin(user) or is_msn_admin(user))


def can_edit_operators(user) -> bool:
    """Operatorlar səhifəsinin redaktəsi - YALNIZ Baş admin (adi adminlər yox)."""
    return is_main_admin(user)


def can_view_operator_queue(user) -> bool:
    return bool(is_full_admin(user) or is_operator(user))


# ----------------------------------------------------------------------------
# Dövr (round) məntiqi
# ----------------------------------------------------------------------------
def _disabled_message(operator) -> str:
    if operator.disabled_reason == MsnOperator.DISABLED_MANUAL:
        return "Siz Baş admin tərəfindən söndürülmüsünüz. Yoxlama aparmaq üçün Baş admin sizi aktiv etməlidir."
    return (
        "Bu dövr üçün yoxlama limitinizə çatmısınız. Digər operatorlar da limitə çatanda "
        "avtomatik yenidən aktiv olacaqsınız (və ya Baş admin sizi aça bilər)."
    )


def _maybe_start_new_round(cfg=None) -> bool:
    """Bütün (əl ilə söndürülməmiş) operatorlar limitə çatıbsa - yeni dövr."""
    cfg = cfg or OperatorSettings.get()
    pool = (
        MsnOperator.objects.filter(is_active=True, manual_override=False)
        .exclude(disabled_reason=MsnOperator.DISABLED_MANUAL)
    )
    if not pool.exists() or pool.filter(round_count__lt=cfg.max_per_round).exists():
        return False
    # Əvvəl 'pool'u id-lərlə sabitləyirik (update-dən sonra filtr dəyişməsin)
    ids = list(pool.values_list("id", flat=True))
    MsnOperator.objects.filter(is_active=True).update(round_count=0)
    MsnOperator.objects.filter(id__in=ids).update(is_enabled=True, disabled_reason="")
    OperatorSettings.objects.filter(pk=cfg.pk).update(round_number=F("round_number") + 1)
    return True


def _register_review(operator) -> None:
    cfg = OperatorSettings.get()
    operator.round_count += 1
    # Baş admin əl ilə açıbsa - limit tətbiq olunmur, yalnız Baş admin söndürəndə söndürülür.
    if operator.round_count >= cfg.max_per_round and not operator.manual_override:
        operator.is_enabled = False
        operator.disabled_reason = MsnOperator.DISABLED_LIMIT
    operator.save(update_fields=["round_count", "is_enabled", "disabled_reason"])
    _maybe_start_new_round(cfg)


def recompute_limits() -> None:
    """Limit dəyişəndə çağırılır: yeni limitə çatmış aktiv operatorlar söndürülür, lazımsa yeni dövr."""
    cfg = OperatorSettings.get()
    MsnOperator.objects.filter(
        is_active=True, is_enabled=True, manual_override=False, round_count__gte=cfg.max_per_round,
    ).update(is_enabled=False, disabled_reason=MsnOperator.DISABLED_LIMIT)
    _maybe_start_new_round(cfg)


def set_operator_enabled(operator, enabled: bool) -> None:
    """Baş admin əl ilə açır / söndürür.
    AÇMA     -> operator limitdən azad olur (manual_override), Baş admin söndürənə qədər açıq qalır.
    SÖNDÜRMƏ -> operator bloklanır (manual) və override ləğv olunur."""
    if enabled:
        operator.is_enabled = True
        operator.disabled_reason = ""
        operator.manual_override = True
    else:
        operator.is_enabled = False
        operator.disabled_reason = MsnOperator.DISABLED_MANUAL
        operator.manual_override = False
    operator.save(update_fields=["is_enabled", "disabled_reason", "manual_override"])
    if enabled is False:
        _maybe_start_new_round()


# ----------------------------------------------------------------------------
# Yoxlama
# ----------------------------------------------------------------------------
def _doc_link(document) -> str:
    return f"{DOC_TYPE_LIST_ROUTE.get(document.doc_type, '/modullar/lisenziya-senedler')}/{document.id}"


def notify_operators(document) -> None:
    """Sənəd operator yoxlamasına düşəndə bütün aktiv operatorlara bildiriş."""
    operators = list(User.objects.filter(msn_operator__is_active=True, is_active=True))
    if not operators:
        return
    title = f"Yoxlama gözləyən yeni sənəd — {document.number}"
    body = f"{document.get_doc_type_display()} kateqoriyasında {document.number} nömrəli sənəd operator yoxlamasını gözləyir."
    link = "/lisenziya-icazeleri/operator-yoxlama"
    Notification.objects.bulk_create([
        Notification(recipient=u, title=title, body=body, link=link) for u in operators
    ])
    for u in operators:
        _send_email_async(u.email, title, body)


def _notify_creator_rejected(document, reason: str) -> None:
    if not document.created_by_id:
        return
    title = f"Sənədiniz operator yoxlamasında imtina edildi — {document.number}"
    body = f"Səbəb: {reason}"
    Notification.objects.create(recipient=document.created_by, title=title, body=body, link=_doc_link(document))
    _send_email_async(document.created_by.email, title, f"{title}\n\n{body}")


@transaction.atomic
def review_document(document_id, user, decision: str, comment: str = ""):
    """Operator (və ya Baş admin) sənədi yoxlayır: decision = 'ugurlu' | 'imtina'."""
    from licenses.models import PermitDocument

    if decision not in ("ugurlu", "imtina"):
        raise ValidationError({"detail": "Qərar 'ugurlu' və ya 'imtina' olmalıdır."})
    comment = (comment or "").strip()
    if decision == "imtina" and not comment:
        raise ValidationError({"detail": "İmtina səbəbi tələb olunur."})

    document = PermitDocument.objects.select_for_update().get(pk=document_id)
    if document.status != "yoxlamada":
        raise ValidationError({"detail": "Bu sənəd operator yoxlamasında deyil və ya artıq yoxlanılıb."})

    operator = None
    if not is_main_admin(user):
        operator = MsnOperator.objects.select_for_update().filter(user=user, is_active=True).first()
        if operator is None:
            raise PermissionDenied("Yoxlama aparmaq üçün operator olmalısınız.")
        if not operator.is_enabled:
            # QEYD: 403 yox 400 - frontend 403-də istifadəçini ana səhifəyə atır.
            raise ValidationError({"detail": _disabled_message(operator)})

    now = timezone.now()
    document.operator_decision = decision
    document.operator_reviewed_by = user
    document.operator_reviewed_at = now
    document.operator_comment = comment

    if decision == "ugurlu":
        # Qurum təsdiqi artıq verilib; indi sənəd avtomatik təsdiq hüququ olan şəxsə (2-ci mərhələ) düşür.
        document.status = "gozleyir"
        document.approval_stage = 2
    else:
        document.status = "legv"
        document.rejected_by = user
        document.rejected_at = now
        document.rejection_reason = comment
    document.save()

    if operator is not None:
        _register_review(operator)

    if decision == "ugurlu":
        notify_stage2_reviewer(document)
    else:
        _notify_creator_rejected(document, comment)
    return document


# ----------------------------------------------------------------------------
# Operator yaratma
# ----------------------------------------------------------------------------
@transaction.atomic
def create_operator(data: dict, created_by) -> MsnOperator:
    org = Organization.objects.filter(code=Organization.CODE_MSN).first()
    user = User(
        first_name=data["first_name"], last_name=data["last_name"], username=data["username"],
        email=data["email"], phone=data.get("phone", ""), fin_kod=data.get("fin_kod", ""),
        organization=org,
    )
    user.set_password(DEFAULT_INITIAL_PASSWORD)
    user.must_change_password = True      # ilk girişdə yeni şifrə təyin edir (mövcud axın)
    user.save()
    return MsnOperator.objects.create(user=user, created_by=created_by)


def msn_operator_candidates():
    """Operator təyin oluna biləcək MSN istifadəçiləri: MSN təşkilatının aktiv işçiləri
    (Baş admin xaric), hazırda aktiv operator olmayanlar."""
    taken = MsnOperator.objects.filter(is_active=True).values_list("user_id", flat=True)
    return (
        User.objects.filter(is_active=True, is_superuser=False, organization__code=Organization.CODE_MSN)
        .exclude(id__in=list(taken))
        .select_related("department", "position")
        .order_by("first_name", "last_name", "username")
    )


@transaction.atomic
def assign_operator(user_id, created_by) -> MsnOperator:
    """Mövcud MSN istifadəçisini operator təyin edir (əvvəl operatorluqdan çıxarılıbsa - yenidən aktivləşdirir)."""
    user = msn_operator_candidates().filter(pk=user_id).first()
    if user is None:
        existing = MsnOperator.objects.filter(user_id=user_id, is_active=True).exists()
        raise ValidationError({"detail": (
            "Bu istifadəçi artıq operatordur." if existing
            else "Seçilmiş istifadəçi MSN-in aktiv işçisi deyil və ya Baş admindir."
        )})
    operator = MsnOperator.objects.filter(user=user).first()
    if operator is None:
        return MsnOperator.objects.create(user=user, created_by=created_by)
    operator.is_active = True
    operator.is_enabled = True
    operator.disabled_reason = ""
    operator.manual_override = False
    operator.round_count = 0
    operator.created_by = created_by
    operator.save()
    return operator


# ----------------------------------------------------------------------------
# Statistika
# ----------------------------------------------------------------------------
def _annotated_operators(day):
    docs_created = "user__permit_documents"
    reviewed = "user__operator_reviewed_documents"
    return (
        MsnOperator.objects.filter(is_active=True).select_related("user")
        .annotate(
            created_count=Count(docs_created, filter=Q(**{f"{docs_created}__created_at__date": day}), distinct=True),
            reviewed_count=Count(reviewed, filter=Q(**{f"{reviewed}__operator_reviewed_at__date": day}), distinct=True),
            approved_count=Count(reviewed, filter=Q(**{
                f"{reviewed}__operator_reviewed_at__date": day, f"{reviewed}__operator_decision": "ugurlu",
            }), distinct=True),
            rejected_count=Count(reviewed, filter=Q(**{
                f"{reviewed}__operator_reviewed_at__date": day, f"{reviewed}__operator_decision": "imtina",
            }), distinct=True),
            total_reviewed=Count(reviewed, distinct=True),
        )
        .order_by("user__first_name", "user__last_name", "user__username")
    )


def _operator_row(op, cfg) -> dict:
    u = op.user
    return {
        "id": op.id,
        "user_id": u.id,
        "username": u.username,
        "full_name": f"{u.first_name} {u.last_name}".strip() or u.username,
        "email": u.email,
        "phone": u.phone,
        "is_enabled": op.is_enabled,
        "disabled_reason": op.disabled_reason,
        "round_count": op.round_count,
        "manual_override": op.manual_override,
        "max_per_round": cfg.max_per_round,
        "created_today": getattr(op, "created_count", 0),
        "reviewed_today": getattr(op, "reviewed_count", 0),
        "approved_today": getattr(op, "approved_count", 0),
        "rejected_today": getattr(op, "rejected_count", 0),
        "reviewed_total": getattr(op, "total_reviewed", 0),
        "created_at": op.created_at,
    }


def build_operators_payload(day, viewer) -> dict:
    cfg = OperatorSettings.get()
    rows = [_operator_row(op, cfg) for op in _annotated_operators(day)]
    return {
        "date": day.isoformat(),
        "can_edit": can_edit_operators(viewer),
        "settings": {"max_per_round": cfg.max_per_round, "round_number": cfg.round_number},
        "totals": {
            "operators": len(rows),
            "created_today": sum(r["created_today"] for r in rows),
            "reviewed_today": sum(r["reviewed_today"] for r in rows),
            "pending_documents": _pending_count(),
        },
        "results": rows,
    }


def _pending_count() -> int:
    from licenses.models import PermitDocument
    return PermitDocument.objects.filter(status="yoxlamada").count()


def my_operator_status(user) -> dict:
    """Operator yoxlama səhifəsinin yuxarısındakı 'mənim limitim' paneli."""
    cfg = OperatorSettings.get()
    today = timezone.localdate()
    if is_main_admin(user):
        return {"role": "main_admin", "can_decide": True, "limited": False,
                "max_per_round": cfg.max_per_round, "round_number": cfg.round_number}
    op = MsnOperator.objects.filter(user=user, is_active=True).first()
    if op is None:
        return {"role": "viewer", "can_decide": False, "limited": False,
                "max_per_round": cfg.max_per_round, "round_number": cfg.round_number}
    from licenses.models import PermitDocument
    reviewed_today = PermitDocument.objects.filter(
        operator_reviewed_by=user, operator_reviewed_at__date=today,
    ).count()
    return {
        "role": "operator",
        "can_decide": op.is_enabled,
        "limited": True,
        "is_enabled": op.is_enabled,
        "disabled_reason": op.disabled_reason,
        "disabled_message": "" if op.is_enabled else _disabled_message(op),
        "manual_override": op.manual_override,
        "round_count": op.round_count,
        "max_per_round": cfg.max_per_round,
        "round_number": cfg.round_number,
        "reviewed_today": reviewed_today,
    }