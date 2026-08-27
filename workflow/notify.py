"""
Sənəd yaradılanda 1-ci mərhələ icraçılarına (qurum admini ya da təyin edilmiş MSN işçisi)
bildiriş + e-poçt göndərmək üçün köməkçi.

E-poçt HTTP cavabını gecikdirməsin deyə ayrıca thread-də (fire-and-forget) göndərilir -
sistemdə hələ Celery/RQ kimi tapşırıq növbəsi olmadığı üçün ən sadə etibarlı yanaşma budur.
send_mail_to onsuz da özü xəta halında sakitcə logla kifayətlənir (bax authentication.utils),
ona görə e-poçt problemi sənəd yaradılmasını heç vaxt pozmur.
"""
import threading

from workflow.models import DocumentWorkflowConfig, Notification

DOC_TYPE_LIST_ROUTE = {
    "ixrac": "/modullar/lisenziya-senedler/idxal-ixrac",
    "idxal": "/modullar/lisenziya-senedler/idxal-ixrac",
    "istehsal": "/modullar/lisenziya-senedler/istehsal",
    "xususi_satis": "/modullar/lisenziya-senedler/xususi-satis",
    "gomrukden_azadolma": "/modullar/lisenziya-senedler/edv-guzesti",
    "edvden_azadolma": "/modullar/lisenziya-senedler/edv-guzesti",
}


def _send_email_async(to_email: str, subject: str, body: str) -> None:
    if not to_email:
        return
    from authentication.utils import send_mail_to
    threading.Thread(target=send_mail_to, args=(to_email, subject, body), daemon=True).start()


def _stage1_recipients(document):
    from authentication.models import User
    from workflow.models import OrgReviewerPermission

    config = DocumentWorkflowConfig.objects.filter(doc_type=document.doc_type).first()
    stage1_mode = config.stage1_mode if config else "qurum"

    if stage1_mode == "msn" and config and config.stage1_user_id and config.stage1_user.is_active:
        return [config.stage1_user]

    if not document.organization_id:
        return []

    # 'qurum' rejimi: təşkilatın həm admini, HƏM DƏ bu sənəd növü üzrə 'Qurum yoxlaması
    # icazəsi' (OrgReviewerPermission) verilmiş bütün işçiləri bildirişi alır - tək bir nəfər
    # (yalnız admin) yox, hamısı, ki, kimsə tətildə/məşğul olsa belə yoxlama gecikməsin.
    org_admin_ids = User.objects.filter(
        organization_id=document.organization_id, is_org_admin=True, is_active=True,
    ).values_list("id", flat=True)
    reviewer_ids = OrgReviewerPermission.objects.filter(
        organization_id=document.organization_id, doc_type=document.doc_type, can_review=True,
    ).values_list("user_id", flat=True)

    recipient_ids = set(org_admin_ids) | set(reviewer_ids)
    return list(User.objects.filter(id__in=recipient_ids, is_active=True))


def notify_stage1_reviewers(document) -> None:
    """Sənəd yaradıldıqdan dərhal sonra çağırılır (bax licenses.views.PermitDocumentViewSet.create).
    Konfiqurasiya yoxdursa əvvəlki davranışa uyğun defolt olaraq 'qurum' rejimi tətbiq olunur."""
    recipients = _stage1_recipients(document)
    if not recipients:
        return

    title = f"Yeni sənəd yoxlanışa göndərildi — {document.number}"
    body = (
        f"{document.get_doc_type_display()} kateqoriyasında yeni sənəd ({document.number}) "
        f"1-ci mərhələ yoxlamasını gözləyir."
    )
    link = f"{DOC_TYPE_LIST_ROUTE.get(document.doc_type, '/modullar/lisenziya-senedler')}/{document.id}"

    Notification.objects.bulk_create([
        Notification(recipient=user, title=title, body=body, link=link) for user in recipients
    ])
    for user in recipients:
        _send_email_async(user.email, title, body)


def notify_stage2_reviewer(document) -> None:
    """1-ci mərhələ təsdiqləndikdən dərhal sonra çağırılır (bax
    licenses.views.PermitDocumentViewSet.approve) - sənəd 2-ci mərhələyə keçəndə 2-ci mərhələ
    icraçısına (həmişə MSN, bax DocumentWorkflowConfig.stage2_user) bildiriş göndərir."""
    config = DocumentWorkflowConfig.objects.filter(doc_type=document.doc_type).first()
    if not config or not config.stage2_user_id or not config.stage2_user.is_active:
        return

    title = f"Sənəd 2-ci mərhələ təsdiqini gözləyir — {document.number}"
    body = (
        f"{document.get_doc_type_display()} kateqoriyasında {document.number} nömrəli sənəd "
        f"1-ci mərhələni keçdi və son təsdiqinizi gözləyir."
    )
    link = f"{DOC_TYPE_LIST_ROUTE.get(document.doc_type, '/modullar/lisenziya-senedler')}/{document.id}"

    Notification.objects.create(recipient=config.stage2_user, title=title, body=body, link=link)
    _send_email_async(config.stage2_user.email, title, body)


def notify_certificate_ready(document, certificate) -> None:
    """Lisenziya BÜTÜN mərhələlərdən keçib təsdiqləndikdə (ya da mərhələli təsdiq
    söndürülübsə, sənəd yaradılan kimi) çağırılır - müraciəti göndərən şəxsə (created_by)
    lisenziyasının hazır olduğunu bildirir və rəsmi sənədin göstərildiyi səhifəyə yönləndirir."""
    recipient = document.created_by
    if not recipient or not recipient.is_active:
        return

    title = f"Lisenziyanız təsdiqləndi — {document.number}"
    body = (
        f"{document.get_doc_type_display()} kateqoriyasında {document.number} nömrəli "
        f"müraciətiniz təsdiqləndi. Rəsmi sənədinizi görmək üçün klikləyin."
    )
    link = f"/lisenziya-icazeleri/sened/{certificate.id}"

    Notification.objects.create(recipient=recipient, title=title, body=body, link=link)
    _send_email_async(recipient.email, title, body)


def notify_certificate_signed(document, certificate) -> None:
    """Sertifikat SİM İmza / Asan İmza ilə imzalandıqda çağırılır (bax
    licenses.views.LicenseCertificateView.sign) - müraciəti göndərən şəxsə (created_by)
    sənədin artıq imzalandığını bildirir."""
    recipient = document.created_by
    if not recipient or not recipient.is_active:
        return

    method_label = certificate.get_signature_method_display() or "elektron imza"
    title = f"Lisenziyanız imzalandı — {document.number}"
    body = (
        f"{document.get_doc_type_display()} kateqoriyasında {document.number} nömrəli "
        f"sənədiniz {method_label} ilə imzalandı."
    )
    link = f"/lisenziya-icazeleri/sened/{certificate.id}"

    Notification.objects.create(recipient=recipient, title=title, body=body, link=link)
    _send_email_async(recipient.email, title, body)