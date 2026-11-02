"""Sənədin 'natamam (qaralama)' -> 'yoxlamaya göndərildi' keçidi.

Məcburi sənədlər artıq yaradılma anında bloklayıcı deyil: bir və ya bir neçə məcburi fayl
çatışmırsa sənəd 'qaralama' (natamam) statusunda qalır. Çatışmayan fayllar yükləndikdə
(və ya yaradılma anında hamısı varsa) submit_if_complete() sənədi növbəti addıma göndərir.
"""
from django.utils import timezone

from licenses.field_schema import get_schema
from licenses.models import ApprovalSettings, LicenseCertificate


def missing_required_files(document) -> list:
    """Hələ yüklənməmiş məcburi faylların siyahısı: [{'key': ..., 'label': ...}]."""
    if document.is_confidential:
        return []
    schema = get_schema(document.doc_type)
    uploaded = set(document.files.values_list("field_key", flat=True))
    return [
        {"key": f["key"], "label": f["label"]}
        for f in schema["file_fields"]
        if f.get("required") and f["key"] not in uploaded
    ]


def submit_if_complete(document) -> bool:
    """Sənəd qaralamadadırsa və bütün məcburi fayllar yüklənibsə - onu göndərir.

    Növbəti addım:
      - kateqoriyada mərhələli təsdiq söndürülübsə -> birbaşa 'aktiv' + sertifikat;
      - əks halda                                  -> 'gozleyir', 1-ci mərhələ (qurum təsdiqi).
    Operator yoxlaması burada DEYİL - qurum təsdiqindən SONRA gəlir (bax PermitDocument.approve_stage).
    """
    if document.status != "qaralama":
        return False
    if missing_required_files(document):
        return False

    from workflow.notify import notify_certificate_ready, notify_stage1_reviewers

    document.submitted_at = timezone.now()
    document.approval_stage = 1

    if not ApprovalSettings.get_for(document.doc_type).staged_approval_enabled:
        document.status = "aktiv"
        document.save()
        certificate, _ = LicenseCertificate.objects.get_or_create(
            permit_document=document, defaults={"form_data": document.form_data}
        )
        notify_certificate_ready(document, certificate)
    else:
        document.status = "gozleyir"
        document.save()
        notify_stage1_reviewers(document)
    return True