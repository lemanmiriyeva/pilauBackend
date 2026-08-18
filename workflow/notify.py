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
    "edv_guzest": "/modullar/lisenziya-senedler/edv-guzesti",
}


def _send_email_async(to_email: str, subject: str, body: str) -> None:
    if not to_email:
        return
    from authentication.utils import send_mail_to
    threading.Thread(target=send_mail_to, args=(to_email, subject, body), daemon=True).start()


def _stage1_recipients(document):
    from authentication.models import User

    config = DocumentWorkflowConfig.objects.filter(doc_type=document.doc_type).first()
    stage1_mode = config.stage1_mode if config else "qurum"

    if stage1_mode == "msn" and config and config.stage1_user_id and config.stage1_user.is_active:
        return [config.stage1_user]

    if document.organization_id:
        return list(
            User.objects.filter(
                organization_id=document.organization_id, is_org_admin=True, is_active=True,
            )
        )
    return []


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